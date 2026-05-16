"""Main window: tabbed interface (Formatted | LaTeX | PDF) with full menus."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction, QActionGroup, QGuiApplication, QKeySequence,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QSlider, QSpinBox, QStatusBar, QTabWidget,
    QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from . import __version__, git_backend, icons, kdocz, page_sizes, version_string
from .compiler import CompileResult, compile_tex, tectonic_available
from .editor import DocumentEditor, TEMPLATE_CHOICES
from . import importers
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

    def __init__(self, tex_source: str, workdir: Path):
        super().__init__()
        self._tex = tex_source
        self._workdir = workdir

    def run(self) -> None:
        self.finished_with.emit(compile_tex(self._tex, self._workdir))


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

        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel("<b>Page margins</b>"))
        form.addRow("Top:", self._m_top)
        form.addRow("Bottom:", self._m_bottom)
        form.addRow("Left:", self._m_left)
        form.addRow("Right:", self._m_right)
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
        )


# Back-compat alias for the older name used elsewhere in this file.
DocPropertiesDialog = DocSettingsDialog


# ---------- main window ----------

_RECENT_FILES_MAX = 8


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._current_path: Path | None = None
        self._kdocz_extract_dir: Path | None = None   # set when opening a .kdocz
        self._build_dir = Path(tempfile.mkdtemp(prefix="khervedoc-"))
        self._compile_worker: _CompileWorker | None = None
        self._pending_recompile = False
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
        self.move(screen.x() + (screen.width() - w) // 2,
                  screen.y() + (screen.height() - h) // 2)

        self._editor = DocumentEditor(self)
        self._latex_view = LatexView(self)
        self._preview = PdfPreview(self)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._editor, "Formatted")
        self._tabs.addTab(self._latex_view, "LaTeX")
        self._tabs.addTab(self._preview, "PDF")
        self.setCentralWidget(self._tabs)

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

        self._tectonic_label = QLabel(
            "tectonic: OK" if tectonic_available() else "tectonic: NOT FOUND — preview disabled",
            self)
        self._status.addPermanentWidget(self._tectonic_label)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()

        self._editor.documentChanged.connect(self._on_doc_changed)
        self._editor.text_edit.cursorPositionChanged.connect(self._sync_toolbar_state)
        # Reverse path: edits in the LaTeX tab re-parse via import_tex and
        # rebuild the Formatted view + PDF.
        self._latex_view.latexEdited.connect(self._on_latex_edited)
        # Flag toggled while we're rebuilding from LaTeX, so the
        # Formatted-edit handler doesn't immediately overwrite the LaTeX
        # text with its re-serialization (which would clobber the user's
        # in-progress edit).
        self._suppress_latex_update = False

        self._editor.set_document(_starter_document())
        self._update_title()
        self._kick_compile()

    # ----- actions -----

    def _build_actions(self) -> None:
        e = self._editor

        # File
        self.act_new = QAction(icons.file_new(), "&New", self,
                               shortcut=QKeySequence.New, triggered=self._new)
        self.act_open = QAction(icons.file_open(), "&Open...", self,
                                shortcut=QKeySequence.Open, triggered=self._open)
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
        self.act_pagebreak = QAction(icons.page_break(), "Page break", self,
                                     triggered=e.insert_page_break)
        self.act_hrule = QAction(icons.horizontal_rule(), "Horizontal rule", self,
                                 triggered=e.insert_horizontal_rule)

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

        # History
        self.act_commit_now = QAction(icons.commit(), "Commit && push now", self,
                                      triggered=self._commit_and_maybe_push)
        self.act_history = QAction(icons.history(), "Show commit &history...", self,
                                   triggered=self._show_history)

        # Help
        self.act_about = QAction("&About kherveDOC", self, triggered=self._about)

    # ----- menus -----

    def _build_menus(self) -> None:
        mb = self.menuBar()

        m_file = mb.addMenu("&File")
        m_file.addAction(self.act_new)
        m_file.addAction(self.act_open)
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
        m_insert.addSeparator()
        m_insert.addAction(self.act_bullet); m_insert.addAction(self.act_numbered)
        m_insert.addSeparator()
        m_insert.addAction(self.act_link); m_insert.addAction(self.act_footnote)
        m_insert.addAction(self.act_citation); m_insert.addAction(self.act_crossref)
        m_insert.addSeparator()
        m_insert.addAction(self.act_figure); m_insert.addAction(self.act_table)
        m_insert.addSeparator()
        m_insert.addAction(self.act_pagebreak); m_insert.addAction(self.act_hrule)
        m_insert.addAction(self.act_raw)

        m_view = mb.addMenu("&View")
        m_view.addAction(self.act_view_formatted)
        m_view.addAction(self.act_view_latex)
        m_view.addAction(self.act_view_pdf)

        m_history = mb.addMenu("&History")
        m_history.addAction(self.act_commit_now)
        m_history.addAction(self.act_history)

        m_help = mb.addMenu("&Help")
        m_help.addAction(self.act_about)

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
        for act in (self.act_math_inline, self.act_math_block):
            tb.addAction(act)
        tb.addSeparator()
        for act in (self.act_link, self.act_footnote, self.act_citation,
                    self.act_crossref):
            tb.addAction(act)
        tb.addSeparator()
        for act in (self.act_figure, self.act_table, self.act_pagebreak,
                    self.act_hrule):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_commit_now); tb.addAction(self.act_history)

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
        self._editor.set_document(_starter_document())
        self._update_title()

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

    def _write_to(self, path: Path) -> None:
        doc = self._editor.get_document()
        # Dispatch on the file extension: .kdocz is the bundled ZIP container,
        # .kdoc.json is the plain JSON model. The .tex export sits alongside
        # in both cases so users can inspect the source without unzipping.
        if kdocz.is_kdocz_path(path):
            kdocz.save_kdocz(doc, path)
            tex_basename = path.stem
        else:
            path.write_text(to_json(doc), encoding="utf-8")
            tex_basename = path.name.replace(".kdoc.json", "")
        tex_path = path.parent / f"{tex_basename}.tex"
        tex_path.write_text(serialize_document(doc), encoding="utf-8")

        commit_msg = f"Save {path.name} at {datetime.now().isoformat(timespec='seconds')}"
        if git_backend.is_available():
            git_backend.init_repo(path.parent)
            oid = git_backend.commit_all(path.parent, commit_msg)
            pushed = git_backend.push(path.parent) if oid else False
            if oid:
                tail = f"; pushed" if pushed else " (push failed or no remote)"
                self._status.showMessage(f"Saved + committed {oid[:8]}{tail}", 5000)
            else:
                self._status.showMessage("Saved (no changes to commit)", 4000)
        else:
            self._status.showMessage("Saved (pygit2 unavailable)", 4000)

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
        result = compile_tex(serialize_document(self._editor.get_document()),
                             self._build_dir)
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
        self._preview.set_zoom_percent(snapped)

    def _nudge_zoom(self, delta: int) -> None:
        self._zoom_slider.setValue(self._zoom_slider.value() + delta)

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
            QMessageBox.information(self, "Commit", "Save the document first.")
            return
        self._write_to(self._current_path)

    def _show_history(self) -> None:
        if self._current_path is None:
            QMessageBox.information(self, "History", "Save the document first.")
            return
        rows = git_backend.history(self._current_path.parent)
        if not rows:
            QMessageBox.information(self, "History", "No commits yet.")
            return
        text = "\n".join(f"{oid}  {ts}  {msg}" for oid, ts, msg in rows)
        QMessageBox.information(self, "Commit history", text)

    def _about(self) -> None:
        QMessageBox.about(
            self, "About kherveDOC",
            f"<h3>kherveDOC {version_string()}</h3>"
            f"<p>WYSIWYG editor that produces LaTeX and tracks changes in Git.</p>"
            f"<p>tectonic: {'OK' if tectonic_available() else 'not installed'}</p>")

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

    def _kick_compile(self) -> None:
        if not tectonic_available():
            self._preview.show_message(
                "tectonic not installed — install it to see a live preview.")
            return
        if self._compile_worker is not None and self._compile_worker.isRunning():
            self._pending_recompile = True
            return
        tex = serialize_document(self._editor.get_document())
        self._latex_view.set_source(tex)
        self._compile_worker = _CompileWorker(tex, self._build_dir)
        self._compile_worker.finished_with.connect(self._on_compile_done)
        self._compile_worker.start()
        self._status.showMessage("Compiling...", 0)

    def _on_compile_done(self, result: CompileResult) -> None:
        self._status.clearMessage()
        if result.ok and result.pdf_path is not None:
            self._preview.show_pdf(result.pdf_path)
        else:
            tail = "\n".join(result.log.splitlines()[-10:]) if result.log else ""
            self._preview.show_message(f"{result.error}\n\n{tail}")
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


def _starter_document() -> Document:
    return Document(
        meta=DocMeta(title="", author=""),
        children=[
            Title(children=[Text(text="My document")]),
            Author(children=[Text(text="Your name")]),
            Section(level=1, children=[Text(text="Introduction")]),
            Paragraph(children=[
                Text(text="Type here. Use the paragraph-style picker to choose "),
                Text(text="Title", marks=["bold"]),
                Text(text=", "),
                Text(text="Heading 1-5", marks=["bold"]),
                Text(text=" or "),
                Text(text="Body text", marks=["bold"]),
                Text(text=". Use the Insert menu for math, lists, links, "),
                Text(text="figures, tables and more."),
            ]),
        ],
    )
