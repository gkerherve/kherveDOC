"""Main window: tabbed interface (Formatted | LaTeX | PDF) with full menus."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QSize, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction, QActionGroup, QGuiApplication, QIcon, QKeySequence, QPixmap,
    QTextCursor, QTextDocument,
)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSlider, QSpinBox, QSplitter, QStackedWidget, QStatusBar, QTabWidget,
    QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from . import (
    __version__, equations, git_backend, icons, kdocz, page_sizes,
    symbols, themes, version_string,
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
                 source_dir: Path | None = None,
                 skip_images: bool = False):
        super().__init__()
        self._tex = tex_source
        self._workdir = workdir
        self._source_dir = source_dir
        self._skip_images = skip_images

    def run(self) -> None:
        self.finished_with.emit(
            compile_tex(self._tex, self._workdir,
                        source_dir=self._source_dir,
                        skip_images=self._skip_images))


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
                ok, msg = git_backend.push(self._repo_dir, self._remote)
            else:
                ok, msg = False, f"Unknown git op: {self._op!r}"
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"{self._op} crashed: {exc}"
        self.finished_with.emit(self._op, ok, msg)


def _first_text_snippet(page, max_chars: int = 24) -> str:
    """Return the first chunk of meaningful text on a pymupdf page,
    used as the anchor for the editor's page-break overlay. We skip
    leading whitespace, the running header / page-number line if it
    sits on its own at the top, and stop after `max_chars` so the
    snippet is short enough to survive small LaTeX-vs-Qt rendering
    differences (hyphenation, whitespace, etc.) while still being
    unique enough to find unambiguously in the editor."""
    try:
        blocks = page.get_text("blocks") or []
    except Exception:
        return ""
    # Sort top-to-bottom in case pymupdf returned them in another order.
    blocks.sort(key=lambda b: (round(b[1], 1), round(b[0], 1)))
    for b in blocks:
        text = (b[4] if len(b) > 4 else "").strip()
        if not text:
            continue
        # Page numbers sit in their own block and are usually just
        # digits — ignore those so the snippet picks up real text.
        if text.replace(".", "").isdigit():
            continue
        # Collapse internal whitespace so the snippet matches what
        # the editor stores in its QTextBlocks.
        flat = " ".join(text.split())
        if len(flat) < 3:
            continue
        return flat[:max_chars]
    return ""


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
        self._docclass.addItems([
            "article", "report", "book", "letter", "beamer", "memoir",
            "elsarticle", "IEEEtran", "revtex4-2", "achemso",
            "amsart", "llncs", "acmart",
        ])
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
            "geometry / setspace are added automatically by KherveTeX."))
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


class _EquationLatexEdit(QPlainTextEdit):
    """LaTeX input field that intercepts Tab/Shift+Tab to navigate
    between \\square placeholders instead of inserting tab chars."""

    _PLACEHOLDER = r"\square"

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Tab and not ev.modifiers():
            self._jump_placeholder(forward=True)
            return
        if ev.key() == Qt.Key_Backtab or (
                ev.key() == Qt.Key_Tab
                and ev.modifiers() == Qt.ShiftModifier):
            self._jump_placeholder(forward=False)
            return
        super().keyPressEvent(ev)

    def _jump_placeholder(self, forward: bool) -> None:
        text = self.toPlainText()
        cursor = self.textCursor()
        pos = cursor.position()
        ph = self._PLACEHOLDER
        if forward:
            idx = text.find(ph, pos)
            if idx < 0:
                idx = text.find(ph)  # wrap around
        else:
            idx = text.rfind(ph, 0, pos)
            if idx < 0:
                idx = text.rfind(ph)  # wrap around
        if idx < 0:
            return
        cursor.setPosition(idx)
        cursor.setPosition(idx + len(ph), QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)


class EquationEditorDialog(QDialog):
    """Live-preview equation editor.

    Shows a rendered preview that updates as you type, a category
    toolbar with template buttons, and a LaTeX input field with
    Tab-navigable placeholders. Clicking Insert emits the final
    LaTeX for insertion into the document.
    """

    _CATEGORY_ICONS = [
        icons.eq_fractions, icons.eq_sums, icons.eq_integrals,
        icons.eq_scripts, icons.eq_derivatives, icons.eq_greek,
        icons.eq_vectors, icons.eq_brackets, icons.eq_relations,
        icons.eq_functions, icons.eq_environments,
    ]

    def __init__(self, parent: QWidget | None = None,
                 initial_latex: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Equation editor")
        self.resize(640, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ---- live preview ----
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setMinimumHeight(80)
        self._preview.setStyleSheet(
            "QLabel { background: white; border: 1px solid #ccc; "
            "border-radius: 4px; padding: 12px; }")
        self._preview.setText(
            "<span style='color:#999;'>Click a template to start "
            "building your equation</span>")
        root.addWidget(self._preview)

        # ---- category toolbar (2 rows x 5 cols) ----
        toolbar = QFrame()
        toolbar.setFrameShape(QFrame.StyledPanel)
        tb_grid = QGridLayout(toolbar)
        tb_grid.setSpacing(2)
        tb_grid.setContentsMargins(4, 4, 4, 4)
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        groups = equations.EQUATION_GROUPS
        cols = 6
        for idx, (group_name, _items) in enumerate(groups):
            btn = QToolButton()
            btn.setCheckable(True)
            icon_fn = (self._CATEGORY_ICONS[idx]
                       if idx < len(self._CATEGORY_ICONS)
                       else icons.eq_fractions)
            btn.setIcon(icon_fn())
            btn.setIconSize(QSize(24, 24))
            btn.setToolTip(group_name)
            btn.setFixedSize(40, 34)
            btn.setStyleSheet(
                "QToolButton { border: 1px solid transparent; "
                "border-radius: 3px; }"
                "QToolButton:checked { border: 1px solid #1a6dd8; "
                "background: #e0edfa; }")
            self._btn_group.addButton(btn, idx)
            tb_grid.addWidget(btn, idx // cols, idx % cols)
        root.addWidget(toolbar)

        # ---- category label ----
        self._cat_label = QLabel()
        self._cat_label.setStyleSheet(
            "font-weight: bold; color: #444; padding: 2px 4px;")
        root.addWidget(self._cat_label)

        # ---- template panel (stacked, one page per category) ----
        self._stack = QStackedWidget()
        self._populated: set[int] = set()
        for _ in groups:
            page = QWidget()
            QVBoxLayout(page)
            self._stack.addWidget(page)
        self._stack.setMaximumHeight(160)
        root.addWidget(self._stack)

        self._btn_group.idClicked.connect(self._show_category)
        first = self._btn_group.button(0)
        if first:
            first.setChecked(True)
            self._show_category(0)

        # ---- LaTeX input field ----
        latex_label = QLabel("LaTeX source:")
        latex_label.setStyleSheet("color: #666; font-size: 9pt;")
        root.addWidget(latex_label)
        self._edit = _EquationLatexEdit()
        self._edit.setMaximumHeight(72)
        from PySide6.QtGui import QFont as _QFont
        mf = _QFont("Consolas"); mf.setStyleHint(_QFont.Monospace)
        mf.setPointSize(10)
        self._edit.setFont(mf)
        self._edit.setPlaceholderText(
            r"e.g.  \frac{x+1}{2} + \sqrt{y}")
        root.addWidget(self._edit)

        # ---- Insert / Cancel buttons ----
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText("Insert")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

        # ---- debounced live preview ----
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._update_preview)
        self._edit.textChanged.connect(self._preview_timer.start)

        # Seed with initial LaTeX if provided
        if initial_latex:
            self._edit.setPlainText(initial_latex)

    def latex(self) -> str:
        return self._edit.toPlainText().strip()

    # ---- category / template plumbing (reused from old builder) ----

    def _show_category(self, index: int) -> None:
        groups = equations.EQUATION_GROUPS
        if index < 0 or index >= len(groups):
            return
        group_name, items = groups[index]
        self._cat_label.setText(group_name)
        self._stack.setCurrentIndex(index)
        if index not in self._populated:
            self._populate_page(index, items)
            self._populated.add(index)

    def _populate_page(self, index: int, items: list) -> None:
        page = self._stack.widget(index)
        old_layout = page.layout()
        if old_layout:
            while old_layout.count():
                old_layout.takeAt(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(4)
        grid.setContentsMargins(4, 4, 4, 4)
        btn_cols = 5
        for i, (latex, preview_text) in enumerate(items):
            btn = QToolButton()
            btn.setToolTip(f"{preview_text}\n{latex}")
            pixmap = equations.render_template_preview(latex)
            if pixmap and not pixmap.isNull():
                btn.setIcon(QIcon(pixmap))
                pw, ph = pixmap.width(), pixmap.height()
                btn.setIconSize(QSize(min(pw, 100), min(ph, 50)))
                btn.setFixedSize(min(pw + 12, 112), min(ph + 8, 58))
            else:
                btn.setText(preview_text)
                btn.setFixedSize(80, 40)
            btn.setStyleSheet(
                "QToolButton { border: 1px solid #ccc; "
                "border-radius: 3px; padding: 2px; }"
                "QToolButton:hover { border: 1px solid #1a6dd8; "
                "background: #e8f0fa; }")
            btn.clicked.connect(
                lambda checked=False, tex=latex: self._insert_template(tex))
            grid.addWidget(btn, i // btn_cols, i % btn_cols)
        scroll.setWidget(inner)
        old_layout.addWidget(scroll)

    def _insert_template(self, latex: str) -> None:
        """Insert a template at the cursor, replacing the selected
        placeholder if one is selected."""
        cursor = self._edit.textCursor()
        cursor.insertText(latex)
        self._edit.setFocus()
        # Jump to first placeholder in what we just inserted
        self._edit._jump_placeholder(forward=True)

    def _update_preview(self) -> None:
        text = self._edit.toPlainText().strip()
        if not text:
            self._preview.setPixmap(QPixmap())
            self._preview.setText(
                "<span style='color:#999;'>Click a template to start "
                "building your equation</span>")
            return
        px = equations.render_live_preview(text)
        if px and not px.isNull():
            self._preview.setText("")
            self._preview.setPixmap(px)
        else:
            self._preview.setPixmap(QPixmap())
            self._preview.setText(
                f"<span style='color:#c00;'>Cannot render: check "
                f"LaTeX syntax</span>")


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

    def __init__(self, theme_name: str | None = None):
        super().__init__()
        MainWindow._windows.append(self)
        # Read persisted theme when not explicitly provided (e.g. new windows).
        if theme_name is None:
            s = QSettings("kherveDOC", "kherveDOC")
            theme_name = s.value("theme_name", "") or "Light"
        self._theme_name = theme_name
        self._theme = themes.THEMES.get(theme_name, themes.THEMES["Light"])
        self._current_path: Path | None = None
        # Imported (.tex/.docx) files don't get a "current path" — the user
        # has to Save As before KherveTeX knows where to save the .kdocz.
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
        # Default to ~80 % of the screen, capped, so the window starts
        # in a comfortable size rather than near-maximised. The user
        # can still drag-resize bigger if they want.
        w = min(1700, int(screen.width() * 0.80))
        h = min(900, int(screen.height() * 0.85))
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
        # Give the PDF side panel ~2× the width of the Formatted tab.
        # The PDF page renders at its native typeset size (small
        # text), so it benefits from the extra width far more than
        # the editor (where the page card can scroll horizontally if
        # needed but the wrapped editor lines stay readable at
        # narrower widths).
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 5)

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
        self._path_label.setStyleSheet(themes.status_label_stylesheet(self._theme))
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
        self._zoom_label.setStyleSheet(f"padding-right: 6px; color: {self._theme['status_text']};")
        self._status.addPermanentWidget(self._zoom_label)

        # PDF-specific zoom (separate from the editor zoom).
        self._pdf_zoom_sep = QLabel(" | PDF:", self)
        self._pdf_zoom_sep.setStyleSheet(f"color: {self._theme['text_muted']}; padding: 0 2px;")
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
        self._pdf_zoom_label.setStyleSheet(f"padding-right: 6px; color: {self._theme['status_text']};")
        self._status.addPermanentWidget(self._pdf_zoom_label)

        self._tectonic_label = QLabel(
            "tectonic: OK" if tectonic_available() else "tectonic: NOT FOUND — preview disabled",
            self)
        self._status.addPermanentWidget(self._tectonic_label)

        self._io_label = QLabel("", self)
        self._io_label.setStyleSheet(
            f"padding: 0 8px; color: {self._theme['status_text']};")
        self._status.addPermanentWidget(self._io_label)

        # Initially on Formatted tab — hide PDF zoom, show editor zoom.
        self._pdf_zoom_sep.hide()
        self._pdf_zoom_out_btn.hide()
        self._pdf_zoom_slider.hide()
        self._pdf_zoom_in_btn.hide()
        self._pdf_zoom_label.hide()

        # Set icon colors before building actions so they render correctly.
        self._is_dark = themes.is_dark(self._theme_name)
        icons.set_dark(self._is_dark)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()

        self._editor.documentChanged.connect(self._on_doc_changed)
        self._editor.text_edit.cursorPositionChanged.connect(self._sync_toolbar_state)
        self._editor.zoomChanged.connect(self._on_fit_zoom_changed)
        self._latex_view.latexEdited.connect(self._on_latex_edited)
        self._suppress_latex_update = False

        # Cross-tab "Show in …" context-menu actions
        self._editor._extra_context_actions = [
            ("Show in LaTeX", self._nav_formatted_to_latex),
            ("Show in PDF", self._nav_formatted_to_pdf),
        ]
        self._latex_view._extra_context_actions = [
            ("Show in Formatted", self._nav_latex_to_formatted),
            ("Show in PDF", self._nav_latex_to_pdf),
        ]
        self._preview._extra_context_actions = [
            ("Show in Formatted", self._nav_pdf_to_formatted),
            ("Show in LaTeX", self._nav_pdf_to_latex),
        ]
        self._pdf_side_panel._extra_context_actions = [
            ("Show in Formatted", self._nav_pdf_to_formatted),
            ("Show in LaTeX", self._nav_pdf_to_latex),
        ]

        # Apply the full named theme (tab styling, editor, latex view).
        self._apply_named_theme(self._theme_name, startup=True)

        # Restore side-by-side panel state.
        if self._settings.value("side_by_side", False, type=bool):
            self.act_side_by_side.setChecked(True)
            self._toggle_side_by_side(True)

        # Restore fit-page-width state (default: on).
        fit_w = self._settings.value("fit_page_width", True, type=bool)
        self.act_fit_page_width.setChecked(fit_w)
        self._toggle_fit_page_width(fit_w)

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
        self.act_import_md = QAction("Import .&md...", self, triggered=self._import_md)
        self.act_export_tex = QAction("Export .&tex...", self, triggered=self._export_tex)
        self.act_export_pdf = QAction(icons.export_pdf(), "Export .&pdf...", self,
                                      triggered=self._export_pdf)
        self.act_show_in_explorer = QAction(
            "Show in file e&xplorer", self,
            triggered=self._show_in_explorer)
        self.act_doc_props = QAction("Document &properties...", self,
                                     triggered=self._edit_props)
        self.act_manage_styles = QAction("Manage &styles…", self,
                                         triggered=self._manage_styles)
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
        self.act_drawing = QAction(icons.drawing(), "&Drawing…", self,
                                   triggered=e.insert_drawing)
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
        self.act_fit_page_width = QAction("&Fit page width", self,
                                          shortcut=QKeySequence("Ctrl+0"),
                                          checkable=True, checked=True,
                                          triggered=self._toggle_fit_page_width)
        self._theme_actions: dict[str, QAction] = {}
        self._theme_group = QActionGroup(self)
        for name in themes.THEME_NAMES:
            act = QAction(name, self, checkable=True)
            act.triggered.connect(
                lambda checked=False, n=name: self._apply_named_theme(n))
            self._theme_group.addAction(act)
            self._theme_actions[name] = act
            if name == self._theme_name:
                act.setChecked(True)
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
        self.act_branches = QAction(
            icons.branch(),
            "&Branches…", self,
            statusTip="View, create, switch or delete branches",
            triggered=self._show_branches)

        # Review
        self.act_highlight = QAction(
            icons.highlight(), "&Highlight", self,
            shortcut=QKeySequence("Ctrl+Shift+H"),
            statusTip="Highlight selected text",
            triggered=self._show_highlight_picker)
        self.act_remove_highlight = QAction(
            "Remove highlight", self,
            triggered=self._editor.remove_highlight)
        self.act_comment = QAction(
            icons.comment(), "New &comment", self,
            shortcut=QKeySequence("Ctrl+Alt+M"),
            statusTip="Add a reviewer comment to the selected text",
            triggered=self._insert_comment)
        self.act_accept_comment = QAction(
            icons.accept_change(), "&Accept", self,
            statusTip="Accept comment and keep the text",
            triggered=self._editor.accept_comment)
        self.act_reject_comment = QAction(
            icons.reject_change(), "&Reject", self,
            statusTip="Reject comment and delete the text",
            triggered=self._editor.reject_comment)
        self.act_prev_comment = QAction(
            icons.prev_comment(), "← &Previous comment", self,
            shortcut=QKeySequence("Ctrl+Shift+["),
            triggered=self._editor.prev_comment)
        self.act_next_comment = QAction(
            icons.next_comment(), "→ &Next comment", self,
            shortcut=QKeySequence("Ctrl+Shift+]"),
            triggered=self._editor.next_comment)

        # Compile
        self.act_compile_now = QAction(
            icons.compile_pdf(), "&Compile PDF", self,
            shortcut=QKeySequence("Ctrl+Shift+C"),
            statusTip="Compile the PDF now",
            triggered=self._kick_compile)
        self._auto_compile = True
        self.act_auto_compile = QAction(
            icons.auto_compile_on(), "Auto-compile", self,
            checkable=True, checked=True,
            statusTip="Toggle automatic PDF compilation on every edit",
            triggered=self._toggle_auto_compile)
        self._skip_images = False
        self.act_skip_images = QAction(
            icons.compile_no_images(), "Skip images", self,
            checkable=True, checked=False,
            statusTip="Compile without images for faster preview",
            triggered=self._toggle_skip_images)

        # Help
        self.act_help_guide = QAction("&User guide", self,
                                      shortcut=QKeySequence("F1"),
                                      triggered=self._show_help_guide)
        self.act_shortcuts = QAction("&Keyboard shortcuts", self,
                                     triggered=self._show_shortcuts)
        self.act_about = QAction("&About KherveTeX", self, triggered=self._about)

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
        m_import.addAction(self.act_import_md)
        m_export = m_file.addMenu("&Export")
        m_export.addAction(self.act_export_tex)
        m_export.addAction(self.act_export_pdf)
        m_file.addSeparator()
        m_file.addAction(self.act_show_in_explorer)
        m_file.addAction(self.act_doc_props)
        m_file.addAction(self.act_manage_styles)
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
        m_insert.addAction(self.act_drawing)
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
        m_view.addAction(self.act_fit_page_width)
        m_view.addSeparator()
        m_view.addAction(self.act_spell_check)
        m_theme = m_view.addMenu("&Theme")
        for name in themes.THEME_NAMES:
            m_theme.addAction(self._theme_actions[name])

        m_review = mb.addMenu("&Review")
        m_review.addAction(self.act_highlight)
        m_review.addAction(self.act_remove_highlight)
        m_review.addSeparator()
        m_review.addAction(self.act_comment)
        m_review.addAction(self.act_accept_comment)
        m_review.addAction(self.act_reject_comment)
        m_review.addSeparator()
        m_review.addAction(self.act_prev_comment)
        m_review.addAction(self.act_next_comment)

        m_git = mb.addMenu("&Git")
        m_git.addAction(self.act_commit_now)
        m_git.addAction(self.act_pull)
        m_git.addSeparator()
        m_git.addAction(self.act_history)
        m_git.addAction(self.act_branches)
        m_git.addSeparator()
        m_git.addAction(self.act_configure_remotes)

        # Examples menu — each entry opens that example in a new window
        # so the user's current document isn't replaced.
        m_examples = mb.addMenu("E&xamples")
        for label, factory in examples.EXAMPLES:
            act = m_examples.addAction(label)
            act.triggered.connect(
                lambda checked=False, f=factory: self._open_example(f))
        m_examples.addSeparator()
        m_journal = m_examples.addMenu("&Journal / publisher templates")
        for label, factory in examples.JOURNAL_EXAMPLES:
            act = m_journal.addAction(label)
            act.triggered.connect(
                lambda checked=False, f=factory: self._open_example(f))
        m_examples.addSeparator()
        self._custom_tpl_menu = m_examples.addMenu("&My templates")
        self._refresh_custom_templates_menu()
        act_save_tpl = m_examples.addAction("Save current as &template…")
        act_save_tpl.triggered.connect(self._save_as_template)

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

    # ---- custom templates ----

    @staticmethod
    def _templates_dir() -> Path:
        """User templates directory — sits next to QSettings data."""
        d = Path(QSettings("kherveDOC", "kherveDOC").fileName()).parent / "templates"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _refresh_custom_templates_menu(self) -> None:
        menu = self._custom_tpl_menu
        menu.clear()
        tpl_dir = self._templates_dir()
        templates = sorted(tpl_dir.glob("*.json"))
        if not templates:
            act = menu.addAction("(no saved templates)")
            act.setEnabled(False)
            return
        for path in templates:
            name = path.stem
            sub = menu.addMenu(name)
            act_open = sub.addAction("Open in new window")
            act_open.triggered.connect(
                lambda checked=False, p=path: self._open_custom_template(p))
            act_del = sub.addAction("Delete template")
            act_del.triggered.connect(
                lambda checked=False, p=path, n=name: self._delete_template(p, n))

    def _save_as_template(self) -> None:
        """Save the current document as a reusable template."""
        import json
        name, ok = QInputDialog.getText(
            self, "Save as template",
            "Template name:",
            text=self._editor.document().meta.title or "My template")
        if not ok or not name.strip():
            return
        name = name.strip()
        doc = self._editor.document()
        data = to_json(doc)
        path = self._templates_dir() / f"{name}.json"
        if path.exists():
            r = QMessageBox.question(
                self, "Overwrite?",
                f'A template named "{name}" already exists. Overwrite it?')
            if r != QMessageBox.Yes:
                return
        path.write_text(json.dumps(json.loads(data), indent=2),
                        encoding="utf-8")
        self._refresh_custom_templates_menu()
        self.statusBar().showMessage(f"Template saved: {name}", 4000)

    def _open_custom_template(self, path: Path) -> None:
        """Load a user-saved template into a new window."""
        import json
        try:
            raw = path.read_text(encoding="utf-8")
            doc = from_json(raw)
        except Exception as exc:
            QMessageBox.warning(self, "Template error",
                                f"Could not load template:\n{exc}")
            return
        doc.meta = _apply_user_defaults(doc.meta)
        win = self._new_window()
        win._editor.set_document(doc)
        win._kick_compile()

    def _delete_template(self, path: Path, name: str) -> None:
        r = QMessageBox.question(
            self, "Delete template?",
            f'Permanently delete the template "{name}"?')
        if r != QMessageBox.Yes:
            return
        path.unlink(missing_ok=True)
        self._refresh_custom_templates_menu()
        self.statusBar().showMessage(f"Template deleted: {name}", 4000)

    def _refresh_window_menu(self) -> None:
        if not hasattr(self, "_window_menu"):
            return
        self._window_menu.clear()
        self._window_menu.addAction(self.act_new_window)
        self._window_menu.addAction(self.act_open_in_new_window)
        self._window_menu.addSeparator()
        for i, win in enumerate(MainWindow._windows):
            label = win.windowTitle() or f"Window {i + 1}"
            # Trim the "KherveTeX vX.Y.N+sha — " prefix when present so
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
        self._heading_combo.addItem("Frame (slide)", -6)
        self._heading_combo.addItem("Chapter", -5)
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
        tb.addAction(self.act_highlight)
        tb.addAction(self.act_comment)
        tb.addAction(self.act_accept_comment)
        tb.addAction(self.act_reject_comment)
        tb.addSeparator()
        tb.addAction(self.act_commit_now); tb.addAction(self.act_history)

        # Right-aligned compile buttons: push them to the far right
        # with a stretching spacer widget.
        spacer = QWidget()
        sp = spacer.sizePolicy()
        sp.setHorizontalStretch(1)
        sp.setHorizontalPolicy(sp.Policy.Expanding)
        spacer.setSizePolicy(sp)
        tb.addWidget(spacer)
        tb.addAction(self.act_compile_now)
        tb.addAction(self.act_auto_compile)
        tb.addAction(self.act_skip_images)

        # Left vertical toolbar for Insert / layout actions. Matches
        # the top toolbar's 24px icon size for a consistent look.
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
        self._side_tb.addAction(self.act_drawing)
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
        branch_suffix = ""
        if self._current_path and git_backend.is_available():
            _br = git_backend.current_branch(self._current_path.parent)
            if _br:
                branch_suffix = f" [{_br}]"
        self.setWindowTitle(
            f"KherveTeX {version_string()} — {name}{branch_suffix}")
        # Status bar shows "filename  —  full/parent/directory/" so the user
        # can identify the document at a glance and still see where it lives.
        if self._current_path is not None:
            parent = str(self._current_path.parent)
            branch_tag = ""
            if branch_suffix:
                bname = branch_suffix.strip(" []")
                branch_tag = (
                    f"  <span style='background:#d0e8ff;color:#0a5090;"
                    f"padding:1px 5px;border-radius:3px;"
                    f"font-weight:bold;'>{bname}</span>")
            self._path_label.setText(
                f"<b>{self._current_path.name}</b>{branch_tag}  —  "
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
            "All supported (*.kdocz *.kdoc.json *.tex *.md *.markdown);;"
            "Bundled (*.kdocz);;JSON (*.kdoc.json);;LaTeX (*.tex);;"
            "Markdown (*.md *.markdown);;All files (*)")
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
        self._settings.setValue("theme_name", self._theme_name)
        self._settings.setValue("theme_dark", self._is_dark)
        self._settings.setValue("side_by_side", self._side_by_side)
        self._settings.setValue("fit_page_width", self._editor.fit_to_width())
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
            "All supported (*.kdocz *.kdoc.json *.tex *.md *.markdown);;"
            "Bundled (*.kdocz);;JSON (*.kdoc.json);;LaTeX (*.tex);;"
            "Markdown (*.md *.markdown);;All files (*)")
        if path_s:
            self._open_path(Path(path_s))

    def _open_path(self, path: Path) -> None:
        self._io_label.setText("Loading\u2026")
        self._io_label.repaint()
        try:
            if kdocz.is_kdocz_path(path):
                doc, extract_dir = kdocz.load_kdocz(path)
                self._kdocz_extract_dir = extract_dir
            elif path.suffix.lower() == ".tex":
                doc = importers.import_tex(path.read_text(encoding="utf-8"))
                self._kdocz_extract_dir = None
            elif path.suffix.lower() in (".md", ".markdown"):
                doc = importers.import_md(path.read_text(encoding="utf-8"))
                self._kdocz_extract_dir = None
            else:
                doc = from_json(path.read_text(encoding="utf-8"))
                self._kdocz_extract_dir = None
        except Exception as exc:
            self._io_label.setText("")
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._current_path = path
        self._import_source_dir = None  # current_path supersedes any prior import
        self._sync_editor_source_dir()
        self._editor.set_document_dir(path.parent)
        # Show the cached PDF instantly while recompilation runs in the background
        cached_pdf = path.parent / f"{self._doc_stem(path)}.pdf"
        if cached_pdf.exists():
            self._preview.show_pdf(cached_pdf)
            if self._side_by_side:
                self._pdf_side_panel.show_pdf(cached_pdf)
        self._editor.set_document(doc)
        self._update_title()
        self._remember_recent(path)
        self._io_label.setText("")

    def _save(self) -> None:
        if self._current_path is None:
            self._save_as()
        else:
            self._write_to(self._current_path)

    def _save_as(self) -> None:
        path_s, selected_filter = QFileDialog.getSaveFileName(
            self, "Save document", "document.kdocz",
            "Bundled KherveTeX (*.kdocz);;JSON KherveTeX (*.kdoc.json)")
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
        self._editor.set_document_dir(path.parent)
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
        self._io_label.setText("Saving\u2026")
        self._io_label.repaint()
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
        self._io_label.setText("")

        commit_msg = getattr(self, "_pending_commit_msg", None) or \
            f"Save {path.name} at {datetime.now().isoformat(timespec='seconds')}"
        self._pending_commit_msg = None
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

    def _show_in_explorer(self) -> None:
        if self._current_path is None:
            self._status.showMessage("Save the document first", 3000)
            return
        import subprocess, sys
        folder = str(self._current_path.parent)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(self._current_path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(self._current_path)])
        else:
            subprocess.Popen(["xdg-open", folder])

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
        self.setWindowTitle(f"KherveTeX {version_string()} — {path.stem} (imported)")
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
        self.setWindowTitle(f"KherveTeX {version_string()} — {path.stem} (imported)")
        n_imgs = len(list(image_dir.glob("image_*"))) if image_dir.exists() else 0
        self._status.showMessage(
            f"Imported {path.name} ({n_imgs} image(s) extracted to {image_dir})", 8000)

    def _import_md(self) -> None:
        path_s, _ = QFileDialog.getOpenFileName(
            self, "Import Markdown", "",
            "Markdown (*.md *.markdown);;All files (*)")
        if not path_s:
            return
        path = Path(path_s)
        try:
            doc = importers.import_md(path.read_text(encoding="utf-8"))
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self._current_path = None
        self._import_source_dir = path.parent
        self._sync_editor_source_dir()
        self._editor.set_document(doc)
        self.setWindowTitle(
            f"KherveTeX {version_string()} — {path.stem} (imported)")
        self._status.showMessage(
            f"Imported {path.name} — Save As to keep it", 6000)

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

    def _manage_styles(self) -> None:
        from .style_dialog import StyleDialog
        dlg = StyleDialog(self)
        dlg.exec()

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
        self._sync_chapter_enabled()
        self._kick_compile()

    def _sync_chapter_enabled(self) -> None:
        """Grey out Chapter / Frame entries in the heading combo when
        the current documentclass doesn't support them."""
        if not hasattr(self, "_heading_combo"):
            return
        from .editor import class_supports_chapter
        meta = self._editor.meta()
        chapter_ok = class_supports_chapter(meta.documentclass)
        frame_ok = (meta.documentclass or "").lower() == "beamer"
        model = self._heading_combo.model()
        for i in range(self._heading_combo.count()):
            data = self._heading_combo.itemData(i)
            item = model.item(i)
            if item is None:
                continue
            if data == -5:
                flags = item.flags()
                if chapter_ok:
                    item.setFlags(flags | Qt.ItemIsEnabled
                                        | Qt.ItemIsSelectable)
                    item.setToolTip("")
                else:
                    item.setFlags(flags & ~Qt.ItemIsEnabled
                                        & ~Qt.ItemIsSelectable)
                    item.setToolTip(
                        "Chapter is only available in the book, "
                        "report and memoir document classes — "
                        "the current class is "
                        f"{meta.documentclass!r}.")
            elif data == -6:
                flags = item.flags()
                if frame_ok:
                    item.setFlags(flags | Qt.ItemIsEnabled
                                        | Qt.ItemIsSelectable)
                    item.setToolTip("")
                else:
                    item.setFlags(flags & ~Qt.ItemIsEnabled
                                        & ~Qt.ItemIsSelectable)
                    item.setToolTip(
                        "Frame is only available in the beamer "
                        "document class — the current class is "
                        f"{meta.documentclass!r}.")

    def _on_zoom_slider_changed(self, pct: int) -> None:
        # Snap to 5%-multiples so drag movements feel less twitchy.
        snapped = max(25, min(300, 5 * round(pct / 5)))
        if snapped != pct:
            self._zoom_slider.blockSignals(True)
            self._zoom_slider.setValue(snapped)
            self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{snapped}%")
        # Manual slider drag disables fit-to-width.
        if self._editor.fit_to_width():
            self._editor.set_fit_to_width(False)
            self.act_fit_page_width.setChecked(False)
        self._editor.set_zoom_percent(snapped)

    def _nudge_zoom(self, delta: int) -> None:
        if self._editor.fit_to_width():
            self._editor.set_fit_to_width(False)
            self.act_fit_page_width.setChecked(False)
        self._zoom_slider.setValue(self._zoom_slider.value() + delta)

    def _on_pdf_zoom_changed(self, pct: int) -> None:
        snapped = max(25, min(400, 5 * round(pct / 5)))
        if snapped != pct:
            self._pdf_zoom_slider.blockSignals(True)
            self._pdf_zoom_slider.setValue(snapped)
            self._pdf_zoom_slider.blockSignals(False)
        self._pdf_zoom_label.setText(f"{snapped}%")
        # Manual slider drag disables fit-to-width for PDF.
        if self._preview.fit_to_width():
            self._preview.set_fit_to_width(False)
            self._pdf_side_panel.set_fit_to_width(False)
            self.act_fit_page_width.setChecked(False)
        self._preview.set_zoom_percent(snapped)
        self._pdf_side_panel.set_zoom_percent(snapped)

    def _nudge_pdf_zoom(self, delta: int) -> None:
        if self._preview.fit_to_width():
            self._preview.set_fit_to_width(False)
            self._pdf_side_panel.set_fit_to_width(False)
            self.act_fit_page_width.setChecked(False)
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
        if self._tabs.currentIndex() == 2:
            self._preview.show_find_bar()
            return
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

    def _toggle_fit_page_width(self, checked: bool) -> None:
        self._editor.set_fit_to_width(checked)
        self._preview.set_fit_to_width(checked)
        self._pdf_side_panel.set_fit_to_width(checked)

    def _on_fit_zoom_changed(self, pct: int) -> None:
        """Editor computed a new zoom via fit-to-width; sync the slider."""
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(pct)
        self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{pct}%")

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
        self.act_branches.setIcon(icons.branch())
        self.act_spell_check.setIcon(icons.spell_check())
        self.act_highlight.setIcon(icons.highlight())
        self.act_comment.setIcon(icons.comment())
        self.act_accept_comment.setIcon(icons.accept_change())
        self.act_reject_comment.setIcon(icons.reject_change())
        self.act_prev_comment.setIcon(icons.prev_comment())
        self.act_next_comment.setIcon(icons.next_comment())
        self.act_compile_now.setIcon(icons.compile_pdf())
        if self._auto_compile:
            self.act_auto_compile.setIcon(icons.auto_compile_on())
        else:
            self.act_auto_compile.setIcon(icons.auto_compile_off())
        for i, a in enumerate(self.heading_actions, start=1):
            a.setIcon(icons.heading(i))
        self._zoom_out_btn.setIcon(icons.zoom_out())
        self._zoom_in_btn.setIcon(icons.zoom_in())
        self._pdf_zoom_out_btn.setIcon(icons.zoom_out())
        self._pdf_zoom_in_btn.setIcon(icons.zoom_in())

    def _toggle_spell_check(self, enabled: bool) -> None:
        self._editor.set_spell_check_enabled(enabled)
        self._settings.setValue("spell_check", enabled)

    def _apply_named_theme(self, name: str, startup: bool = False) -> None:
        app = QApplication.instance()
        t = themes.apply_theme(app, name)
        self._theme_name = name
        self._theme = t
        dark = themes.is_dark(name)
        self._is_dark = dark

        self._settings.setValue("theme_name", name)
        self._settings.setValue("theme_dark", dark)

        # Tab styling
        self._tabs.setStyleSheet(themes.tab_stylesheet(t))

        # Icons
        icons.set_dark(dark)
        if not startup:
            self._refresh_icons()

        # LaTeX view
        self._latex_view.set_dark(dark)
        self._latex_view.setStyleSheet(themes.latex_view_stylesheet(t))

        # Editor page / desk
        self._editor.set_dark(dark)
        self._editor.text_edit.setStyleSheet(
            themes.editor_textedit_stylesheet(t))
        page = self._editor.findChild(QWidget, "page")
        if page:
            page.setStyleSheet(themes.editor_page_stylesheet(t))
        desk = self._editor.findChild(QWidget, "desk")
        if desk:
            desk.setStyleSheet(themes.editor_desk_stylesheet(t))

        # Status bar labels
        sl = themes.status_label_stylesheet(t)
        self._path_label.setStyleSheet(sl)
        self._zoom_label.setStyleSheet(
            f"padding-right: 6px; color: {t['status_text']};")
        self._pdf_zoom_sep.setStyleSheet(
            f"color: {t['text_muted']}; padding: 0 2px;")
        self._pdf_zoom_label.setStyleSheet(
            f"padding-right: 6px; color: {t['status_text']};")

        # Check the right radio in the theme menu
        act = self._theme_actions.get(name)
        if act and not act.isChecked():
            act.setChecked(True)

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
        """Open the live equation editor dialog."""
        dlg = EquationEditorDialog(self)
        if dlg.exec() == QDialog.Accepted:
            latex = dlg.latex()
            if latex:
                self._apply_equation_template(latex)

    def _apply_equation_template(self, latex: str) -> None:
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

    # ----- review -----

    def _show_highlight_picker(self) -> None:
        """Show a small popup with highlight colour choices."""
        from .model import HIGHLIGHT_COLORS
        menu = QMenu(self)
        for name, hexval in HIGHLIGHT_COLORS.items():
            act = menu.addAction(icons.highlight(hexval),
                                 name.capitalize())
            act.triggered.connect(
                lambda checked=False, c=name: self._editor.insert_highlight(c))
        menu.addSeparator()
        act_remove = menu.addAction("Remove highlight")
        act_remove.triggered.connect(self._editor.remove_highlight)
        # Show below the highlight toolbar button
        btn = self.findChild(QToolButton, "")
        pos = self.cursor().pos()
        menu.exec(pos)

    def _insert_comment(self) -> None:
        """Insert a comment, auto-filling the author from git config."""
        author = ""
        if git_backend.is_available() and self._current_path:
            try:
                import pygit2
                repo_dir = (git_backend._find_enclosing_repo(
                    self._current_path.parent) or self._current_path.parent)
                repo = pygit2.Repository(str(repo_dir))
                sig = repo.default_signature
                author = sig.name
            except Exception:
                pass
        self._editor.insert_comment(author=author)

    # ----- git -----

    def _commit_and_maybe_push(self) -> None:
        if self._current_path is None:
            QMessageBox.information(
                self, "Save snapshot",
                "You need to save your document first before a snapshot "
                "can be created.\n\n"
                "Use File \u2192 Save (Ctrl+S) to save it, then try again.")
            return
        # Show dialog for custom commit message
        default_msg = (f"Save {self._current_path.name} at "
                       f"{datetime.now().isoformat(timespec='seconds')}")
        msg, ok = QInputDialog.getText(
            self, "Commit message",
            "Describe what you changed:",
            text=default_msg)
        if not ok:
            return
        self._pending_commit_msg = msg.strip() or default_msg
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
                # Keep the brief status message, but also show a
                # dialog with the actual git error so the user can
                # act on it (most common: "Authentication failed").
                self._status.showMessage(
                    "✔ Saved and snapshot created "
                    "(⚠ upload failed — see dialog)", 8000)
                self._show_push_failure_dialog(msg)
        self._git_worker = None

    def _show_push_failure_dialog(self, error_msg: str) -> None:
        """Surface a real push failure with actionable advice. The
        most common cause on Windows is HTTPS authentication: GitHub
        stopped accepting passwords years ago, so the user needs a
        Personal Access Token stored via Windows Credential Manager
        (which the system `git` CLI talks to). If `git` isn't on
        PATH at all, that's a separate hint."""
        from . import git_backend
        hints = []
        if "Authentication" in error_msg or "authentication" in error_msg:
            hints.append(
                "GitHub no longer accepts your account password over "
                "HTTPS — you need a <b>Personal Access Token</b>.<br>"
                "&nbsp;&nbsp;1. Go to <a href='https://github.com/settings/tokens'>"
                "github.com/settings/tokens</a> → Generate new token (classic)"
                "<br>"
                "&nbsp;&nbsp;2. Tick the <code>repo</code> scope, generate, "
                "copy the token"
                "<br>"
                "&nbsp;&nbsp;3. Next time the editor asks for a password, "
                "paste the token instead of your password.")
        elif "not found" in error_msg.lower() or "404" in error_msg:
            hints.append(
                "GitHub says the repository does not exist. Check that "
                "the URL in <b>Git → Connect to GitHub</b> matches the "
                "one shown on the repo's GitHub page (Code → HTTPS).")
        elif "rejected" in error_msg.lower() or "non-fast-forward" in error_msg:
            hints.append(
                "Someone else (or another machine) pushed to this "
                "branch since you last pulled. Use "
                "<b>Git → Download latest from cloud</b> first, then "
                "save again.")
        if not git_backend._system_git_available():
            hints.append(
                "<i>Tip: install Git for Windows so the editor can use "
                "your Windows Credential Manager for HTTPS pushes — "
                "<a href='https://git-scm.com/download/win'>"
                "git-scm.com/download/win</a></i>")
        body = (f"<b>Could not upload to cloud.</b><br><br>"
                f"<code>{error_msg}</code>")
        if hints:
            body += "<br><br>" + "<br><br>".join(hints)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Upload failed")
        box.setTextFormat(Qt.RichText)
        box.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        box.setText(body)
        box.exec()

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
                "You need to save your document first so KherveTeX "
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
                "No snapshots yet. Every time you save, KherveTeX "
                "automatically creates a snapshot.\n\n"
                "Save your document and come back here to see its history.")
            return
        from .history_dialog import HistoryDialog
        stem = self._doc_stem(self._current_path)
        dlg = HistoryDialog(self._current_path.parent, self,
                            file_stem=stem)
        dlg.exec()

    def _show_branches(self) -> None:
        """Open the history dialog (which now includes branch management)
        without file_stem filtering so all branches are visible."""
        if self._current_path is None:
            QMessageBox.information(
                self, "Branches",
                "Save your document first so the repository exists.")
            return
        if not git_backend.is_available():
            QMessageBox.warning(
                self, "Branches",
                "The pygit2 library is not installed.\n\n"
                "To fix this, run:  pip install pygit2")
            return
        from .history_dialog import HistoryDialog
        dlg = HistoryDialog(self._current_path.parent, self)
        dlg.exec()

    def _about(self) -> None:
        """Rich About dialog: app + author bio + every library KherveTeX
        actually loads, each with a one-line description of why it's here."""
        from PySide6.QtWidgets import QTextBrowser

        def _ver(modname: str) -> str:
            try:
                mod = __import__(modname)
                return getattr(mod, "__version__", "") or "(unknown)"
            except Exception:
                return "not installed"

        py_ver = __import__("sys").version.split()[0]
        tec = "installed" if tectonic_available() else "not found"

        libraries = [
            ("PySide6", _ver("PySide6"),
             "Official Qt for Python bindings — the entire GUI "
             "(toolbar, tabs, the formatted-text widget, dialogs).",
             "https://doc.qt.io/qtforpython-6/"),
            ("PyMuPDF (fitz)", _ver("pymupdf"),
             "Page-level access to PDFs; used by the .docx import path "
             "to pull embedded images out of the archive.",
             "https://pymupdf.readthedocs.io/"),
            ("QtPdf / QtPdfWidgets", "ships with PySide6",
             "Renders the live PDF preview pane natively, so the right-"
             "hand tab shows real pages with shadows, not rasterised PNGs.",
             "https://doc.qt.io/qt-6/qtpdf-index.html"),
            ("pygit2", _ver("pygit2"),
             "libgit2 bindings — drives the auto-commit on Save, the "
             "history viewer and the push to GitHub.",
             "https://www.pygit2.org/"),
            ("python-docx", _ver("docx"),
             "Reads .docx files for the Word importer (paragraph styles "
             "→ headings, embedded images → Figure blocks).",
             "https://python-docx.readthedocs.io/"),
            ("pyspellchecker", _ver("spellchecker"),
             "Fast offline spell-check used by the as-you-type wavy-"
             "underline marker.",
             "https://pyspellchecker.readthedocs.io/"),
            ("matplotlib", _ver("matplotlib"),
             "Optional — used by the figure-insertion path when a user "
             "asks the editor to plot data instead of importing an image.",
             "https://matplotlib.org/"),
            ("tectonic", tec,
             "External LaTeX engine. Auto-downloads packages on first "
             "compile; produces the PDF shown in the preview pane and "
             "exported by File → Export → PDF.",
             "https://tectonic-typesetting.github.io/"),
        ]

        rows = []
        for name, ver, role, url in libraries:
            rows.append(
                "<tr>"
                f"<td valign='top' style='padding:6px 14px 6px 0'>"
                f"<b>{name}</b><br>"
                f"<span style='color:#666;font-size:9pt'>{ver}</span></td>"
                f"<td valign='top' style='padding:6px 0'>{role}<br>"
                f"<a href='{url}'>{url}</a></td>"
                "</tr>")
        lib_table = (
            "<table cellpadding='0' cellspacing='0' "
            "style='border-collapse:collapse'>"
            + "".join(rows) +
            "</table>")

        html = (
            f"<h2 style='margin-bottom:2pt'>KherveTeX {version_string()}</h2>"
            f"<p style='color:#555;margin-top:0'>A WYSIWYG document editor "
            f"that produces publication-quality LaTeX output with built-in "
            f"Git version control.</p>"
            f"<p><b>Source:</b> "
            f"<a href='https://github.com/gkerherve/KherveTeX'>"
            f"github.com/gkerherve/KherveTeX</a> &nbsp;·&nbsp; "
            f"<b>License:</b> MIT</p>"
            f"<hr>"
            f"<h3>About the author</h3>"
            f"<p><b>Gwilherm Kerherv&eacute;</b> &nbsp;—&nbsp; "
            f"Research Associate, Department of Materials, "
            f"<a href='https://www.imperial.ac.uk/materials/'>"
            f"Imperial College London</a>.</p>"
            f"<p>Works on surface analysis and X-ray Photoelectron "
            f"Spectroscopy (XPS), with a focus on materials for energy "
            f"storage and catalysis. Maintains a small constellation of "
            f"open-source tools for the XPS community, including "
            f"<a href='https://github.com/gkerherve/KherveFitting'>"
            f"KherveFitting</a> (peak fitting for XPS spectra) and "
            f"<a href='https://github.com/gkerherve/spe_reader'>"
            f"spe-xps-reader</a> (an open reader for PHI Instruments SPE "
            f"binary files). KherveTeX grew out of the same workflow — "
            f"writing papers and reports in LaTeX without leaving the "
            f"WYSIWYG comfort zone of Word.</p>"
            f"<p><a href='mailto:g.kerherve@imperial.ac.uk'>"
            f"g.kerherve@imperial.ac.uk</a></p>"
            f"<hr>"
            f"<h3>Libraries</h3>"
            f"<p style='color:#666;margin-bottom:6pt'>Python {py_ver}</p>"
            f"{lib_table}"
            f"<p style='color:#888;margin-top:14pt;font-size:9pt'>"
            f"Every toolbar icon is drawn at runtime with QPainter — no "
            f"binary image assets ship with the app. PDF compilation runs "
            f"in a background QThread so the editor stays responsive."
            f"</p>"
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("About KherveTeX")
        dlg.resize(680, 740)
        browser = QTextBrowser(dlg)
        browser.setOpenExternalLinks(True)
        browser.setHtml(html)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        layout = QVBoxLayout(dlg)
        layout.addWidget(browser, 1)
        layout.addWidget(buttons)
        dlg.exec()

    def _show_help_guide(self) -> None:
        from PySide6.QtWidgets import QTextBrowser
        dlg = QDialog(self)
        dlg.setWindowTitle("KherveTeX User Guide")
        dlg.resize(680, 560)
        tabs = QTabWidget(dlg)

        def _page(html: str) -> QTextBrowser:
            b = QTextBrowser()
            b.setOpenExternalLinks(True)
            b.setHtml(html)
            return b

        tabs.addTab(_page(
            "<h2>Getting started</h2>"
            "<p>KherveTeX is a document editor that looks and feels like a "
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
            "<p><b>Equation builder</b> (<code>Ctrl+Shift+E</code>): an "
            "interactive editor with live preview. Click templates "
            "(fractions, integrals, matrices, sums, brackets, etc.) to "
            "build equations visually, use Tab to jump between "
            "placeholders, and see the rendered result in real time.</p>"
            "<p><b>Symbol picker</b> (<code>Ctrl+Shift+S</code>): browse Greek "
            "letters, operators, arrows and other symbols.</p>"

            "<h3>Figures &amp; tables</h3>"
            "<p>Use <b>Insert &gt; Figure</b> to add an image. The path is "
            "resolved relative to the document folder. A thumbnail preview "
            "appears in the Formatted tab.</p>"
            "<p><b>Insert &gt; Table</b> opens a dialog for rows, columns, "
            "caption and alignment.</p>"

            "<h3>Drawing tool</h3>"
            "<p><b>Insert &gt; Drawing</b> opens a canvas where you can "
            "sketch diagrams with multiple tools:</p>"
            "<ul>"
            "<li><b>Select</b> &mdash; click items to select them, drag to "
            "reposition</li>"
            "<li><b>Pen</b> &mdash; freehand drawing</li>"
            "<li><b>Line / Rectangle / Ellipse / Arrow</b> &mdash; "
            "geometric shapes</li>"
            "<li><b>Text</b> &mdash; add text labels with configurable "
            "font size (8&ndash;72 pt)</li>"
            "<li><b>Eraser</b> &mdash; click any item to remove it</li>"
            "</ul>"
            "<p>The canvas shows a <b>grid</b> overlay for alignment "
            "(toggle with the <i># Grid</i> button). Enable <b>Snap</b> "
            "to lock shapes to grid intersections. The grid is not visible "
            "in the exported image.</p>"
            "<p><b>Re-editing:</b> double-click any drawing figure in the "
            "Formatted tab to reopen the drawing dialog with all original "
            "shapes intact for further editing.</p>"

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
            "<p>KherveTeX saves in two native formats:</p>"
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
            "<li><b>.md / .markdown</b> &mdash; Markdown files with support "
            "for headings, lists, code blocks, math, images and links.</li>"
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
            "<p>KherveTeX has built-in Git integration via "
            "<code>pygit2</code>.</p>"

            "<h3>Automatic commits</h3>"
            "<p>Every time you save, KherveTeX creates a Git commit in the "
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

        tabs.addTab(_page(
            "<h2>PDF &amp; navigation</h2>"

            "<h3>Cross-tab navigation</h3>"
            "<p>Right-click anywhere in the <b>Formatted</b>, <b>LaTeX</b>, "
            "or <b>PDF</b> tab to see <i>Show in&hellip;</i> actions that "
            "jump to the same location in another tab:</p>"
            "<ul>"
            "<li>Formatted &rarr; <i>Show in LaTeX</i>, "
            "<i>Show in PDF</i></li>"
            "<li>LaTeX &rarr; <i>Show in Formatted</i>, "
            "<i>Show in PDF</i></li>"
            "<li>PDF &rarr; <i>Show in Formatted</i>, "
            "<i>Show in LaTeX</i></li>"
            "</ul>"

            "<h3>PDF find bar</h3>"
            "<p>Press <code>Ctrl+F</code> while on the PDF tab to open a "
            "search bar. Type a query and press Enter or click the "
            "&#9650;/&#9660; buttons to step through matches. "
            "All matches are highlighted in blue.</p>"

            "<h3>Show in file explorer</h3>"
            "<p>Use <b>File &gt; Show in file explorer</b> to open the "
            "document's folder in your system file manager.</p>"

            "<h3>Status bar</h3>"
            "<p>The bottom bar shows (left to right):</p>"
            "<ul>"
            "<li>Document file path</li>"
            "<li>Editor zoom slider (Formatted tab)</li>"
            "<li>PDF zoom slider (PDF tab or side panel)</li>"
            "<li>Tectonic status (OK or NOT FOUND)</li>"
            "<li>Loading/Saving indicator during file I/O</li>"
            "</ul>"
        ), "PDF && navigation")

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
                ("Ctrl+F", "Find (text or PDF search)"),
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
        # Re-evaluate Chapter availability — importing a .tex (or
        # switching docclass via the LaTeX tab) may have changed
        # whether \chapter is allowed.
        self._sync_chapter_enabled()
        if self._auto_compile:
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
        if self._auto_compile:
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

    def _toggle_auto_compile(self, checked: bool) -> None:
        self._auto_compile = checked
        if checked:
            self.act_auto_compile.setIcon(icons.auto_compile_on())
            self.act_auto_compile.setToolTip("Auto-compile: ON (click to disable)")
            self._kick_compile()
        else:
            self.act_auto_compile.setIcon(icons.auto_compile_off())
            self.act_auto_compile.setToolTip("Auto-compile: OFF (click to enable)")

    def _toggle_skip_images(self, checked: bool) -> None:
        self._skip_images = checked
        tip = ("Skip images: ON — images replaced by placeholders"
               if checked else "Skip images: OFF — full compile with images")
        self.act_skip_images.setToolTip(tip)
        if self._auto_compile:
            self._kick_compile()

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
        self._compile_worker = _CompileWorker(
            tex, self._build_dir, source_dir,
            skip_images=self._skip_images)
        self._compile_worker.finished_with.connect(self._on_compile_done)
        self._compile_worker.start()
        self._status.showMessage("Compiling...", 0)

    def _on_compile_done(self, result: CompileResult) -> None:
        self._status.clearMessage()
        if result.ok and result.pdf_path is not None:
            self._preview.show_pdf(result.pdf_path)
            if self._side_by_side:
                self._pdf_side_panel.show_pdf(result.pdf_path)
            # Cache the PDF next to the document for instant loading
            if self._current_path is not None:
                import shutil
                cached = (self._current_path.parent
                          / f"{self._doc_stem(self._current_path)}.pdf")
                try:
                    shutil.copy2(result.pdf_path, cached)
                except OSError:
                    pass
            # Tell the editor how many pages the PDF has AND give it
            # the first-text snippet of each subsequent page so the
            # break-line overlay can anchor itself to the actual
            # block where the PDF starts that page — way more
            # accurate than the doc_height/pdf_pages uniform-spacing
            # fallback (which assumes content is evenly distributed,
            # and falls apart when page 1 has a title block).
            try:
                import pymupdf
                anchors: list[tuple[int, str]] = []
                with pymupdf.open(result.pdf_path) as pdf:
                    pages = len(pdf)
                    for i in range(1, pages):   # skip page 1 (no break above it)
                        snippet = _first_text_snippet(pdf[i])
                        if snippet:
                            anchors.append((i + 1, snippet))
                self._editor.text_edit.set_pdf_page_count(pages)
                self._editor.text_edit.set_page_anchors(anchors)
            except Exception:
                pass
        else:
            tail = "\n".join(result.log.splitlines()[-10:]) if result.log else ""
            self._preview.show_message(f"{result.error}\n\n{tail}")
            if self._side_by_side:
                self._pdf_side_panel.show_message(f"{result.error}\n\n{tail}")
        self._compile_worker = None
        if self._pending_recompile:
            self._pending_recompile = False
            self._kick_compile()

    # ----- cross-tab "Show in …" navigation -----

    def _nav_formatted_to_latex(self) -> None:
        snippet = self._editor.cursor_snippet()
        if snippet and self._latex_view.scroll_to_snippet(snippet):
            self._tabs.setCurrentIndex(1)

    def _nav_formatted_to_pdf(self) -> None:
        snippet = self._editor.cursor_snippet()
        if not snippet:
            return
        target = self._pdf_side_panel if self._side_by_side else self._preview
        if not self._side_by_side:
            self._tabs.setCurrentIndex(2)
        target.find_text(snippet)

    def _nav_latex_to_formatted(self) -> None:
        snippet = self._latex_view.cursor_snippet()
        if snippet and self._editor.scroll_to_snippet(snippet):
            self._tabs.setCurrentIndex(0)

    def _nav_latex_to_pdf(self) -> None:
        snippet = self._latex_view.cursor_snippet()
        if not snippet:
            return
        target = self._pdf_side_panel if self._side_by_side else self._preview
        if not self._side_by_side:
            self._tabs.setCurrentIndex(2)
        target.find_text(snippet)

    def _nav_pdf_to_formatted(self) -> None:
        page = self._preview.current_page()
        anchors = self._editor.text_edit.page_anchor_positions()
        # Find the anchor for this page and scroll the editor there
        for page_no, y in anchors:
            if page_no - 1 == page:
                cursor = self._editor.text_edit.textCursor()
                block = self._editor.text_edit.document().firstBlock()
                doc_layout = self._editor.text_edit.document().documentLayout()
                while block.isValid():
                    if doc_layout.blockBoundingRect(block).top() >= y:
                        cursor.setPosition(block.position())
                        self._editor.text_edit.setTextCursor(cursor)
                        self._editor.text_edit.centerCursor()
                        break
                    block = block.next()
                break
        self._tabs.setCurrentIndex(0)

    def _nav_pdf_to_latex(self) -> None:
        page = self._preview.current_page()
        anchors = self._editor.text_edit._page_anchors
        # Get the text snippet for the current page
        for page_no, snippet in anchors:
            if page_no - 1 == page:
                if self._latex_view.scroll_to_snippet(snippet):
                    self._tabs.setCurrentIndex(1)
                    return
                break
        self._tabs.setCurrentIndex(1)

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
        idx = self._heading_combo.findData(level)
        if idx < 0:
            idx = 0
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
    users see what KherveTeX can do before they have to type anything."""
    doc = examples.welcome()
    doc.meta = _apply_user_defaults(doc.meta)
    return doc
