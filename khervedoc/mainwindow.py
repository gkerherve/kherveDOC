"""Main window: tabbed interface (Formatted | LaTeX | PDF) with full menus."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction, QActionGroup, QGuiApplication, QKeySequence, QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSpinBox,
    QSplitter, QStatusBar, QTabWidget, QToolBar, QToolButton,
    QVBoxLayout, QWidget,
)

from . import (
    __version__, equations, git_backend, icons, kdocz, page_sizes,
    symbols, version_string,
)
from .compiler import CompileResult, compile_tex, tectonic_available
from .editor import DocumentEditor, TEMPLATE_CHOICES
from . import examples, importers
from .latex_view import LatexView
from .model import (
    Author, Document, DocMeta, Paragraph, Section, Text, Title,
    from_json, to_json,
)
from .preview import PdfPreview
from .serializer import serialize_document


# ---------- background compile ----------

class _CompileWorker(QThread):
    finished_with = Signal(object)

    def __init__(self, tex_source: str, workdir: Path,
                 source_dir: Path | None = None):
        super().__init__()
        self._tex = tex_source
        self._workdir = workdir
        self._source_dir = source_dir

    def run(self) -> None:
        self.finished_with.emit(
            compile_tex(self._tex, self._workdir, source_dir=self._source_dir))


class _GitNetworkWorker(QThread):
    """Run pull / push on a background thread so the GUI doesn't lock
    up for the duration of a libgit2 network round-trip. Without this,
    saving or pulling against an unreachable remote freezes the window
    for 30+ seconds (Windows shows it as "Not Responding") — to the
    user that reads as a crash, even though it's just blocked I/O on
    the main thread.

    The worker emits `finished_with` carrying (operation, success,
    message). The caller decides how to surface that — status bar,
    message box, etc.
    """
    finished_with = Signal(str, bool, str)  # op, ok, msg

    def __init__(self, op: str, repo_dir: Path,
                 remote_name: str = "origin"):
        super().__init__()
        self._op = op   # "pull" or "push"
        self._repo_dir = repo_dir
        self._remote = remote_name

    def run(self) -> None:
        from . import git_backend
        try:
            if self._op == "pull":
                ok, msg = git_backend.pull(self._repo_dir, self._remote)
            elif self._op == "push":
                ok = git_backend.push(self._repo_dir, self._remote)
                msg = (f"Pushed to {self._remote}." if ok
                       else f"Push to {self._remote} failed.")
            else:
                ok, msg = False, f"Unknown git op: {self._op!r}"
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"{self._op} crashed: {exc}"
        self.finished_with.emit(self._op, ok, msg)


# ---------- document properties dialog ----------

_FONT_FAMILIES = [
    ("default",   "Computer Modern (LaTeX default)"),
    ("times",     "Times Roman"),
    ("palatino",  "Palatino"),
    ("charter",   "Charter"),
    ("libertine", "Linux Libertine"),
    ("helvetica", "Helvetica (sans-serif)"),
    ("courier",   "Courier (monospace)"),
]


class DocSettingsDialog(QDialog):
    """All document-level typesetting knobs in one tabbed dialog."""

    def __init__(self, meta: DocMeta, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Document settings")
        self.resize(560, 540)
        # Keep a reference so result_meta can carry forward fields this
        # dialog doesn't expose (page_size, etc.) without dropping them.
        self._orig_meta = meta

        tabs = QTabWidget(self)
        tabs.addTab(self._build_metadata_tab(meta), "Metadata")
        tabs.addTab(self._build_text_tab(meta), "Text")
        tabs.addTab(self._build_layout_tab(meta), "Layout")
        tabs.addTab(self._build_packages_tab(meta), "Packages")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs); layout.addWidget(buttons)

    # ---- tabs ----

    def _build_metadata_tab(self, meta: DocMeta) -> QWidget:
        self._title = QLineEdit(meta.title)
        self._author = QLineEdit(meta.author)
        self._docclass = QComboBox(); self._docclass.setEditable(True)
        self._docclass.addItems(["article", "report", "book", "letter",
                                 "beamer", "memoir"])
        self._docclass.setCurrentText(meta.documentclass)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow("Title:", self._title)
        form.addRow("Author:", self._author)
        form.addRow("Document class:", self._docclass)
        return w

    def _build_text_tab(self, meta: DocMeta) -> QWidget:
        self._font_family = QComboBox()
        for code, label in _FONT_FAMILIES:
            self._font_family.addItem(label, code)
        idx = self._font_family.findData(meta.body_font_family)
        if idx >= 0: self._font_family.setCurrentIndex(idx)

        self._body_pt = QComboBox()
        for v in (10, 11, 12):
            self._body_pt.addItem(f"{v} pt", v)
        idx = self._body_pt.findData(meta.body_font_pt)
        if idx >= 0: self._body_pt.setCurrentIndex(idx)

        self._line_spacing = QDoubleSpinBox()
        self._line_spacing.setRange(0.8, 3.0)
        self._line_spacing.setSingleStep(0.1)
        self._line_spacing.setDecimals(2)
        self._line_spacing.setValue(meta.line_spacing)

        self._para_indent = QCheckBox("Indent first line of every paragraph")
        self._para_indent.setChecked(meta.paragraph_indent)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow("Body font:", self._font_family)
        form.addRow("Body size:", self._body_pt)
        form.addRow("Line spacing:", self._line_spacing)
        form.addRow("", self._para_indent)
        return w

    def _build_layout_tab(self, meta: DocMeta) -> QWidget:
        def _margin_spin(value: float) -> QDoubleSpinBox:
            sb = QDoubleSpinBox()
            sb.setRange(0.5, 6.0); sb.setSingleStep(0.1); sb.setSuffix(" cm")
            sb.setDecimals(1); sb.setValue(value)
            return sb

        self._m_top = _margin_spin(meta.margin_top_cm)
        self._m_bottom = _margin_spin(meta.margin_bottom_cm)
        self._m_left = _margin_spin(meta.margin_left_cm)
        self._m_right = _margin_spin(meta.margin_right_cm)
        self._columns = QComboBox()
        for n in (1, 2, 3):
            label = {1: "1 column (single)", 2: "2 columns",
                     3: "3 columns"}[n]
            self._columns.addItem(label, n)
        idx = self._columns.findData(int(getattr(meta, "column_count", 1) or 1))
        if idx >= 0: self._columns.setCurrentIndex(idx)

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel("<b>Page margins</b>"))
        form.addRow("Top:", self._m_top)
        form.addRow("Bottom:", self._m_bottom)
        form.addRow("Left:", self._m_left)
        form.addRow("Right:", self._m_right)
        form.addRow(QLabel("<b>Columns</b>"))
        form.addRow("Whole document:", self._columns)
        form.addRow(QLabel(
            "<i>For a multi-column region inside an otherwise one-column<br>"
            "document, use Insert &rarr; Multi-column region instead.</i>"))
        return w

    def _build_packages_tab(self, meta: DocMeta) -> QWidget:
        self._packages = QPlainTextEdit("\n".join(meta.packages))
        self._packages.setPlaceholderText("One package name per line")
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(
            "Extra LaTeX packages, one per line. "
            "geometry / setspace are added automatically by kherveDOC."))
        v.addWidget(self._packages, 1)
        return w

    # ---- result ----

    def result_meta(self) -> DocMeta:
        pkgs = [p.strip() for p in self._packages.toPlainText().splitlines()
                if p.strip()]
        return DocMeta(
            title=self._title.text(),
            author=self._author.text(),
            documentclass=self._docclass.currentText().strip() or "article",
            packages=pkgs,
            page_size=self._orig_meta.page_size,
            margin_top_cm=self._m_top.value(),
            margin_bottom_cm=self._m_bottom.value(),
            margin_left_cm=self._m_left.value(),
            margin_right_cm=self._m_right.value(),
            body_font_pt=int(self._body_pt.currentData() or 12),
            body_font_family=str(self._font_family.currentData() or "default"),
            line_spacing=self._line_spacing.value(),
            paragraph_indent=self._para_indent.isChecked(),
            column_count=int(self._columns.currentData() or 1),
            frontmatter_extras=self._orig_meta.frontmatter_extras,
            preamble_extras=self._orig_meta.preamble_extras,
        )


# Back-compat alias for the older name used elsewhere in this file.
DocPropertiesDialog = DocSettingsDialog


class SymbolPickerWindow(QWidget):
    """Floating, non-modal palette of LaTeX symbols.

    Built as a standalone Qt.Tool window so the user can keep it open
    alongside the main editor, drift between paragraphs, and click
    glyphs to drop them into the formatted text at the current cursor.
    """

    symbolPicked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        # Tool window = floats above the parent, has a small frame, and
        # does NOT block the main window the way a modal QDialog does.
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Symbols")
        self.resize(440, 480)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        outer = QVBoxLayout(inner)
        outer.setSpacing(8)
        outer.setContentsMargins(6, 6, 6, 6)

        for group_name, items in symbols.SYMBOL_GROUPS:
            label = QLabel(f"<b>{group_name}</b>")
            label.setStyleSheet("color: #444; padding-top: 4px;")
            outer.addWidget(label)
            grid = QGridLayout()
            grid.setSpacing(2)
            cols = 10
            for i, (latex, glyph) in enumerate(items):
                btn = QPushButton(glyph)
                btn.setToolTip(latex)
                btn.setFixedSize(32, 28)
                btn.setStyleSheet(
                    "QPushButton { font-size: 12pt; padding: 0; }")
                btn.clicked.connect(
                    lambda checked=False, tex=latex: self.symbolPicked.emit(tex))
                grid.addWidget(btn, i // cols, i % cols)
            outer.addLayout(grid)

        outer.addStretch(1)
        scroll.setWidget(inner)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)


# Back-compat: older code references the dialog name. The window also
# satisfies the rest of MainWindow's plumbing.
SymbolPickerDialog = SymbolPickerWindow


class EquationBuilderWindow(QWidget):
    """Floating palette of templated math constructs.

    Clicking a tile drops the template's LaTeX form at the current
    cursor, wrapped in inline math. Templates use a U+25A1 placeholder
    (□) so the user can immediately spot the slots they need to fill in.
    """

    templatePicked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Equation builder")
        self.resize(520, 540)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        outer = QVBoxLayout(inner)
        outer.setSpacing(8)
        outer.setContentsMargins(6, 6, 6, 6)

        for group_name, items in equations.EQUATION_GROUPS:
            label = QLabel(f"<b>{group_name}</b>")
            label.setStyleSheet("color: #444; padding-top: 4px;")
            outer.addWidget(label)
            grid = QGridLayout()
            grid.setSpacing(2)
            cols = 6
            for i, (latex, preview) in enumerate(items):
                btn = QPushButton(preview)
                btn.setToolTip(latex)
                btn.setMinimumHeight(30)
                btn.setStyleSheet(
                    "QPushButton { font-size: 10pt; padding: 2px 6px; "
                    "text-align: center; }")
                btn.clicked.connect(
                    lambda checked=False, tex=latex: self.templatePicked.emit(tex))
                grid.addWidget(btn, i // cols, i % cols)
            outer.addLayout(grid)

        outer.addStretch(1)
        scroll.setWidget(inner)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)


# ---------- main window ----------

_RECENT_FILES_MAX = 8


class _FindBar(QWidget):
    """Compact find bar shown at the bottom of the editor area."""

    find_next = Signal()
    find_prev = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)

        lay.addWidget(QLabel("Find:"))
        self.field = QLineEdit(self)
        self.field.setPlaceholderText("Search text...")
        self.field.setClearButtonEnabled(True)
        self.field.returnPressed.connect(self.find_next)
        lay.addWidget(self.field, 1)

        prev_btn = QPushButton("Previous", self)
        prev_btn.clicked.connect(self.find_prev)
        lay.addWidget(prev_btn)

        next_btn = QPushButton("Next", self)
        next_btn.setDefault(True)
        next_btn.clicked.connect(self.find_next)
        lay.addWidget(next_btn)

        self.case_cb = QCheckBox("Match case", self)
        lay.addWidget(self.case_cb)

        close_btn = QPushButton("x", self)
        close_btn.setFixedWidth(28)
        close_btn.setFlat(True)
        close_btn.clicked.connect(self.closed)
        lay.addWidget(close_btn)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.closed.emit()
        else:
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    # Module-level registry of every live MainWindow. Needed so windows
    # spawned via File > New window don't get garbage-collected the
    # moment the local reference falls out of scope, and so the Window
    # menu can list every open document.
    _windows: list["MainWindow"] = []

    def __init__(self):
        super().__init__()
        MainWindow._windows.append(self)
        self._current_path: Path | None = None
        # Imported (.tex/.docx) files don't get a "current path" — the user
        # has to Save As before kherveDOC knows where to save the .kdocz.
        # But we still want the original file's parent directory available
        # so relative \includegraphics paths (`Images/foo.png` next to the
        # imported .tex) resolve when compiling the preview.
        self._import_source_dir: Path | None = None
        self._kdocz_extract_dir: Path | None = None   # set when opening a .kdocz
        self._build_dir = Path(tempfile.mkdtemp(prefix="khervedoc-"))
        self._compile_worker: _CompileWorker | None = None
        self._pending_recompile = False
        # Background git worker for pull / push so the GUI never
        # blocks on a slow remote. None when no op is in flight.
        self._git_worker: _GitNetworkWorker | None = None
        # Persistent settings (Windows registry / platform-equivalent)
        # used for the Open Recent list and any other cross-session prefs.
        self._settings = QSettings("kherveDOC", "kherveDOC")
        raw_recent = self._settings.value("recent_files", []) or []
        # QSettings on Windows returns either a list, a single string, or
        # None depending on how many entries we wrote. Normalise.
        if isinstance(raw_recent, str):
            raw_recent = [raw_recent]
        self._recent: list[Path] = [
            Path(p) for p in raw_recent if p and Path(p).exists()]

        screen = QGuiApplication.primaryScreen().availableGeometry()
        w = min(1500, int(screen.width() * 0.85))
        h = min(950, int(screen.height() * 0.85))
        self.resize(w, h)
        # Cascade secondary windows so they don't perfectly overlap the
        # first one. The Nth window shifts by (N-1)*30 px in both axes.
        cascade = (len(MainWindow._windows) - 1) * 30
        self.move(screen.x() + (screen.width() - w) // 2 + cascade,
                  screen.y() + (screen.height() - h) // 2 + cascade)

        self._editor = DocumentEditor(self)
        self._latex_view = LatexView(self)
        self._preview = PdfPreview(self)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._editor, "Formatted")
        self._tabs.addTab(self._latex_view, "LaTeX")
        self._tabs.addTab(self._preview, "PDF")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Splitter: left = tabs, right = PDF panel (hidden until toggled).
        self._splitter = QSplitter(Qt.Horizontal, self)
        self._splitter.addWidget(self._tabs)
        self._pdf_side_panel = PdfPreview(self)
        self._pdf_side_panel.hide()
        self._splitter.addWidget(self._pdf_side_panel)
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 3)

        # Find bar (hidden until Ctrl+F).
        self._find_bar = _FindBar(self)
        self._find_bar.hide()
        self._find_bar.find_next.connect(lambda: self._do_find(forward=True))
        self._find_bar.find_prev.connect(lambda: self._do_find(forward=False))
        self._find_bar.closed.connect(self._find_bar.hide)

        central = QWidget(self)
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self._splitter, 1)
        cl.addWidget(self._find_bar)
        self.setCentralWidget(central)
        self._side_by_side = False

        self._status = QStatusBar(self)
        self.setStatusBar(self._status)

        # Left side: full document path (or "Untitled" before first save).
        self._path_label = QLabel("Untitled", self)
        self._path_label.setStyleSheet("color: #444; padding: 0 6px;")
        self._path_label.setMinimumWidth(200)
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._status.addWidget(self._path_label, 1)   # stretch=1 → takes the space

        # Right side, in order: zoom-out icon, slider, zoom-in icon, percent
        # readout, then the tectonic indicator. Matches Word's bottom-bar
        # zoom layout: drag the slider to scale live; click + / - to step.
        self._zoom_out_btn = QToolButton(self)
        self._zoom_out_btn.setIcon(icons.zoom_out())
        self._zoom_out_btn.setToolTip("Zoom out")
        self._zoom_out_btn.setAutoRaise(True)
        self._zoom_out_btn.clicked.connect(lambda: self._nudge_zoom(-10))
        self._status.addPermanentWidget(self._zoom_out_btn)

        self._zoom_slider = QSlider(Qt.Horizontal, self)
        self._zoom_slider.setRange(25, 300)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setMinimumWidth(140)
        self._zoom_slider.setMaximumWidth(220)
        self._zoom_slider.setSingleStep(10)
        self._zoom_slider.setPageStep(25)
        self._zoom_slider.setTickPosition(QSlider.TicksBelow)
        self._zoom_slider.setTickInterval(25)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        self._status.addPermanentWidget(self._zoom_slider)

        self._zoom_in_btn = QToolButton(self)
        self._zoom_in_btn.setIcon(icons.zoom_in())
        self._zoom_in_btn.setToolTip("Zoom in")
        self._zoom_in_btn.setAutoRaise(True)
        self._zoom_in_btn.clicked.connect(lambda: self._nudge_zoom(+10))
        self._status.addPermanentWidget(self._zoom_in_btn)

        self._zoom_label = QLabel("100%", self)
        self._zoom_label.setMinimumWidth(42)
        self._zoom_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._zoom_label.setStyleSheet("padding-right: 6px; color: #444;")
        self._status.addPermanentWidget(self._zoom_label)

        # PDF-specific zoom (separate from the editor zoom).
        self._pdf_zoom_sep = QLabel(" | PDF:", self)
        self._pdf_zoom_sep.setStyleSheet("color: #888; padding: 0 2px;")
        self._status.addPermanentWidget(self._pdf_zoom_sep)

        self._pdf_zoom_out_btn = QToolButton(self)
        self._pdf_zoom_out_btn.setIcon(icons.zoom_out())
        self._pdf_zoom_out_btn.setToolTip("PDF zoom out")
        self._pdf_zoom_out_btn.setAutoRaise(True)
        self._pdf_zoom_out_btn.clicked.connect(lambda: self._nudge_pdf_zoom(-10))
        self._status.addPermanentWidget(self._pdf_zoom_out_btn)

        self._pdf_zoom_slider = QSlider(Qt.Horizontal, self)
        self._pdf_zoom_slider.setRange(25, 400)
        self._pdf_zoom_slider.setValue(100)
        self._pdf_zoom_slider.setMinimumWidth(100)
        self._pdf_zoom_slider.setMaximumWidth(180)
        self._pdf_zoom_slider.setSingleStep(10)
        self._pdf_zoom_slider.setPageStep(25)
        self._pdf_zoom_slider.setTickPosition(QSlider.TicksBelow)
        self._pdf_zoom_slider.setTickInterval(25)
        self._pdf_zoom_slider.valueChanged.connect(self._on_pdf_zoom_changed)
        self._status.addPermanentWidget(self._pdf_zoom_slider)

        self._pdf_zoom_in_btn = QToolButton(self)
        self._pdf_zoom_in_btn.setIcon(icons.zoom_in())
        self._pdf_zoom_in_btn.setToolTip("PDF zoom in")
        self._pdf_zoom_in_btn.setAutoRaise(True)
        self._pdf_zoom_in_btn.clicked.connect(lambda: self._nudge_pdf_zoom(+10))
        self._status.addPermanentWidget(self._pdf_zoom_in_btn)

        self._pdf_zoom_label = QLabel("100%", self)
        self._pdf_zoom_label.setMinimumWidth(42)
        self._pdf_zoom_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._pdf_zoom_label.setStyleSheet("padding-right: 6px; color: #444;")
        self._status.addPermanentWidget(self._pdf_zoom_label)

        self._tectonic_label = QLabel(
            "tectonic: OK" if tectonic_available() else "tectonic: NOT FOUND — preview disabled",
            self)
        self._status.addPermanentWidget(self._tectonic_label)

        # Initially on Formatted tab — hide PDF zoom, show editor zoom.
        self._pdf_zoom_sep.hide()
        self._pdf_zoom_out_btn.hide()
        self._pdf_zoom_slider.hide()
        self._pdf_zoom_in_btn.hide()
        self._pdf_zoom_label.hide()

        # Set icon colors before building actions so they render correctly.
        self._is_dark = self._settings.value("theme_dark", False, type=bool)
        if self._is_dark:
            icons.set_dark(True)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()

        self._editor.documentChanged.connect(self._on_doc_changed)
        self._editor.text_edit.cursorPositionChanged.connect(self._sync_toolbar_state)
        self._latex_view.latexEdited.connect(self._on_latex_edited)
        self._suppress_latex_update = False

        # Apply persisted theme styling to editor/latex panels.
        if self._is_dark:
            self._toggle_theme(True)

        # Restore side-by-side panel state.
        if self._settings.value("side_by_side", False, type=bool):
            self.act_side_by_side.setChecked(True)
            self._toggle_side_by_side(True)

        self._editor.set_document(_starter_document())
        self._update_title()
        self._kick_compile()

    # ----- actions -----

    def _build_actions(self) -> None:
        e = self._editor

        # File
        self.act_new = QAction(icons.file_new(), "&New", self,
                               shortcut=QKeySequence.New, triggered=self._new)
        self.act_new_window = QAction("New &window", self,
                                      shortcut=QKeySequence("Ctrl+Shift+N"),
                                      triggered=self._new_window)
        self.act_open = QAction(icons.file_open(), "&Open...", self,
                                shortcut=QKeySequence.Open, triggered=self._open)
        self.act_open_in_new_window = QAction(
            "Open in new wind&ow...", self,
            shortcut=QKeySequence("Ctrl+Shift+O"),
            triggered=self._open_in_new_window)
        self.act_save = QAction(icons.file_save(), "&Save", self,
                                shortcut=QKeySequence.Save, triggered=self._save)
        self.act_save_as = QAction("Save &As...", self,
                                   shortcut=QKeySequence.SaveAs, triggered=self._save_as)
        self.act_close_doc = QAction("&Close document", self, triggered=self._new)
        self.act_import_tex = QAction("Import .&tex...", self, triggered=self._import_tex)
        self.act_import_docx = QAction("Import .&docx...", self, triggered=self._import_docx)
        self.act_export_tex = QAction("Export .&tex...", self, triggered=self._export_tex)
        self.act_export_pdf = QAction(icons.export_pdf(), "Export .&pdf...", self,
                                      triggered=self._export_pdf)
        self.act_doc_props = QAction("Document &properties...", self,
                                     triggered=self._edit_props)
        self.act_quit = QAction("&Quit", self, shortcut=QKeySequence.Quit,
                                triggered=self.close)

        # Edit
        text = self._editor.text_edit
        self.act_undo = QAction(icons.undo(), "&Undo", self,
                                shortcut=QKeySequence.Undo, triggered=text.undo)
        self.act_redo = QAction(icons.redo(), "&Redo", self,
                                shortcut=QKeySequence.Redo, triggered=text.redo)
        self.act_cut = QAction("Cu&t", self, shortcut=QKeySequence.Cut, triggered=text.cut)
        self.act_copy = QAction("&Copy", self, shortcut=QKeySequence.Copy, triggered=text.copy)
        self.act_paste = QAction("&Paste", self, shortcut=QKeySequence.Paste, triggered=text.paste)
        self.act_select_all = QAction("Select &All", self,
                                      shortcut=QKeySequence.SelectAll, triggered=text.selectAll)
        self.act_clear_fmt = QAction("Clear &formatting", self,
                                     triggered=e.clear_formatting)
        self.act_find = QAction("&Find...", self,
                                shortcut=QKeySequence.Find,
                                triggered=self._show_find_bar)

        # Alignment (exclusive group — exactly one is checked at any time)
        self.alignment_group = QActionGroup(self)
        self.alignment_group.setExclusive(True)
        self.act_align_left = QAction(icons.align_left(), "Align &left", self,
                                      checkable=True,
                                      triggered=lambda: e.apply_alignment("left"))
        self.act_align_center = QAction(icons.align_center(), "Align &center", self,
                                        checkable=True,
                                        triggered=lambda: e.apply_alignment("center"))
        self.act_align_right = QAction(icons.align_right(), "Align &right", self,
                                       checkable=True,
                                       triggered=lambda: e.apply_alignment("right"))
        self.act_align_justify = QAction(icons.align_justify(), "&Justify", self,
                                         checkable=True,
                                         triggered=lambda: e.apply_alignment("justify"))
        for a in (self.act_align_left, self.act_align_center,
                  self.act_align_right, self.act_align_justify):
            self.alignment_group.addAction(a)
        self.act_align_left.setChecked(True)

        # Document-wide column count — exclusive group with 1/2/3 columns.
        # Lambdas capture the value so each trigger sets the same field
        # via the shared _set_column_count helper.
        self.columns_group = QActionGroup(self)
        self.columns_group.setExclusive(True)
        self.act_cols_1 = QAction(icons.one_column(), "&1 column", self,
                                  checkable=True,
                                  triggered=lambda: self._set_column_count(1))
        self.act_cols_2 = QAction(icons.two_columns(), "&2 columns", self,
                                  checkable=True,
                                  triggered=lambda: self._set_column_count(2))
        self.act_cols_3 = QAction(icons.three_columns(), "&3 columns", self,
                                  checkable=True,
                                  triggered=lambda: self._set_column_count(3))
        for a in (self.act_cols_1, self.act_cols_2, self.act_cols_3):
            self.columns_group.addAction(a)
        self.act_cols_1.setChecked(True)

        # Format
        self.act_bold = QAction(icons.bold(), "&Bold", self,
                                shortcut=QKeySequence.Bold, checkable=True,
                                triggered=lambda: e.toggle_mark("bold"))
        self.act_italic = QAction(icons.italic(), "&Italic", self,
                                  shortcut=QKeySequence.Italic, checkable=True,
                                  triggered=lambda: e.toggle_mark("italic"))
        self.act_underline = QAction(icons.underline(), "&Underline", self,
                                     shortcut=QKeySequence.Underline, checkable=True,
                                     triggered=lambda: e.toggle_mark("underline"))
        self.act_strike = QAction(icons.strike(), "&Strikethrough", self,
                                  checkable=True,
                                  triggered=lambda: e.toggle_mark("strikethrough"))
        self.act_code = QAction(icons.code(), "&Code (monospace)", self,
                                checkable=True,
                                triggered=lambda: e.toggle_mark("code"))
        self.act_smallcaps = QAction(icons.smallcaps(), "Small caps", self,
                                     checkable=True,
                                     triggered=lambda: e.toggle_mark("smallcaps"))
        self.act_sub = QAction(icons.subscript(), "Subs&cript", self, checkable=True,
                               triggered=lambda: e.toggle_mark("subscript"))
        self.act_super = QAction(icons.superscript(), "Su&perscript", self, checkable=True,
                                 triggered=lambda: e.toggle_mark("superscript"))

        # Headings
        self.heading_group = QActionGroup(self)
        self.heading_group.setExclusive(True)
        self.act_h_body = QAction("Body text", self, checkable=True,
                                  triggered=lambda: e.apply_heading(0))
        self.heading_group.addAction(self.act_h_body)
        self.heading_actions: list[QAction] = []
        for level in range(1, 6):
            a = QAction(icons.heading(level), f"Heading &{level}", self, checkable=True,
                        triggered=lambda checked=False, l=level: e.apply_heading(l))
            self.heading_group.addAction(a)
            self.heading_actions.append(a)

        # Insert
        self.act_math_inline = QAction(icons.math_inline(), "Inline &math", self,
                                       shortcut=QKeySequence("Ctrl+M"),
                                       triggered=e.insert_inline_math)
        self.act_math_block = QAction(icons.math_block(), "Math &block", self,
                                      shortcut=QKeySequence("Ctrl+Shift+M"),
                                      triggered=e.insert_math_block)
        self.act_bullet = QAction(icons.bullet_list(), "Bullet &list", self,
                                  triggered=e.insert_bullet_list)
        self.act_numbered = QAction(icons.numbered_list(), "&Numbered list", self,
                                    triggered=e.insert_numbered_list)
        self.act_link = QAction(icons.link(), "&Hyperlink...", self,
                                shortcut=QKeySequence("Ctrl+K"),
                                triggered=self._insert_link_with_hyperref)
        self.act_footnote = QAction(icons.footnote(), "&Footnote...", self,
                                    triggered=e.insert_footnote)
        self.act_citation = QAction(icons.citation(), "&Citation...", self,
                                    triggered=e.insert_citation)
        self.act_crossref = QAction(icons.cross_ref(), "Cross-&reference...", self,
                                    triggered=e.insert_crossref)
        self.act_figure = QAction(icons.figure(), "F&igure...", self,
                                  triggered=e.insert_figure)
        self.act_table = QAction(icons.table(), "&Table...", self,
                                 triggered=e.insert_table)
        self.act_raw = QAction("Raw LaTeX...", self, triggered=e.insert_raw_latex)
        self.act_code_block = QAction("&Code block...", self,
                                      triggered=e.insert_code_block)
        self.act_symbol = QAction(icons.symbol(), "&Symbol...", self,
                                  shortcut=QKeySequence("Ctrl+Shift+S"),
                                  triggered=self._insert_symbol)
        self.act_equation_builder = QAction(
            icons.equation_builder(), "&Equation builder...", self,
            shortcut=QKeySequence("Ctrl+Shift+E"),
            triggered=self._insert_equation_template)
        # Quick-applies the corresponding paragraph style to the current
        # block. Same effect as picking it from the heading combo, but
        # surfaced in the Insert menu and toolbar so it's discoverable
        # for users who don't realise the combo has these entries.
        self.act_abstract = QAction("&Abstract paragraph", self,
                                    triggered=lambda: e.apply_heading(-3))
        self.act_keywords = QAction("Key&words paragraph", self,
                                    triggered=lambda: e.apply_heading(-4))
        self.act_pagebreak = QAction(icons.page_break(), "Page break", self,
                                     triggered=e.insert_page_break)
        self.act_hrule = QAction(icons.horizontal_rule(), "Horizontal rule", self,
                                 triggered=e.insert_horizontal_rule)
        self.act_multicol = QAction("&Multi-column region (2)...", self,
                                    triggered=e.insert_multicol_region)

        # View
        self.act_view_formatted = QAction("Show &Formatted tab", self,
                                          shortcut=QKeySequence("Ctrl+1"),
                                          triggered=lambda: self._tabs.setCurrentIndex(0))
        self.act_view_latex = QAction("Show &LaTeX tab", self,
                                      shortcut=QKeySequence("Ctrl+2"),
                                      triggered=lambda: self._tabs.setCurrentIndex(1))
        self.act_view_pdf = QAction("Show &PDF tab", self,
                                    shortcut=QKeySequence("Ctrl+3"),
                                    triggered=lambda: self._tabs.setCurrentIndex(2))
        self.act_side_by_side = QAction("PDF &side panel", self,
                                        shortcut=QKeySequence("Ctrl+4"),
                                        checkable=True, triggered=self._toggle_side_by_side)
        self.act_dark_theme = QAction("&Dark theme", self,
                                      checkable=True, triggered=self._toggle_theme)
        self.act_dark_theme.setChecked(
            self._settings.value("theme_dark", False, type=bool))
        # Spell-check toggle. Disabled (greyed out) when pyspellchecker
        # isn't installed so the user knows the feature exists even on
        # a stripped-down environment.
        from . import spellcheck
        self.act_spell_check = QAction(icons.spell_check(), "Check &spelling",
                                       self, checkable=True,
                                       triggered=self._toggle_spell_check)
        spell_available = spellcheck.is_available()
        self.act_spell_check.setEnabled(spell_available)
        wanted = self._settings.value("spell_check", spell_available, type=bool)
        # Apply persisted preference up front so the highlighter starts
        # in the right state (default ON when available).
        self.act_spell_check.setChecked(wanted and spell_available)
        self._editor.set_spell_check_enabled(wanted and spell_available)
        if spell_available:
            self.act_spell_check.setToolTip(
                "Underline misspelled English words in red. "
                "Toggle from the toolbar or View menu.")
        else:
            # Greyed-out menu entry, plus a one-shot status-bar
            # message so the user sees the install hint without
            # having to hunt for it in the menu.
            self.act_spell_check.setToolTip(
                "Install pyspellchecker to enable live spell checking:\n"
                "  pip install pyspellchecker")
            # Defer the status message so it fires after the status
            # bar exists; QTimer.singleShot(0) puts it on the event
            # queue after __init__ finishes.
            QTimer.singleShot(0, lambda: self._status.showMessage(
                "Spell check off — install pyspellchecker "
                "(pip install pyspellchecker) to enable it.", 10000))

        # Git
        self.act_commit_now = QAction(
            icons.commit(),
            "&Save snapshot and upload", self,
            statusTip="Save your work, create a version snapshot, and "
                      "upload it to the cloud (GitHub, GitLab, etc.)",
            triggered=self._commit_and_maybe_push)
        self.act_pull = QAction(
            "&Download latest from cloud", self,
            statusTip="Download the newest version of this document "
                      "from the cloud (e.g. if a collaborator made changes)",
            triggered=self._pull_from_remote)
        self.act_configure_remotes = QAction(
            "Connect to &GitHub / GitLab…", self,
            statusTip="Set up a cloud link so your document is backed up "
                      "online and can be shared with others",
            triggered=self._configure_remotes)
        self.act_history = QAction(
            icons.history(),
            "View &version history…", self,
            statusTip="Browse every saved snapshot of this document "
                      "and see what changed each time",
            triggered=self._show_history)

        # Help
        self.act_help_guide = QAction("&User guide", self,
                                      shortcut=QKeySequence("F1"),
                                      triggered=self._show_help_guide)
        self.act_shortcuts = QAction("&Keyboard shortcuts", self,
                                     triggered=self._show_shortcuts)
        self.act_about = QAction("&About kherveDOC", self, triggered=self._about)

    # ----- menus -----

    def _build_menus(self) -> None:
        mb = self.menuBar()

        m_file = mb.addMenu("&File")
        m_file.addAction(self.act_new)
        m_file.addAction(self.act_new_window)
        m_file.addAction(self.act_open)
        m_file.addAction(self.act_open_in_new_window)
        self._recent_menu = m_file.addMenu("Open &recent")
        self._refresh_recent_menu()
        m_file.addSeparator()
        m_file.addAction(self.act_save)
        m_file.addAction(self.act_save_as)
        m_file.addAction(self.act_close_doc)
        m_file.addSeparator()
        m_import = m_file.addMenu("&Import")
        m_import.addAction(self.act_import_tex)
        m_import.addAction(self.act_import_docx)
        m_export = m_file.addMenu("&Export")
        m_export.addAction(self.act_export_tex)
        m_export.addAction(self.act_export_pdf)
        m_file.addSeparator()
        m_file.addAction(self.act_doc_props)
        m_file.addSeparator()
        m_file.addAction(self.act_quit)

        m_edit = mb.addMenu("&Edit")
        m_edit.addAction(self.act_undo); m_edit.addAction(self.act_redo)
        m_edit.addSeparator()
        m_edit.addAction(self.act_cut); m_edit.addAction(self.act_copy)
        m_edit.addAction(self.act_paste); m_edit.addAction(self.act_select_all)
        m_edit.addSeparator()
        m_edit.addAction(self.act_find)
        m_edit.addSeparator()
        m_edit.addAction(self.act_clear_fmt)

        m_format = mb.addMenu("F&ormat")
        m_format.addAction(self.act_bold); m_format.addAction(self.act_italic)
        m_format.addAction(self.act_underline); m_format.addAction(self.act_strike)
        m_format.addAction(self.act_code); m_format.addAction(self.act_smallcaps)
        m_format.addAction(self.act_sub); m_format.addAction(self.act_super)
        m_format.addSeparator()
        m_align = m_format.addMenu("Alignment")
        m_align.addAction(self.act_align_left); m_align.addAction(self.act_align_center)
        m_align.addAction(self.act_align_right); m_align.addAction(self.act_align_justify)
        m_format.addSeparator()
        m_heading = m_format.addMenu("Paragraph style")
        m_heading.addAction(self.act_h_body)
        for a in self.heading_actions:
            m_heading.addAction(a)

        m_insert = mb.addMenu("&Insert")
        m_insert.addAction(self.act_math_inline); m_insert.addAction(self.act_math_block)
        m_insert.addAction(self.act_symbol); m_insert.addAction(self.act_equation_builder)
        m_insert.addSeparator()
        m_insert.addAction(self.act_abstract); m_insert.addAction(self.act_keywords)
        m_insert.addSeparator()
        m_insert.addAction(self.act_bullet); m_insert.addAction(self.act_numbered)
        m_insert.addSeparator()
        m_insert.addAction(self.act_link); m_insert.addAction(self.act_footnote)
        m_insert.addAction(self.act_citation); m_insert.addAction(self.act_crossref)
        m_insert.addSeparator()
        m_insert.addAction(self.act_figure); m_insert.addAction(self.act_table)
        m_insert.addSeparator()
        m_insert.addAction(self.act_pagebreak); m_insert.addAction(self.act_hrule)
        m_insert.addAction(self.act_multicol)
        m_insert.addAction(self.act_code_block)
        m_insert.addAction(self.act_raw)

        m_view = mb.addMenu("&View")
        m_view.addAction(self.act_view_formatted)
        m_view.addAction(self.act_view_latex)
        m_view.addAction(self.act_view_pdf)
        m_view.addSeparator()
        m_view.addAction(self.act_side_by_side)
        m_view.addSeparator()
        m_view.addAction(self.act_spell_check)
        m_view.addAction(self.act_dark_theme)

        m_git = mb.addMenu("&Git")
        m_git.addAction(self.act_commit_now)
        m_git.addAction(self.act_pull)
        m_git.addSeparator()
        m_git.addAction(self.act_configure_remotes)
        m_git.addSeparator()
        m_git.addAction(self.act_history)

        # Examples menu — each entry opens that example in a new window
        # so the user's current document isn't replaced.
        m_examples = mb.addMenu("E&xamples")
        for label, factory in examples.EXAMPLES:
            act = m_examples.addAction(label)
            act.triggered.connect(
                lambda checked=False, f=factory: self._open_example(f))

        # Window menu — populated dynamically with one entry per open
        # MainWindow so the user can flip between documents without
        # alt-tabbing. Refreshed on aboutToShow and whenever a window
        # opens / closes / changes title.
        self._window_menu = mb.addMenu("&Window")
        self._window_menu.aboutToShow.connect(self._refresh_window_menu)
        self._refresh_window_menu()

        m_help = mb.addMenu("&Help")
        m_help.addAction(self.act_help_guide)
        m_help.addAction(self.act_shortcuts)
        m_help.addSeparator()
        m_help.addAction(self.act_about)

    def _open_example(self, factory) -> None:
        """Spawn a new window and load the example into it. User-default
        meta fields (font / margins / page size) are layered on top so
        the example follows the same conventions as File > New."""
        doc = factory()
        doc.meta = _apply_user_defaults(doc.meta)
        win = self._new_window()
        win._editor.set_document(doc)
        win._kick_compile()

    def _refresh_window_menu(self) -> None:
        if not hasattr(self, "_window_menu"):
            return
        self._window_menu.clear()
        self._window_menu.addAction(self.act_new_window)
        self._window_menu.addAction(self.act_open_in_new_window)
        self._window_menu.addSeparator()
        for i, win in enumerate(MainWindow._windows):
            label = win.windowTitle() or f"Window {i + 1}"
            # Trim the "kherveDOC vX.Y.N+sha — " prefix when present so
            # the Window menu shows just the document name.
            marker = " — "
            if marker in label:
                label = label.split(marker, 1)[1]
            act = self._window_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(win is self)
            act.triggered.connect(lambda checked=False, w=win: (
                w.raise_(), w.activateWindow()))

    # ----- toolbar -----

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main toolbar", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction(self.act_new); tb.addAction(self.act_open)
        tb.addAction(self.act_save); tb.addAction(self.act_export_pdf)
        tb.addSeparator()
        tb.addAction(self.act_undo); tb.addAction(self.act_redo)
        tb.addSeparator()

        self._heading_combo = QComboBox(self)
        # Order matches Word's paragraph-style picker.
        self._heading_combo.addItem("Body text", 0)
        self._heading_combo.addItem("Title", -1)
        self._heading_combo.addItem("Author", -2)
        self._heading_combo.addItem("Abstract", -3)
        self._heading_combo.addItem("Keywords", -4)
        for level in range(1, 6):
            self._heading_combo.addItem(f"Heading {level}", level)
        self._heading_combo.setMinimumWidth(120)
        self._heading_combo.currentIndexChanged.connect(
            lambda idx: self._editor.apply_heading(self._heading_combo.itemData(idx)))
        tb.addWidget(self._heading_combo)

        # Narrow template combo — just the document-class shortcodes.
        self._template_combo = QComboBox(self)
        for cls in TEMPLATE_CHOICES:
            self._template_combo.addItem(cls, cls)
        self._template_combo.setMinimumWidth(90)
        self._template_combo.setMaximumWidth(110)
        self._template_combo.setToolTip("LaTeX document class")
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)
        tb.addWidget(self._template_combo)

        # Body-text font size — affects only the default body size; headings
        # keep their canonical sizes. Editable so users can type 11.5 etc.
        self._fontsize_combo = QComboBox(self)
        self._fontsize_combo.setEditable(True)
        for pt in (8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 24):
            self._fontsize_combo.addItem(str(pt), pt)
        self._fontsize_combo.setCurrentText("12")
        self._fontsize_combo.setMaximumWidth(60)
        self._fontsize_combo.setToolTip("Body text font size (pt)")
        self._fontsize_combo.lineEdit().editingFinished.connect(
            self._on_fontsize_changed)
        self._fontsize_combo.currentIndexChanged.connect(
            self._on_fontsize_changed)
        tb.addWidget(self._fontsize_combo)

        # Paper size combo (A4 / Letter / Legal).
        self._pagesize_combo = QComboBox(self)
        for p in page_sizes.ALL:
            self._pagesize_combo.addItem(p.code, p.code)
        self._pagesize_combo.setMinimumWidth(70)
        self._pagesize_combo.setMaximumWidth(90)
        self._pagesize_combo.setToolTip("Page size")
        self._pagesize_combo.currentIndexChanged.connect(self._on_pagesize_changed)
        tb.addWidget(self._pagesize_combo)
        tb.addSeparator()

        for act in (self.act_bold, self.act_italic, self.act_underline,
                    self.act_strike, self.act_code, self.act_smallcaps,
                    self.act_sub, self.act_super):
            tb.addAction(act)
        tb.addSeparator()
        for act in (self.act_align_left, self.act_align_center,
                    self.act_align_right, self.act_align_justify):
            tb.addAction(act)
        tb.addSeparator()
        for act in (self.act_bullet, self.act_numbered):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_spell_check)
        tb.addSeparator()
        tb.addAction(self.act_commit_now); tb.addAction(self.act_history)

        # Left vertical toolbar for Insert / layout actions.
        self._side_tb = QToolBar("Insert", self)
        self._side_tb.setMovable(False)
        self._side_tb.setOrientation(Qt.Vertical)
        self._side_tb.setIconSize(tb.iconSize())
        self.addToolBar(Qt.LeftToolBarArea, self._side_tb)

        self._side_tb.addAction(self.act_math_inline)
        self._side_tb.addAction(self.act_math_block)
        self._side_tb.addAction(self.act_symbol)
        self._side_tb.addAction(self.act_equation_builder)
        self._side_tb.addSeparator()
        self._side_tb.addAction(self.act_link)
        self._side_tb.addAction(self.act_footnote)
        self._side_tb.addAction(self.act_citation)
        self._side_tb.addAction(self.act_crossref)
        self._side_tb.addSeparator()
        self._side_tb.addAction(self.act_figure)
        self._side_tb.addAction(self.act_table)
        self._side_tb.addSeparator()
        self._side_tb.addAction(self.act_cols_1)
        self._side_tb.addAction(self.act_cols_2)
        self._side_tb.addAction(self.act_cols_3)
        self._side_tb.addSeparator()
        self._side_tb.addAction(self.act_pagebreak)
        self._side_tb.addAction(self.act_hrule)

    # ----- title -----

    def _update_title(self) -> None:
        name = self._current_path.name if self._current_path else "Untitled"
        self.setWindowTitle(f"kherveDOC {version_string()} — {name}")
        # Status bar shows "filename  —  full/parent/directory/" so the user
        # can identify the document at a glance and still see where it lives.
        if self._current_path is not None:
            parent = str(self._current_path.parent)
            self._path_label.setText(
                f"<b>{self._current_path.name}</b>  —  "
                f"<span style='color:#666'>{parent}</span>")
            self._path_label.setToolTip(str(self._current_path))
        else:
            self._path_label.setText(
                "<b>Untitled</b>  —  <span style='color:#888'>not saved yet</span>")
            self._path_label.setToolTip("")

    # ----- file actions -----

    def _new(self) -> None:
        self._current_path = None
        self._import_source_dir = None
        self._editor.set_document(_starter_document())
        self._update_title()

    def _new_window(self) -> MainWindow:
        """Open a fresh, empty MainWindow alongside this one. Returns the
        new window so callers (Open in new window...) can route a
        document into it."""
        win = MainWindow()
        win.show()
        return win

    def _open_in_new_window(self) -> None:
        path_s, _ = QFileDialog.getOpenFileName(
            self, "Open document in new window", "",
            "All supported (*.kdocz *.kdoc.json *.tex);;"
            "Bundled (*.kdocz);;JSON (*.kdoc.json);;LaTeX (*.tex);;All files (*)")
        if not path_s:
            return
        win = self._new_window()
        win._open_path(Path(path_s))

    def setWindowTitle(self, title: str) -> None:
        # Every title change should be reflected in the Window menus of
        # all sibling windows so the document list stays current as
        # users open / save / import documents.
        super().setWindowTitle(title)
        # Guard against early calls during __init__ (before the menu
        # exists) by checking the registry / attribute.
        for w in MainWindow._windows:
            w._refresh_window_menu()

    def closeEvent(self, event) -> None:
        self._settings.setValue("theme_dark", self._is_dark)
        self._settings.setValue("side_by_side", self._side_by_side)
        # Persist document-default preferences so new documents start
        # with the user's preferred font size, family, margins etc.
        meta = self._editor.meta()
        self._settings.setValue("default/body_font_pt", meta.body_font_pt)
        self._settings.setValue("default/body_font_family", meta.body_font_family)
        self._settings.setValue("default/line_spacing", meta.line_spacing)
        self._settings.setValue("default/paragraph_indent", meta.paragraph_indent)
        self._settings.setValue("default/margin_top_cm", meta.margin_top_cm)
        self._settings.setValue("default/margin_bottom_cm", meta.margin_bottom_cm)
        self._settings.setValue("default/margin_left_cm", meta.margin_left_cm)
        self._settings.setValue("default/margin_right_cm", meta.margin_right_cm)
        self._settings.setValue("default/page_size", meta.page_size)
        # Remove ourselves from the live-windows registry so the Window
        # menus on other windows refresh, and so the process can exit
        # once the last window closes (Qt does this automatically once
        # the last top-level QWidget is destroyed).
        try:
            MainWindow._windows.remove(self)
        except ValueError:
            pass
        # Refresh the Window menu on all surviving windows so this
        # document no longer appears in the list.
        for w in MainWindow._windows:
            w._refresh_window_menu()
        super().closeEvent(event)

    def _open(self) -> None:
        path_s, _ = QFileDialog.getOpenFileName(
            self, "Open document", "",
            "All supported (*.kdocz *.kdoc.json *.tex);;"
            "Bundled (*.kdocz);;JSON (*.kdoc.json);;LaTeX (*.tex);;All files (*)")
        if path_s:
            self._open_path(Path(path_s))

    def _open_path(self, path: Path) -> None:
        try:
            if kdocz.is_kdocz_path(path):
                doc, extract_dir = kdocz.load_kdocz(path)
                self._kdocz_extract_dir = extract_dir
            elif path.suffix.lower() == ".tex":
                # Import via the .tex parser; unknown commands become
                # RawLatex blocks rather than disappearing.
                doc = importers.import_tex(path.read_text(encoding="utf-8"))
                self._kdocz_extract_dir = None
            else:
                doc = from_json(path.read_text(encoding="utf-8"))
                self._kdocz_extract_dir = None
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._current_path = path
        self._import_source_dir = None  # current_path supersedes any prior import
        self._sync_editor_source_dir()
        self._editor.set_document(doc)
        self._update_title()
        self._remember_recent(path)

    def _save(self) -> None:
        if self._current_path is None:
            self._save_as()
        else:
            self._write_to(self._current_path)

    def _save_as(self) -> None:
        path_s, selected_filter = QFileDialog.getSaveFileName(
            self, "Save document", "document.kdocz",
            "Bundled kherveDOC (*.kdocz);;JSON kherveDOC (*.kdoc.json)")
        if not path_s: return
        path = Path(path_s)
        # If the user didn't type an extension, infer it from the chosen
        # filter. Default to the bundled format because it is self-contained
        # for documents with images.
        if path.suffix.lower() not in (".kdocz",) and not str(path).endswith(".kdoc.json"):
            if "kdoc.json" in selected_filter:
                path = path.with_name(path.stem + ".kdoc.json")
            else:
                path = path.with_suffix(".kdocz")
        self._current_path = path
        self._update_title()
        self._write_to(path)
        self._remember_recent(path)

    @staticmethod
    def _doc_stem(path: Path) -> str:
        """Return the document's base name, handling .kdoc.json correctly."""
        if path.name.endswith(".kdoc.json"):
            return path.name.replace(".kdoc.json", "")
        return path.stem

    def _write_to(self, path: Path) -> None:
        doc = self._editor.get_document()
        # Dispatch on the file extension: .kdocz is the bundled ZIP container,
        # .kdoc.json is the plain JSON model. The .tex export sits alongside
        # in both cases so users can inspect the source without unzipping.
        tex_basename = self._doc_stem(path)
        if kdocz.is_kdocz_path(path):
            kdocz.save_kdocz(doc, path)
        else:
            path.write_text(to_json(doc), encoding="utf-8")
        tex_path = path.parent / f"{tex_basename}.tex"
        tex_path.write_text(serialize_document(doc), encoding="utf-8")

        commit_msg = f"Save {path.name} at {datetime.now().isoformat(timespec='seconds')}"
        if git_backend.is_available():
            git_backend.init_repo(path.parent)
            oid = git_backend.commit_all(path.parent, commit_msg,
                                         file_stem=tex_basename)
            if oid:
                if git_backend.get_remotes(path.parent):
                    # Push on a background thread so a slow / dead
                    # remote can't freeze the editor for 30+ seconds
                    # every time the user hits Ctrl+S. The save itself
                    # already happened locally; the push status is
                    # reported asynchronously via _on_git_done.
                    self._status.showMessage(
                        "\u2714 Saved and snapshot created \u2014 uploading\u2026",
                        0)
                    self._start_git_worker("push", path.parent, "origin")
                else:
                    self._status.showMessage(
                        f"\u2714 Saved and snapshot created "
                        f"(use Git \u2192 Connect to GitHub to enable cloud backup)",
                        6000)
            else:
                self._status.showMessage(
                    "\u2714 Saved (nothing new to snapshot)", 4000)
        else:
            self._status.showMessage(
                "\u2714 Saved (install pygit2 to enable version history)", 5000)

    def _import_tex(self) -> None:
        path_s, _ = QFileDialog.getOpenFileName(
            self, "Import LaTeX", "", "LaTeX (*.tex);;All files (*)")
        if not path_s: return
        path = Path(path_s)
        try:
            doc = importers.import_tex(path.read_text(encoding="utf-8"))
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self._current_path = None
        # Remember where the .tex came from so relative \includegraphics
        # paths (e.g. Images/foo.png next to main.tex) resolve when we
        # compile the preview in a temp build dir.
        self._import_source_dir = path.parent
        self._sync_editor_source_dir()
        self._editor.set_document(doc)
        self.setWindowTitle(f"kherveDOC {version_string()} — {path.stem} (imported)")
        self._status.showMessage(f"Imported {path.name} — Save As to keep it", 6000)

    def _import_docx(self) -> None:
        if not importers.docx_available():
            QMessageBox.warning(
                self, "python-docx missing",
                "python-docx is not installed. Run "
                "<code>pip install python-docx</code> to enable .docx import.")
            return
        path_s, _ = QFileDialog.getOpenFileName(
            self, "Import Word document", "", "Word (*.docx);;All files (*)")
        if not path_s: return
        path = Path(path_s)
        # Embedded images get written next to the eventual save location.
        # Until the user picks one, drop them in the temp build dir.
        image_dir = self._build_dir / f"{path.stem}_images"
        try:
            doc = importers.import_docx(path, image_dir)
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self._current_path = None
        self._import_source_dir = None  # docx images are extracted into build_dir
        self._sync_editor_source_dir()
        self._editor.set_document(doc)
        self.setWindowTitle(f"kherveDOC {version_string()} — {path.stem} (imported)")
        n_imgs = len(list(image_dir.glob("image_*"))) if image_dir.exists() else 0
        self._status.showMessage(
            f"Imported {path.name} ({n_imgs} image(s) extracted to {image_dir})", 8000)

    def _export_tex(self) -> None:
        path_s, _ = QFileDialog.getSaveFileName(
            self, "Export LaTeX", "document.tex", "LaTeX (*.tex)")
        if path_s:
            Path(path_s).write_text(
                serialize_document(self._editor.get_document()), encoding="utf-8")

    def _export_pdf(self) -> None:
        if not tectonic_available():
            QMessageBox.warning(self, "tectonic missing",
                                "Install tectonic to export PDF.")
            return
        path_s, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "document.pdf", "PDF (*.pdf)")
        if not path_s: return
        source_dir = self._resolved_source_dir()
        result = compile_tex(serialize_document(self._editor.get_document()),
                             self._build_dir, source_dir=source_dir)
        if result.ok and result.pdf_path is not None:
            Path(path_s).write_bytes(result.pdf_path.read_bytes())
            self._status.showMessage(f"Exported {path_s}", 4000)
        else:
            QMessageBox.critical(self, "Compile failed",
                                 result.error or "Unknown error")

    def _edit_props(self) -> None:
        dlg = DocPropertiesDialog(self._editor.meta(), self)
        if dlg.exec() == QDialog.Accepted:
            self._editor.set_meta(dlg.result_meta())
            self._kick_compile()

    def _set_column_count(self, n: int) -> None:
        """Toolbar handler: update meta.column_count and re-preview.
        Skips the round-trip when the value hasn't actually changed
        (e.g. clicking the already-checked button)."""
        meta = self._editor.meta()
        if getattr(meta, "column_count", 1) == n:
            return
        meta.column_count = n
        self._editor.set_meta(meta)
        self._kick_compile()

    def _sync_column_toolbar(self) -> None:
        """Tick the toolbar button that matches meta.column_count. Called
        on doc load so opening a 2-column doc shows the 2-column button
        as checked without firing a redundant recompile."""
        n = int(getattr(self._editor.meta(), "column_count", 1) or 1)
        target = {1: self.act_cols_1, 2: self.act_cols_2,
                  3: self.act_cols_3}.get(n, self.act_cols_1)
        target.blockSignals(True)
        target.setChecked(True)
        target.blockSignals(False)

    def _on_template_changed(self, idx: int) -> None:
        cls = self._template_combo.itemData(idx)
        if not cls: return
        meta = self._editor.meta()
        if meta.documentclass == cls: return
        meta.documentclass = cls
        self._editor.set_meta(meta)
        self._kick_compile()

    def _on_zoom_slider_changed(self, pct: int) -> None:
        # Snap to 5%-multiples so drag movements feel less twitchy.
        snapped = max(25, min(300, 5 * round(pct / 5)))
        if snapped != pct:
            self._zoom_slider.blockSignals(True)
            self._zoom_slider.setValue(snapped)
            self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{snapped}%")
        self._editor.set_zoom_percent(snapped)

    def _nudge_zoom(self, delta: int) -> None:
        self._zoom_slider.setValue(self._zoom_slider.value() + delta)

    def _on_pdf_zoom_changed(self, pct: int) -> None:
        snapped = max(25, min(400, 5 * round(pct / 5)))
        if snapped != pct:
            self._pdf_zoom_slider.blockSignals(True)
            self._pdf_zoom_slider.setValue(snapped)
            self._pdf_zoom_slider.blockSignals(False)
        self._pdf_zoom_label.setText(f"{snapped}%")
        self._preview.set_zoom_percent(snapped)
        self._pdf_side_panel.set_zoom_percent(snapped)

    def _nudge_pdf_zoom(self, delta: int) -> None:
        self._pdf_zoom_slider.setValue(self._pdf_zoom_slider.value() + delta)

    def _on_tab_changed(self, index: int) -> None:
        self._update_zoom_visibility()

    def _update_zoom_visibility(self) -> None:
        tab = self._tabs.currentIndex()
        on_formatted = tab == 0
        on_pdf_tab = tab == 2
        show_editor_zoom = on_formatted
        show_pdf_zoom = on_pdf_tab or self._side_by_side
        self._zoom_out_btn.setVisible(show_editor_zoom)
        self._zoom_slider.setVisible(show_editor_zoom)
        self._zoom_in_btn.setVisible(show_editor_zoom)
        self._zoom_label.setVisible(show_editor_zoom)
        self._pdf_zoom_sep.setVisible(show_pdf_zoom)
        self._pdf_zoom_out_btn.setVisible(show_pdf_zoom)
        self._pdf_zoom_slider.setVisible(show_pdf_zoom)
        self._pdf_zoom_in_btn.setVisible(show_pdf_zoom)
        self._pdf_zoom_label.setVisible(show_pdf_zoom)

    # ----- find bar -----

    def _show_find_bar(self) -> None:
        self._find_bar.show()
        self._find_bar.field.setFocus()
        self._find_bar.field.selectAll()

    def _do_find(self, forward: bool = True) -> None:
        text = self._find_bar.field.text()
        if not text:
            return
        tab = self._tabs.currentIndex()
        if tab == 0:
            widget = self._editor.text_edit
        elif tab == 1:
            widget = self._latex_view._edit
        else:
            return
        flags = QTextDocument.FindFlags()
        if not forward:
            flags |= QTextDocument.FindBackward
        if self._find_bar.case_cb.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        found = widget.find(text, flags)
        if not found:
            # Wrap around: move cursor to start/end and retry once.
            cursor = widget.textCursor()
            if forward:
                cursor.movePosition(QTextCursor.Start)
            else:
                cursor.movePosition(QTextCursor.End)
            widget.setTextCursor(cursor)
            found = widget.find(text, flags)
        if found:
            widget.ensureCursorVisible()
            # In the Formatted tab the text edit sits inside an outer
            # QScrollArea ("desk").  ensureCursorVisible scrolls only the
            # QTextEdit's own viewport — we also need to scroll the outer
            # container so the matched line is on-screen.
            if tab == 0:
                cursor_rect = widget.cursorRect()
                global_pos = widget.mapTo(self._editor, cursor_rect.center())
                self._editor._scroll.ensureVisible(
                    global_pos.x(), global_pos.y(), 50, 80)
        else:
            self._status.showMessage(f'"{text}" not found', 3000)

    def _on_fontsize_changed(self, *_) -> None:
        try:
            pt = int(float(self._fontsize_combo.currentText().strip().rstrip("pt")))
        except (ValueError, TypeError):
            return
        self._editor.set_body_font_pt(pt)

    def _on_pagesize_changed(self, idx: int) -> None:
        code = self._pagesize_combo.itemData(idx)
        if not code: return
        if self._editor.meta().page_size == code: return
        self._editor.set_page_size(code)
        self._kick_compile()

    def _toggle_side_by_side(self, checked: bool) -> None:
        self._side_by_side = checked
        if checked:
            self._pdf_side_panel.show()
            self._kick_compile()
        else:
            self._pdf_side_panel.hide()
        self._update_zoom_visibility()

    def _refresh_icons(self) -> None:
        """Recreate every toolbar icon so colours match the active theme."""
        self.act_new.setIcon(icons.file_new())
        self.act_open.setIcon(icons.file_open())
        self.act_save.setIcon(icons.file_save())
        self.act_export_pdf.setIcon(icons.export_pdf())
        self.act_undo.setIcon(icons.undo())
        self.act_redo.setIcon(icons.redo())
        self.act_bold.setIcon(icons.bold())
        self.act_italic.setIcon(icons.italic())
        self.act_underline.setIcon(icons.underline())
        self.act_strike.setIcon(icons.strike())
        self.act_code.setIcon(icons.code())
        self.act_smallcaps.setIcon(icons.smallcaps())
        self.act_sub.setIcon(icons.subscript())
        self.act_super.setIcon(icons.superscript())
        self.act_align_left.setIcon(icons.align_left())
        self.act_align_center.setIcon(icons.align_center())
        self.act_align_right.setIcon(icons.align_right())
        self.act_align_justify.setIcon(icons.align_justify())
        self.act_cols_1.setIcon(icons.one_column())
        self.act_cols_2.setIcon(icons.two_columns())
        self.act_cols_3.setIcon(icons.three_columns())
        self.act_math_inline.setIcon(icons.math_inline())
        self.act_math_block.setIcon(icons.math_block())
        self.act_bullet.setIcon(icons.bullet_list())
        self.act_numbered.setIcon(icons.numbered_list())
        self.act_link.setIcon(icons.link())
        self.act_footnote.setIcon(icons.footnote())
        self.act_citation.setIcon(icons.citation())
        self.act_crossref.setIcon(icons.cross_ref())
        self.act_figure.setIcon(icons.figure())
        self.act_table.setIcon(icons.table())
        self.act_symbol.setIcon(icons.symbol())
        self.act_equation_builder.setIcon(icons.equation_builder())
        self.act_pagebreak.setIcon(icons.page_break())
        self.act_hrule.setIcon(icons.horizontal_rule())
        self.act_commit_now.setIcon(icons.commit())
        self.act_history.setIcon(icons.history())
        self.act_spell_check.setIcon(icons.spell_check())
        for i, a in enumerate(self.heading_actions, start=1):
            a.setIcon(icons.heading(i))
        self._zoom_out_btn.setIcon(icons.zoom_out())
        self._zoom_in_btn.setIcon(icons.zoom_in())
        self._pdf_zoom_out_btn.setIcon(icons.zoom_out())
        self._pdf_zoom_in_btn.setIcon(icons.zoom_in())

    def _toggle_spell_check(self, enabled: bool) -> None:
        self._editor.set_spell_check_enabled(enabled)
        self._settings.setValue("spell_check", enabled)

    def _toggle_theme(self, dark: bool) -> None:
        from .__main__ import apply_theme
        app = QApplication.instance()
        apply_theme(app, dark)
        self._settings.setValue("theme_dark", dark)
        icons.set_dark(dark)
        self._refresh_icons()
        self._latex_view.set_dark(dark)
        # Update the editor page styling for dark mode.
        if dark:
            self._editor.text_edit.setStyleSheet(
                "QTextEdit { background: #2d2d2d; color: #d4d4d4; border: none; }")
            page = self._editor.findChild(QWidget, "page")
            if page:
                page.setStyleSheet(
                    "#page { background: #2d2d2d; border: 1px solid #555; }")
            desk = self._editor.findChild(QWidget, "desk")
            if desk:
                desk.setStyleSheet("#desk { background: #1a1a1a; }")
        else:
            self._editor.text_edit.setStyleSheet(
                "QTextEdit { background: white; border: none; }")
            page = self._editor.findChild(QWidget, "page")
            if page:
                page.setStyleSheet(
                    "#page { background: white; border: 1px solid #b8bcc1; }")
            desk = self._editor.findChild(QWidget, "desk")
            if desk:
                desk.setStyleSheet("#desk { background: #d0d4d8; }")

    def _insert_symbol(self) -> None:
        # Lazy-create the palette once, then re-show on subsequent clicks.
        # Keeps it alongside the editor (Qt.Tool window) so users can
        # drop multiple symbols without closing/reopening every time.
        if not hasattr(self, "_symbol_window") or self._symbol_window is None:
            self._symbol_window = SymbolPickerWindow(self)
            self._symbol_window.symbolPicked.connect(self._dispatch_symbol_pick)
        self._symbol_window.show()
        self._symbol_window.raise_()
        self._symbol_window.activateWindow()

    def _dispatch_symbol_pick(self, latex: str) -> None:
        """Route a symbol-palette pick to math-inline or raw-inline insert
        based on the LaTeX command. Text-mode macros like \\Kstroke
        wouldn't render inside $...$, so they go in as InlineRaw."""
        if symbols.is_text_mode_symbol(latex):
            self._editor.insert_raw_inline_with(latex)
        else:
            self._editor.insert_inline_math_with(latex)

    def _insert_equation_template(self) -> None:
        """Open the floating equation-builder palette. Picks drop the
        template at the cursor — multi-line templates go in as math
        blocks; everything else as inline math."""
        if not hasattr(self, "_equation_window") or self._equation_window is None:
            self._equation_window = EquationBuilderWindow(self)
            self._equation_window.templatePicked.connect(self._apply_equation_template)
        self._equation_window.show()
        self._equation_window.raise_()
        self._equation_window.activateWindow()

    def _apply_equation_template(self, latex: str) -> None:
        # Templates that contain a \begin{...} get their own math block
        # (display math). Single-line templates are inserted inline.
        if "\\begin{" in latex:
            self._editor.insert_math_block_with(latex)
        else:
            self._editor.insert_inline_math_with(latex)

    def _insert_link_with_hyperref(self) -> None:
        # Ensure hyperref is in the package list before inserting.
        meta = self._editor.meta()
        if "hyperref" not in meta.packages:
            meta.packages.append("hyperref")
            self._editor.set_meta(meta)
        self._editor.insert_link()

    # ----- recent files -----

    def _remember_recent(self, path: Path) -> None:
        if path in self._recent:
            self._recent.remove(path)
        self._recent.insert(0, path)
        self._recent = self._recent[:_RECENT_FILES_MAX]
        self._settings.setValue("recent_files", [str(p) for p in self._recent])
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        if not hasattr(self, "_recent_menu"): return
        self._recent_menu.clear()
        if not self._recent:
            placeholder = QAction("(no recent files)", self)
            placeholder.setEnabled(False)
            self._recent_menu.addAction(placeholder)
            return
        for p in self._recent:
            a = QAction(str(p), self)
            a.triggered.connect(lambda checked=False, q=p: self._open_path(q))
            self._recent_menu.addAction(a)

    # ----- git -----

    def _commit_and_maybe_push(self) -> None:
        if self._current_path is None:
            QMessageBox.information(
                self, "Save snapshot",
                "You need to save your document first before a snapshot "
                "can be created.\n\n"
                "Use File \u2192 Save (Ctrl+S) to save it, then try again.")
            return
        self._write_to(self._current_path)

    def _start_git_worker(self, op: str, repo_dir: Path,
                          remote_name: str) -> None:
        """Spawn a _GitNetworkWorker for pull / push. Kept on
        self._git_worker so we can hold a reference (Qt threads get
        GC'd otherwise) and re-check it before starting another op."""
        worker = _GitNetworkWorker(op, repo_dir, remote_name)
        worker.finished_with.connect(self._on_git_done)
        self._git_worker = worker
        # Visual hint that something is happening — the status bar
        # message stays sticky (timeout 0) until _on_git_done clears
        # or replaces it.
        if op == "pull":
            self._status.showMessage(
                f"Downloading latest from {remote_name}…", 0)
        worker.start()

    def _on_git_done(self, op: str, ok: bool, msg: str) -> None:
        if op == "pull":
            if ok:
                if "up to date" in msg.lower():
                    self._status.showMessage(
                        "✔ Already up to date — you have the latest version",
                        5000)
                else:
                    self._status.showMessage(f"✔ {msg}", 6000)
                    self._reload_current()
            else:
                self._status.clearMessage()
                QMessageBox.warning(
                    self, "Download failed",
                    f"{msg}\n\n"
                    "What you can try:\n"
                    "  • Check your internet connection\n"
                    "  • Make sure the cloud URL is correct "
                    "(Git → Connect to GitHub)\n"
                    "  • If the problem says \"diverged\", ask a "
                    "colleague for help or use the git command line")
        elif op == "push":
            if ok:
                self._status.showMessage(
                    "✔ Saved, snapshot created, and uploaded to cloud", 5000)
            else:
                self._status.showMessage(
                    "✔ Saved and snapshot created "
                    "(⚠ upload failed — check your internet connection)", 6000)
        self._git_worker = None

    def _pull_from_remote(self) -> None:
        if self._current_path is None:
            QMessageBox.information(
                self, "Download latest",
                "You need to save your document first.\n\n"
                "Use File \u2192 Save (Ctrl+S), then try again.")
            return
        if not git_backend.is_available():
            QMessageBox.warning(
                self, "Download latest",
                "The pygit2 library is not installed, so cloud "
                "features are unavailable.\n\n"
                "To fix this, run:  pip install pygit2")
            return
        remotes = git_backend.get_remotes(self._current_path.parent)
        if not remotes:
            ask = QMessageBox.question(
                self, "Download latest",
                "This document is not connected to a cloud service yet.\n\n"
                "To download changes from a collaborator you first need to "
                "connect to GitHub, GitLab or another git server.\n\n"
                "Would you like to set that up now?")
            if ask == QMessageBox.Yes:
                self._configure_remotes()
            return
        if len(remotes) == 1:
            remote_name = remotes[0][0]
        else:
            names = [n for n, _ in remotes]
            chosen, ok = QInputDialog.getItem(
                self, "Download from\u2026",
                "Which cloud service?", names, 0, False)
            if not ok:
                return
            remote_name = chosen
        # Refuse to start a second network op while one is already
        # running \u2014 otherwise two threads race on the same repo and
        # libgit2 can crash.
        if getattr(self, "_git_worker", None) is not None and \
                self._git_worker.isRunning():
            self._status.showMessage(
                "A git operation is already in progress, please wait\u2026",
                4000)
            return
        self._start_git_worker("pull", self._current_path.parent, remote_name)

    def _configure_remotes(self) -> None:
        if self._current_path is None:
            QMessageBox.information(
                self, "Connect to cloud",
                "You need to save your document first so kherveDOC "
                "knows where to create the connection.\n\n"
                "Use File \u2192 Save (Ctrl+S), then try again.")
            return
        if not git_backend.is_available():
            QMessageBox.warning(
                self, "Connect to cloud",
                "The pygit2 library is not installed, so cloud "
                "features are unavailable.\n\n"
                "To fix this, run:  pip install pygit2")
            return
        from .remote_dialog import RemoteDialog
        dlg = RemoteDialog(self._current_path.parent, self)
        dlg.exec()

    def _reload_current(self) -> None:
        """Re-read the current document from disk after an external
        change (e.g. a successful pull). Best-effort: silently no-ops
        if the file has gone away."""
        if self._current_path is None or not self._current_path.exists():
            return
        try:
            self._open_path(self._current_path)
        except Exception as exc:
            self._status.showMessage(
                f"Reload after pull failed: {exc}", 6000)

    def _show_history(self) -> None:
        if self._current_path is None:
            QMessageBox.information(
                self, "Version history",
                "You need to save your document at least once before "
                "there is any history to show.\n\n"
                "Use File \u2192 Save (Ctrl+S), then try again.")
            return
        if not git_backend.is_available():
            QMessageBox.warning(
                self, "Version history",
                "The pygit2 library is not installed, so version "
                "history is unavailable.\n\n"
                "To fix this, run:  pip install pygit2")
            return
        if not git_backend.history_detailed(self._current_path.parent, limit=1):
            QMessageBox.information(
                self, "Version history",
                "No snapshots yet. Every time you save, kherveDOC "
                "automatically creates a snapshot.\n\n"
                "Save your document and come back here to see its history.")
            return
        from .history_dialog import HistoryDialog
        stem = self._doc_stem(self._current_path)
        dlg = HistoryDialog(self._current_path.parent, self,
                            file_stem=stem)
        dlg.exec()

    def _about(self) -> None:
        tec = "installed" if tectonic_available() else "not found"
        QMessageBox.about(
            self, "About kherveDOC",
            f"<h2>kherveDOC {version_string()}</h2>"
            f"<p>A WYSIWYG document editor that produces publication-quality "
            f"LaTeX output with built-in Git version control.</p>"
            f"<hr>"
            f"<p><b>Author:</b> Gwilherm Kerherv&eacute;<br>"
            f"Imperial College London<br>"
            f"<a href='mailto:g.kerherve@imperial.ac.uk'>g.kerherve@imperial.ac.uk</a></p>"
            f"<p><b>Source:</b> "
            f"<a href='https://github.com/gkerherve/kherveDOC'>"
            f"github.com/gkerherve/kherveDOC</a></p>"
            f"<hr>"
            f"<table cellpadding='2'>"
            f"<tr><td><b>Python</b></td><td>{__import__('sys').version.split()[0]}</td></tr>"
            f"<tr><td><b>PySide6</b></td><td>{__import__('PySide6').__version__}</td></tr>"
            f"<tr><td><b>tectonic</b></td><td>{tec}</td></tr>"
            f"</table>"
            f"<p style='color: #888; margin-top: 12px;'>"
            f"Built with PySide6, tectonic, PyMuPDF and pygit2.</p>")

    def _show_help_guide(self) -> None:
        from PySide6.QtWidgets import QTextBrowser
        dlg = QDialog(self)
        dlg.setWindowTitle("kherveDOC User Guide")
        dlg.resize(680, 560)
        tabs = QTabWidget(dlg)

        def _page(html: str) -> QTextBrowser:
            b = QTextBrowser()
            b.setOpenExternalLinks(True)
            b.setHtml(html)
            return b

        tabs.addTab(_page(
            "<h2>Getting started</h2>"
            "<p>kherveDOC is a document editor that looks and feels like a "
            "word processor but produces publication-quality LaTeX output. "
            "Every document is stored as a structured model and can be "
            "compiled to PDF in real time.</p>"

            "<h3>The three tabs</h3>"
            "<ul>"
            "<li><b>Formatted</b> &mdash; WYSIWYG editor. Type, format text, "
            "insert figures and equations just like in a word processor.</li>"
            "<li><b>LaTeX</b> &mdash; Raw LaTeX source with syntax highlighting "
            "and autocomplete. Edits here are parsed back into the Formatted "
            "tab automatically.</li>"
            "<li><b>PDF</b> &mdash; Live preview of the compiled document "
            "(requires <i>tectonic</i>).</li>"
            "</ul>"

            "<h3>Side-by-side mode</h3>"
            "<p>Press <code>Ctrl+4</code> or use <b>View &gt; PDF side panel</b> "
            "to split the window: edit on the left, preview PDF on the right.</p>"

            "<h3>Zoom controls</h3>"
            "<p>Two independent zoom sliders sit in the status bar at the bottom. "
            "The editor zoom appears on the Formatted tab; the PDF zoom appears "
            "on the PDF tab (and whenever the side panel is open).</p>"
        ), "Getting started")

        tabs.addTab(_page(
            "<h2>Formatting</h2>"
            "<h3>Text styles</h3>"
            "<p>Select text and use the toolbar or shortcuts:</p>"
            "<table cellpadding='4'>"
            "<tr><td><code>Ctrl+B</code></td><td>Bold</td></tr>"
            "<tr><td><code>Ctrl+I</code></td><td>Italic</td></tr>"
            "<tr><td><code>Ctrl+U</code></td><td>Underline</td></tr>"
            "</table>"
            "<p>Additional styles (strikethrough, small caps, code, sub/superscript) "
            "are available in the toolbar and the <b>Format</b> menu.</p>"

            "<h3>Paragraph styles</h3>"
            "<p>Use the <b>Paragraph Style</b> dropdown in the toolbar to set "
            "the current paragraph to Body text, Title, Author, Abstract, "
            "Keywords, or Heading 1&ndash;5.</p>"

            "<h3>Alignment &amp; columns</h3>"
            "<p>Four alignment buttons (left, centre, right, justify) and "
            "three column buttons (1, 2, 3 columns) control document layout. "
            "These apply to the whole document.</p>"

            "<h3>Lists</h3>"
            "<p>Click the bullet or numbered list button to start a list. "
            "Use <code>Tab</code> to increase nesting and "
            "<code>Shift+Tab</code> to decrease it.</p>"
        ), "Formatting")

        tabs.addTab(_page(
            "<h2>Inserting content</h2>"

            "<h3>Mathematics</h3>"
            "<p><b>Inline math</b> (<code>Ctrl+M</code>): wrap selected text "
            "in <code>$...$</code> for inline equations.</p>"
            "<p><b>Math block</b> (<code>Ctrl+Shift+M</code>): insert a "
            "numbered display equation.</p>"
            "<p><b>Equation builder</b> (<code>Ctrl+Shift+E</code>): pick from "
            "templates (fractions, integrals, matrices, sums, etc.).</p>"
            "<p><b>Symbol picker</b> (<code>Ctrl+Shift+S</code>): browse Greek "
            "letters, operators, arrows and other symbols.</p>"

            "<h3>Figures &amp; tables</h3>"
            "<p>Use <b>Insert &gt; Figure</b> to add an image. The path is "
            "resolved relative to the document folder. A thumbnail preview "
            "appears in the Formatted tab.</p>"
            "<p><b>Insert &gt; Table</b> opens a dialog for rows, columns, "
            "caption and alignment.</p>"

            "<h3>References</h3>"
            "<p><b>Hyperlink</b> (<code>Ctrl+K</code>): attach a URL to "
            "selected text.</p>"
            "<p><b>Footnote</b>, <b>Citation</b> and <b>Cross-reference</b> "
            "are available from the Insert menu and toolbar.</p>"

            "<h3>Other elements</h3>"
            "<ul>"
            "<li><b>Code block</b> &mdash; monospaced, highlighted region</li>"
            "<li><b>Raw LaTeX</b> &mdash; arbitrary LaTeX preserved verbatim</li>"
            "<li><b>Page break</b> / <b>Horizontal rule</b></li>"
            "<li><b>Multi-column region</b> &mdash; local 2-column area "
            "inside a single-column document</li>"
            "</ul>"
        ), "Inserting content")

        tabs.addTab(_page(
            "<h2>Files &amp; formats</h2>"
            "<h3>Saving</h3>"
            "<p>kherveDOC saves in two native formats:</p>"
            "<ul>"
            "<li><b>.kdocz</b> &mdash; a ZIP archive containing the document "
            "model and all embedded images. Portable and self-contained.</li>"
            "<li><b>.kdoc.json</b> &mdash; plain-text JSON. Good for version "
            "control diffs.</li>"
            "</ul>"
            "<p>A <code>.tex</code> file is always written alongside the save "
            "so you can compile externally.</p>"

            "<h3>Importing</h3>"
            "<ul>"
            "<li><b>.tex</b> &mdash; LaTeX source is parsed into the document "
            "model. Unknown commands are preserved as Raw LaTeX blocks.</li>"
            "<li><b>.docx</b> &mdash; Word documents (requires "
            "<code>python-docx</code>). Embedded images are extracted next to "
            "the file.</li>"
            "</ul>"

            "<h3>Exporting</h3>"
            "<ul>"
            "<li><b>.tex</b> &mdash; standalone LaTeX source ready for any "
            "LaTeX compiler.</li>"
            "<li><b>.pdf</b> &mdash; compiled via tectonic.</li>"
            "</ul>"

            "<h3>Document properties</h3>"
            "<p>Open <b>File &gt; Document properties</b> to change:</p>"
            "<ul>"
            "<li><b>Metadata</b>: title, author, document class</li>"
            "<li><b>Text</b>: font family, font size, line spacing, "
            "first-line indent</li>"
            "<li><b>Layout</b>: page margins, column count</li>"
            "<li><b>Packages</b>: custom LaTeX packages</li>"
            "</ul>"
        ), "Files && formats")

        tabs.addTab(_page(
            "<h2>Version control</h2>"
            "<p>kherveDOC has built-in Git integration via "
            "<code>pygit2</code>.</p>"

            "<h3>Automatic commits</h3>"
            "<p>Every time you save, kherveDOC creates a Git commit in the "
            "document's folder. If a remote is configured, it pushes "
            "automatically. Commits use your global Git identity "
            "(name and email from <code>git config</code>).</p>"

            "<h3>Manual commit</h3>"
            "<p>Use <b>History &gt; Commit &amp; push now</b> in the toolbar "
            "or menu to force an immediate save, commit and push.</p>"

            "<h3>Browsing history</h3>"
            "<p><b>History &gt; Show commit history</b> opens a dialog listing "
            "every commit with date, SHA, message and author. Click a row "
            "to view the full diff with red/green syntax highlighting.</p>"

            "<p><i>Note:</i> If <code>pygit2</code> is not installed, "
            "documents still save normally but version history is unavailable.</p>"
        ), "Version control")

        tabs.addTab(_page(
            "<h2>LaTeX tab</h2>"
            "<p>The LaTeX tab gives you direct access to the document source "
            "with full syntax highlighting and autocomplete.</p>"

            "<h3>Syntax highlighting</h3>"
            "<p>Colour-coded backgrounds mark different environments:</p>"
            "<table cellpadding='4'>"
            "<tr><td style='background:#eef3ff; padding:4px 8px;'>"
            "Math (equation, align, gather&hellip;)</td></tr>"
            "<tr><td style='background:#e8f5e9; padding:4px 8px;'>"
            "Figures</td></tr>"
            "<tr><td style='background:#fff3e0; padding:4px 8px;'>"
            "Tables</td></tr>"
            "<tr><td style='background:#f5f5f7; padding:4px 8px;'>"
            "Lists (itemize, enumerate, description)</td></tr>"
            "<tr><td style='background:#fff5d6; padding:4px 8px;'>"
            "Abstract</td></tr>"
            "<tr><td style='background:#f3e5f5; padding:4px 8px;'>"
            "Bibliography</td></tr>"
            "<tr><td style='background:#eef2f7; padding:4px 8px;'>"
            "Code (verbatim, lstlisting, minted)</td></tr>"
            "<tr><td style='background:#e8f0fe; padding:4px 8px;'>"
            "Section headings</td></tr>"
            "</table>"
            "<p>Commands, braces, inline math and comments each have their "
            "own foreground colour.</p>"

            "<h3>Autocomplete</h3>"
            "<p>Type <code>\\</code> followed by at least one letter and a "
            "popup will suggest matching LaTeX commands. Press "
            "<code>Enter</code> or click to accept a suggestion.</p>"

            "<h3>Two-way editing</h3>"
            "<p>Changes in the LaTeX tab are parsed back into the Formatted "
            "tab after a short pause (1.5 s). Edits in the Formatted tab "
            "update the LaTeX source immediately.</p>"
        ), "LaTeX tab")

        layout = QVBoxLayout(dlg)
        layout.addWidget(tabs)
        dlg.exec()

    def _show_shortcuts(self) -> None:
        rows = [
            ("File", [
                ("Ctrl+N", "New document"),
                ("Ctrl+Shift+N", "New window"),
                ("Ctrl+O", "Open"),
                ("Ctrl+S", "Save"),
                ("Ctrl+Shift+S", "Save as"),
            ]),
            ("Edit", [
                ("Ctrl+Z", "Undo"),
                ("Ctrl+Y", "Redo"),
                ("Ctrl+X / C / V", "Cut / Copy / Paste"),
                ("Ctrl+A", "Select all"),
            ]),
            ("Formatting", [
                ("Ctrl+B", "Bold"),
                ("Ctrl+I", "Italic"),
                ("Ctrl+U", "Underline"),
            ]),
            ("Insert", [
                ("Ctrl+M", "Inline math"),
                ("Ctrl+Shift+M", "Math block"),
                ("Ctrl+K", "Hyperlink"),
                ("Ctrl+Shift+S", "Symbol picker"),
                ("Ctrl+Shift+E", "Equation builder"),
            ]),
            ("View", [
                ("Ctrl+1", "Formatted tab"),
                ("Ctrl+2", "LaTeX tab"),
                ("Ctrl+3", "PDF tab"),
                ("Ctrl+4", "PDF side panel"),
            ]),
        ]
        html = "<h3>Keyboard shortcuts</h3>"
        for group, shortcuts in rows:
            html += f"<h4 style='margin-bottom:2px; color:#1a3a8c;'>{group}</h4>"
            html += "<table cellpadding='3' style='margin-left:8px;'>"
            for key, desc in shortcuts:
                html += (f"<tr><td><code style='background:#eef3ff; "
                         f"padding:2px 6px; border-radius:3px;'>"
                         f"{key}</code></td>"
                         f"<td style='padding-left:12px;'>{desc}</td></tr>")
            html += "</table>"
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Keyboard shortcuts")
        dlg.setTextFormat(Qt.RichText)
        dlg.setText(html)
        dlg.exec()

    # ----- compile loop -----

    def _on_doc_changed(self) -> None:
        # When the change originated in the LaTeX tab itself we leave the
        # LaTeX view alone so we don't overwrite the user's typing with a
        # re-serialized version that may differ in whitespace/formatting.
        if not self._suppress_latex_update:
            self._latex_view.set_source(
                serialize_document(self._editor.get_document()))
        self._sync_toolbar_state()
        self._kick_compile()

    def _on_latex_edited(self, text: str) -> None:
        """User edited the LaTeX tab — reparse, replace the document
        model, and let the Formatted view + PDF rerender from it."""
        try:
            doc = importers.import_tex(text)
        except Exception as exc:
            self._status.showMessage(f"LaTeX parse error: {exc}", 5000)
            return
        self._suppress_latex_update = True
        try:
            self._editor.set_document(doc)
        finally:
            # The editor emits documentChanged on a debounce; release the
            # flag after the debounce window so the round-trip can finish
            # without overwriting the user's LaTeX.
            QTimer.singleShot(700,
                lambda: setattr(self, "_suppress_latex_update", False))
        self._kick_compile()

    def _resolved_source_dir(self) -> Path | None:
        """Where to look for relative asset paths (\\includegraphics etc.).
        Prefer the current saved-doc location; fall back to an imported
        .tex's original folder so its `Images/` directory resolves."""
        if self._current_path is not None:
            return self._current_path.parent
        return self._import_source_dir

    def _sync_editor_source_dir(self) -> None:
        self._editor.set_source_dir(self._resolved_source_dir())

    def _kick_compile(self) -> None:
        if not tectonic_available():
            self._preview.show_message(
                "tectonic not installed — install it to see a live preview.")
            return
        if self._compile_worker is not None and self._compile_worker.isRunning():
            self._pending_recompile = True
            return
        tex = serialize_document(self._editor.get_document())
        source_dir = self._resolved_source_dir()
        self._compile_worker = _CompileWorker(tex, self._build_dir, source_dir)
        self._compile_worker.finished_with.connect(self._on_compile_done)
        self._compile_worker.start()
        self._status.showMessage("Compiling...", 0)

    def _on_compile_done(self, result: CompileResult) -> None:
        self._status.clearMessage()
        if result.ok and result.pdf_path is not None:
            self._preview.show_pdf(result.pdf_path)
            if self._side_by_side:
                self._pdf_side_panel.show_pdf(result.pdf_path)
        else:
            tail = "\n".join(result.log.splitlines()[-10:]) if result.log else ""
            self._preview.show_message(f"{result.error}\n\n{tail}")
            if self._side_by_side:
                self._pdf_side_panel.show_message(f"{result.error}\n\n{tail}")
        self._compile_worker = None
        if self._pending_recompile:
            self._pending_recompile = False
            self._kick_compile()

    # ----- toolbar state sync -----

    def _sync_toolbar_state(self) -> None:
        e = self._editor
        self.act_bold.setChecked(e.is_mark_active("bold"))
        self.act_italic.setChecked(e.is_mark_active("italic"))
        self.act_underline.setChecked(e.is_mark_active("underline"))
        self.act_strike.setChecked(e.is_mark_active("strikethrough"))
        self.act_code.setChecked(e.is_mark_active("code"))
        self.act_smallcaps.setChecked(e.is_mark_active("smallcaps"))
        self.act_sub.setChecked(e.is_mark_active("subscript"))
        self.act_super.setChecked(e.is_mark_active("superscript"))
        align = e.current_alignment()
        align_actions = {
            "left": self.act_align_left, "center": self.act_align_center,
            "right": self.act_align_right, "justify": self.act_align_justify,
        }
        align_actions.get(align, self.act_align_left).setChecked(True)
        self._sync_column_toolbar()
        level = e.current_heading_level()
        # heading_combo indices: 0=Body, 1=Title, 2=Author, 3=Abstract,
        # 4=Keywords, 5..9=Heading 1..5
        if level == -1: idx = 1
        elif level == -2: idx = 2
        elif level == -3: idx = 3
        elif level == -4: idx = 4
        elif 1 <= level <= 5: idx = level + 4
        elif level == 0: idx = 0
        else: idx = 0
        if self._heading_combo.currentIndex() != idx:
            self._heading_combo.blockSignals(True)
            self._heading_combo.setCurrentIndex(idx)
            self._heading_combo.blockSignals(False)
        # Heading radio group (only tracks body/headings 1..5)
        if level == 0:
            self.act_h_body.setChecked(True)
        elif 1 <= level <= 5:
            self.heading_actions[level - 1].setChecked(True)

        # Keep the template combo in sync with the document class.
        meta_cls = e.meta().documentclass
        cur = self._template_combo.currentData()
        if cur != meta_cls:
            tidx = self._template_combo.findData(meta_cls)
            if tidx < 0:
                self._template_combo.addItem(meta_cls, meta_cls)
                tidx = self._template_combo.count() - 1
            self._template_combo.blockSignals(True)
            self._template_combo.setCurrentIndex(tidx)
            self._template_combo.blockSignals(False)

        meta_page = e.meta().page_size
        pcur = self._pagesize_combo.currentData()
        if pcur != meta_page:
            pidx = self._pagesize_combo.findData(meta_page)
            if pidx >= 0:
                self._pagesize_combo.blockSignals(True)
                self._pagesize_combo.setCurrentIndex(pidx)
                self._pagesize_combo.blockSignals(False)


def _apply_user_defaults(meta: DocMeta) -> DocMeta:
    """Overlay the user's persisted Document-defaults preferences onto a
    DocMeta produced by an example factory. Lets the welcome tour and
    every Examples-menu doc respect the same font / margin / spacing
    choices the user set under Document properties."""
    s = QSettings("kherveDOC", "kherveDOC")
    meta.body_font_pt = int(s.value("default/body_font_pt", meta.body_font_pt,
                                    type=int))
    meta.body_font_family = str(s.value("default/body_font_family",
                                        meta.body_font_family))
    meta.line_spacing = float(s.value("default/line_spacing", meta.line_spacing,
                                      type=float))
    meta.paragraph_indent = bool(s.value("default/paragraph_indent",
                                         meta.paragraph_indent, type=bool))
    meta.margin_top_cm = float(s.value("default/margin_top_cm",
                                       meta.margin_top_cm, type=float))
    meta.margin_bottom_cm = float(s.value("default/margin_bottom_cm",
                                          meta.margin_bottom_cm, type=float))
    meta.margin_left_cm = float(s.value("default/margin_left_cm",
                                        meta.margin_left_cm, type=float))
    meta.margin_right_cm = float(s.value("default/margin_right_cm",
                                         meta.margin_right_cm, type=float))
    meta.page_size = str(s.value("default/page_size", meta.page_size))
    return meta


def _starter_document() -> Document:
    """First-launch / File>New document — a multi-page welcome tour so
    users see what kherveDOC can do before they have to type anything."""
    doc = examples.welcome()
    doc.meta = _apply_user_defaults(doc.meta)
    return doc
