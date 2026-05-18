"""WYSIWYG editor widget — QTextEdit driving the document model.

Per-block: user-state encodes node type (0=Paragraph, 1-5=Section, 99=MathBlock,
other sentinels for figure/table/raw whose body is stored as block text).

Inlines: special spans (math, link, footnote, citation, cross-ref) are stored
as text fragments with a custom char-format property holding the payload. The
visible text is the human-readable representation; serialization rebuilds the
LaTeX from the property.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import (
    QAction, QColor, QFont, QImage, QKeySequence, QTextBlockFormat,
    QTextCharFormat, QTextCursor, QTextFrameFormat, QTextImageFormat,
    QTextLength, QTextListFormat, QTextTable, QTextTableFormat,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QInputDialog, QMenu, QScrollArea,
    QVBoxLayout, QWidget,
)

from . import page_sizes
from .paged_edit import PagedTextEdit


# LaTeX document classes shown in the toolbar combo. Order = display order.
TEMPLATE_CHOICES = ["article", "report", "book", "letter", "beamer", "memoir"]

from .model import (
    Abstract, Author, Citation, Comment, CrossRef, Document, DocMeta, Figure,
    Footnote, Frame, Highlight, HIGHLIGHT_COLORS, InlineRaw, Keywords, Link,
    List as ListNode, ListItem, MathBlock, MathInline, Paragraph, RawLatex,
    Section, Table, Text, Title,
)


# ---- rendered math (matplotlib mathtext) ----
import re as _re
import hashlib as _hashlib
from io import BytesIO as _BytesIO

_MATH_IMAGE_CACHE: dict[str, Path | None] = {}
_math_tmp_dir: Path | None = None


def _math_cache_dir() -> Path:
    """Lazy-init a temp directory for rendered math PNGs."""
    global _math_tmp_dir
    if _math_tmp_dir is None:
        _math_tmp_dir = Path(tempfile.mkdtemp(prefix="khervedoc-math-"))
    return _math_tmp_dir

_ENV_STRIP_RE = _re.compile(
    r"\\begin\{(equation|align|gather|multline|displaymath|eqnarray"
    r"|alignat|split)\*?\}(.*?)\\end\{\1\*?\}",
    _re.DOTALL)


def _render_math_image(latex: str, font_size: int = 14,
                       cache_dir: Path | None = None) -> Path | None:
    """Render a LaTeX math expression to a PNG file using matplotlib.

    Handles multi-line equations (align, gather, etc.) by splitting on
    ``\\\\`` and rendering each line separately, stacked vertically.
    Returns the path to the PNG file, or None on failure. Results are
    cached on disk.  When *cache_dir* is given the PNG is written there
    instead of the global temp directory."""
    if latex in _MATH_IMAGE_CACHE:
        cached = _MATH_IMAGE_CACHE[latex]
        if cached is not None and cached.exists():
            return cached
    try:
        from matplotlib.figure import Figure as MplFigure
    except ImportError:
        _MATH_IMAGE_CACHE[latex] = None
        return None
    # Strip environment wrappers to get bare math.
    raw = latex.strip()
    m = _ENV_STRIP_RE.search(raw)
    if m:
        raw = m.group(2).strip()
    raw = raw.strip("$").strip()
    if not raw:
        _MATH_IMAGE_CACHE[latex] = None
        return None
    # Translate LaTeX commands that mathtext doesn't know about.
    raw = raw.replace("\\tfrac", "\\frac")
    raw = raw.replace("\\dfrac", "\\frac")
    raw = raw.replace("\\text{", "\\mathrm{")
    raw = raw.replace("\\operatorname{", "\\mathrm{")
    raw = raw.replace("\\displaystyle", "")
    raw = raw.replace("\\textstyle", "")
    raw = raw.replace("\\nonumber", "")
    raw = raw.replace("\\notag", "")
    raw = raw.replace("\\label{", "\\mathrm{")  # hide labels
    # Split multi-line math on \\ and clean up alignment markers.
    lines = _re.split(r"\\\\", raw)
    lines = [ln.replace("&", " ").strip() for ln in lines]
    lines = [ln for ln in lines if ln]
    if not lines:
        _MATH_IMAGE_CACHE[latex] = None
        return None
    try:
        n = len(lines)
        line_height = 0.35
        fig_h = max(0.4, n * line_height)
        fig = MplFigure(figsize=(6, fig_h), dpi=150)
        fig.patch.set_alpha(0)
        for i, line in enumerate(lines):
            y = 1.0 - (i + 0.5) / n
            fig.text(0.5, y, f"${line}$", fontsize=font_size,
                     ha="center", va="center", math_fontfamily="cm")
        h = _hashlib.md5(latex.encode()).hexdigest()[:12]
        dest = cache_dir if cache_dir is not None else _math_cache_dir()
        png_path = dest / f"math_{h}.png"
        fig.savefig(str(png_path), format="png", bbox_inches="tight",
                    pad_inches=0.04, transparent=True)
        _MATH_IMAGE_CACHE[latex] = png_path
        return png_path
    except Exception:
        _MATH_IMAGE_CACHE[latex] = None
        return None


# ---- per-block user state encoding ----
_STATE_PARAGRAPH = 0
_STATE_TITLE = 7        # Word-style "Title" paragraph; emits \maketitle
_STATE_AUTHOR = 8       # Author of the document; pulled into \author{} preamble
_STATE_ABSTRACT = 9     # Abstract paragraph; consecutive blocks merge
_STATE_KEYWORDS = 10    # Keyword line; consecutive blocks merge with \sep
_STATE_CHAPTER = 11     # \chapter — only valid in report/book/memoir classes
_STATE_FRAME = 12       # \begin{frame} — only valid in beamer class
_STATE_MATH_BLOCK = 99
_STATE_FIGURE = 100
_STATE_TABLE = 101
_STATE_RAW = 102


# Document classes that natively support \chapter. The heading-style
# combo greys out the Chapter entry for any other class (article,
# letter, beamer — those classes don't define \chapter at all).
CHAPTER_CLASSES = ("report", "book", "memoir")


def class_supports_chapter(class_name: str) -> bool:
    """True for report / book / memoir (and their variants). article /
    letter / beamer return False, so the heading combo greys out
    Chapter for those."""
    if not class_name:
        return False
    head = class_name.lower().split(",")[0].strip()
    return any(head.startswith(c) for c in CHAPTER_CLASSES)


# ---- char-format custom property ids ----
_P_MATH = QTextCharFormat.UserProperty + 1
_P_LINK = QTextCharFormat.UserProperty + 2     # value = url
_P_FOOTNOTE = QTextCharFormat.UserProperty + 3  # value = note text
_P_CITATION = QTextCharFormat.UserProperty + 4  # value = "key1,key2|style"
_P_CROSSREF = QTextCharFormat.UserProperty + 5  # value = "label|kind"
_P_RAW = QTextCharFormat.UserProperty + 6       # value = raw LaTeX source
_P_HIGHLIGHT = QTextCharFormat.UserProperty + 7  # value = color name
_P_COMMENT = QTextCharFormat.UserProperty + 8    # value = "note|author|timestamp|resolved"


# ---- block payload storage (figures/tables/raw) ----
# Block-text holds a compact serialization the editor doesn't try to render
# visually beyond a stub. Each block's TYPE is identified by its userState
# (figures get _STATE_FIGURE, etc.), so the stub text doesn't need a
# "[TABLE]" / "[FIGURE]" prefix — those were developer-noise and have been
# removed. Current format examples (all kept in one QTextBlock by
# substituting U+2028 for '\n'):
#   Figure: <path>
#           Caption: <text>
#           Label: <label>
#           Width: <width>
#   Table:  r1c1<TAB>r1c2<TAB>...
#           r2c1<TAB>r2c2<TAB>...
#           Caption: <text>
#           Label: <label>
#           Alignment: <align>
#   Raw / Code / Bibliography: raw LaTeX text with internal '\n' replaced
#           by U+2028 so Qt keeps every line in the same QTextBlock.
# The OLD prefixed format ("[TABLE] ... || cap | label | align") is still
# accepted by _table_from_stub / _figure_from_stub etc. so sessions
# carrying stale stubs still load cleanly.
_FIGURE_PREFIX = "[FIGURE] "      # legacy — accepted on read, never written
_TABLE_PREFIX = "[TABLE] "        # legacy — accepted on read, never written
_RAW_PREFIX = "[RAW] "            # legacy — accepted on read, never written
_CODE_PREFIX = "[CODE] "          # legacy — accepted on read, never written
_BIB_PREFIX = "[BIBLIOGRAPHY] "   # legacy — accepted on read, never written
# Read-back prefix list. Kept for backward compatibility with older
# documents whose RawLatex stubs were prefixed.
_RAW_PREFIXES = (_CODE_PREFIX, _BIB_PREFIX, _RAW_PREFIX)
# Field labels for the meta line(s) appended to a figure/table stub.
_META_CAPTION = "Caption: "
_META_LABEL = "Label: "
_META_WIDTH = "Width: "
_META_ALIGNMENT = "Alignment: "
_META_KEYS = (_META_CAPTION, _META_LABEL, _META_WIDTH, _META_ALIGNMENT)


def _figure_stub(block) -> str:
    """Render a Figure as a multi-line stub kept inside one QTextBlock
    (lines joined with U+2028). Each metadata field is on its own
    visible line with a clear "Caption:" / "Label:" / "Width:" label
    so the editor doesn't expose `|`-separated developer noise."""
    parts = [block.path]
    parts.append(f"{_META_CAPTION}{block.caption or ''}")
    parts.append(f"{_META_LABEL}{block.label or ''}")
    parts.append(f"{_META_WIDTH}{block.width or ''}")
    return _LINE_SEP.join(parts)


def _table_stub(block) -> str:
    """Render a Table the same way: rows first (TAB-separated cells,
    U+2028-separated rows), then one metadata line per attribute."""
    rows = [_LINE_SEP.join("\t".join(r) for r in block.rows)] if block.rows else []
    meta = [
        f"{_META_CAPTION}{block.caption or ''}",
        f"{_META_LABEL}{block.label or ''}",
        f"{_META_ALIGNMENT}{block.alignment or ''}",
    ]
    return _LINE_SEP.join(filter(None, rows + meta))


def _split_stub_meta(text: str) -> tuple[list[str], dict[str, str]]:
    """Split a stub into (content lines, metadata dict).

    Walks the trailing lines of `text` (split on U+2028) and pulls off
    any that start with one of the known meta labels. Stops as soon as
    a line doesn't look like a meta line — the rest are content.
    Returns the content lines in their original order plus a {label
    (no trailing space): value} dict."""
    if not text:
        return [], {}
    lines = text.split(_LINE_SEP)
    meta: dict[str, str] = {}
    # Walk from the back; remove meta lines as we encounter them.
    while lines:
        last = lines[-1]
        matched = None
        for key in _META_KEYS:
            if last.startswith(key):
                matched = key
                break
        if matched is None:
            break
        meta[matched.rstrip(": ")] = last[len(matched):]
        lines.pop()
    return lines, meta
# Qt splits text into separate QTextBlocks at every '\n'. For block-text
# fields that NEED to carry literal newlines (multi-line lstlisting and
# verbatim envs, multi-row tables) we substitute U+2028 (Unicode "Line
# Separator"), which Qt renders as a soft line break inside one block
# and which round-trips losslessly on read-back.
_LINE_SEP = chr(0x2028)


# Heading sizes: 0 is reserved for \chapter (the largest), then the
# usual section / subsection / … hierarchy. Chapter sits above
# Heading 1 because that's how LaTeX's book / report layout typesets it.
_HEADING_FONT_SIZES = {0: 26, 1: 22, 2: 18, 3: 15, 4: 13, 5: 12}

# Bidirectional mapping for paragraph alignment.
_QT_ALIGNMENT = {
    "left": Qt.AlignLeft,
    "center": Qt.AlignHCenter,
    "right": Qt.AlignRight,
    "justify": Qt.AlignJustify,
}
# Qt.AlignLeft is the default for new blocks; in LaTeX semantics that
# corresponds to justified text (no wrapper env). Map both to "justify"
# so paragraphs don't spuriously acquire \begin{flushleft} wrappers.
_ALIGNMENT_FROM_QT = {
    Qt.AlignLeft: "justify",
    Qt.AlignHCenter: "center",
    Qt.AlignRight: "right",
    Qt.AlignJustify: "justify",
}
_TITLE_FONT_SIZE = 28


def _heading_char_format(level: int) -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont()
    f.setBold(True)
    f.setPointSize(_HEADING_FONT_SIZES.get(level, 12))
    fmt.setFont(f)
    return fmt


def _frame_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont()
    f.setBold(True)
    f.setPointSize(18)
    fmt.setFont(f)
    fmt.setForeground(QColor("#1565C0"))
    return fmt


def _title_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont()
    f.setBold(True)
    f.setPointSize(_TITLE_FONT_SIZE)
    fmt.setFont(f)
    return fmt


def _title_block_format() -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    bfmt.setAlignment(Qt.AlignHCenter)
    bfmt.setTopMargin(8); bfmt.setBottomMargin(8)
    return bfmt


def _author_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont()
    f.setItalic(True); f.setPointSize(14)
    fmt.setFont(f)
    fmt.setForeground(QColor("#555"))
    return fmt


def _author_block_format() -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    bfmt.setAlignment(Qt.AlignHCenter)
    bfmt.setTopMargin(0); bfmt.setBottomMargin(24)
    return bfmt


def _abstract_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont()
    f.setPointSize(11)
    fmt.setFont(f)
    return fmt


def _abstract_block_format() -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    # Inset the abstract on both sides + warm cream highlight so it
    # reads as a journal-style abstract block at a glance, clearly
    # distinct from body text.
    bfmt.setLeftMargin(48); bfmt.setRightMargin(48)
    bfmt.setTopMargin(8); bfmt.setBottomMargin(8)
    bfmt.setBackground(QColor("#fff5d6"))
    return bfmt


def _keywords_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont()
    f.setItalic(True); f.setPointSize(11)
    fmt.setFont(f)
    fmt.setForeground(QColor("#444"))
    return fmt


def _keywords_block_format() -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    # Pale blue band to mark keywords as a separate "metadata" block,
    # distinct from both body text and the abstract above it.
    bfmt.setLeftMargin(48); bfmt.setRightMargin(48)
    bfmt.setTopMargin(4); bfmt.setBottomMargin(18)
    bfmt.setBackground(QColor("#e3f0ff"))
    return bfmt


def _math_block_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(11)
    fmt.setFont(f)
    fmt.setBackground(QColor("#eef3ff")); fmt.setForeground(QColor("#1a3a8c"))
    return fmt


def _math_inline_format(latex: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont("Consolas"); f.setStyleHint(QFont.Monospace)
    fmt.setFont(f)
    fmt.setBackground(QColor("#fff5d6")); fmt.setForeground(QColor("#7a4c00"))
    fmt.setProperty(_P_MATH, latex)
    return fmt


def _link_format(url: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor("#1a6dd8")); fmt.setFontUnderline(True)
    fmt.setToolTip(url); fmt.setProperty(_P_LINK, url)
    return fmt


def _footnote_format(note: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor("#7a4c00")); fmt.setBackground(QColor("#fff0d0"))
    f = fmt.font(); f.setPointSize(max(8, f.pointSize() - 2)); fmt.setFont(f)
    fmt.setToolTip(note); fmt.setProperty(_P_FOOTNOTE, note)
    return fmt


def _citation_format(keys_style: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor("#5b2d83")); fmt.setBackground(QColor("#f1e5ff"))
    fmt.setProperty(_P_CITATION, keys_style)
    return fmt


def _crossref_format(label_kind: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor("#0a6")); fmt.setBackground(QColor("#e3f5ea"))
    fmt.setProperty(_P_CROSSREF, label_kind)
    return fmt


def _raw_inline_format(latex: str) -> QTextCharFormat:
    """Display InlineRaw nodes (unknown macros preserved from .tex
    imports, text-mode symbol-palette inserts like \\Kstroke) in a
    monospace muted tag so the user can see they're verbatim LaTeX
    rather than typeable letters."""
    fmt = QTextCharFormat()
    f = QFont("Consolas"); f.setStyleHint(QFont.Monospace)
    fmt.setFont(f)
    fmt.setForeground(QColor("#0a3d62")); fmt.setBackground(QColor("#e8f0fb"))
    fmt.setToolTip(latex); fmt.setProperty(_P_RAW, latex)
    return fmt


def _highlight_format(color: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    hex_color = HIGHLIGHT_COLORS.get(color, "#FFFF00")
    fmt.setBackground(QColor(hex_color))
    fmt.setProperty(_P_HIGHLIGHT, color)
    return fmt


def _comment_format(note: str, author: str, timestamp: str,
                    resolved: bool) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setBackground(QColor("#FFE4B5"))
    fmt.setUnderlineStyle(QTextCharFormat.DashUnderline)
    fmt.setUnderlineColor(QColor("#d96b00"))
    resolved_str = "1" if resolved else "0"
    payload = f"{note}|{author}|{timestamp}|{resolved_str}"
    fmt.setProperty(_P_COMMENT, payload)
    tip = f"{author}: {note}" if author else note
    fmt.setToolTip(tip)
    return fmt


def _stub_block_format() -> QTextBlockFormat:
    # Generic stub backdrop — kept as a fallback for code paths that
    # don't yet differentiate by content type. Per-type variants below
    # give each kind of block a distinct visual hint.
    bfmt = QTextBlockFormat()
    bfmt.setTopMargin(6); bfmt.setBottomMargin(6)
    bfmt.setBackground(QColor("#f5f5f7"))
    return bfmt


# Theme-aware palettes for table/figure/raw block widgets. The editor
# stores its current theme on self._dark and looks up the matching
# palette here. Keys match the field name; values are QColor strings.
_LIGHT_PALETTE = {
    "figure_block_bg":  "#e8f5e9",
    "table_block_bg":   "#fff3e0",
    "table_border":     "#e6a85c",
    "table_bg":         "#fff3e0",
    "table_header_bg":  "#ffe0b2",
    "table_header_fg":  "#e65100",
    "table_cell_fg":    "#333333",
    "table_caption_fg": "#888888",
    "figure_border":    "#c8e6c9",
    "figure_bg":        "#e8f5e9",
    "figure_caption_fg": "#2e7d32",
}
_DARK_PALETTE = {
    # Backgrounds tuned to be clearly visible against the editor's
    # #2d2d2d dark page while keeping enough lightness to read text on.
    "figure_block_bg":  "#1f3d2a",
    "table_block_bg":   "#3d2e1a",
    "table_border":     "#a37745",
    "table_bg":         "#3d2e1a",
    "table_header_bg":  "#5a3f1f",
    "table_header_fg":  "#ffab40",
    "table_cell_fg":    "#e8e0d4",
    "table_caption_fg": "#b0a99a",
    "figure_border":    "#5a8a5a",
    "figure_bg":        "#1f3d2a",
    "figure_caption_fg": "#a5d6a7",
}


def _palette(dark: bool) -> dict:
    return _DARK_PALETTE if dark else _LIGHT_PALETTE


def _figure_block_format(dark: bool = False) -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    bfmt.setTopMargin(6); bfmt.setBottomMargin(6)
    bfmt.setBackground(QColor(_palette(dark)["figure_block_bg"]))
    return bfmt


def _table_block_format(dark: bool = False) -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    bfmt.setTopMargin(6); bfmt.setBottomMargin(6)
    bfmt.setBackground(QColor(_palette(dark)["table_block_bg"]))
    return bfmt


def _make_table_format(ncols: int, dark: bool = False) -> QTextTableFormat:
    """Build a QTextTableFormat for a table with *ncols* columns."""
    p = _palette(dark)
    tfmt = QTextTableFormat()
    tfmt.setBorderBrush(QColor(p["table_border"]))
    tfmt.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
    tfmt.setBorder(1)
    tfmt.setCellPadding(6)
    tfmt.setCellSpacing(0)
    tfmt.setBackground(QColor(p["table_bg"]))
    tfmt.setMargin(8)
    constraints = [QTextLength(QTextLength.PercentageLength, 100 / ncols)
                   for _ in range(ncols)]
    tfmt.setColumnWidthConstraints(constraints)
    return tfmt


# Custom property to store table metadata (caption, label, alignment)
# on the QTextTable's frame format so we can read it back.
_P_TABLE_CAPTION = QTextCharFormat.UserProperty + 20
_P_TABLE_LABEL = QTextCharFormat.UserProperty + 21
_P_TABLE_ALIGNMENT = QTextCharFormat.UserProperty + 22

# Figure-table properties (figures rendered as 1-column QTextTable).
_P_FIGURE_PATH = QTextCharFormat.UserProperty + 30
_P_FIGURE_LABEL = QTextCharFormat.UserProperty + 31
_P_FIGURE_WIDTH = QTextCharFormat.UserProperty + 32
_P_IS_FIGURE = QTextCharFormat.UserProperty + 33


def _make_figure_table_format(dark: bool = False) -> QTextTableFormat:
    """QTextTableFormat for a figure widget (1-column table)."""
    p = _palette(dark)
    tfmt = QTextTableFormat()
    tfmt.setBorderBrush(QColor(p["figure_border"]))
    tfmt.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
    tfmt.setBorder(1)
    tfmt.setCellPadding(8)
    tfmt.setCellSpacing(0)
    tfmt.setBackground(QColor(p["figure_bg"]))
    tfmt.setMargin(10)
    tfmt.setAlignment(Qt.AlignHCenter)
    tfmt.setColumnWidthConstraints(
        [QTextLength(QTextLength.PercentageLength, 100)])
    tfmt.setProperty(_P_IS_FIGURE, True)
    return tfmt


def _code_block_format() -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    bfmt.setTopMargin(6); bfmt.setBottomMargin(6)
    bfmt.setBackground(QColor("#eef2f7"))   # pale slate — "code"
    return bfmt


def _bibliography_block_format() -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    bfmt.setTopMargin(6); bfmt.setBottomMargin(6)
    bfmt.setBackground(QColor("#f3e5f5"))   # pale purple — "references"
    return bfmt


def _raw_block_format() -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    bfmt.setTopMargin(6); bfmt.setBottomMargin(6)
    bfmt.setBackground(QColor("#ffebee"))   # pale red — "raw LaTeX, careful"
    return bfmt


def _typed_stub_char_format(color_hex: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(10)
    fmt.setFont(f); fmt.setForeground(QColor(color_hex))
    return fmt


class DocumentEditor(QWidget):
    """Rich-text editor that maintains a bidirectional binding with Document."""

    documentChanged = Signal()  # debounced after the user stops typing
    zoomChanged = Signal(int)   # emitted when fit-to-width recalculates zoom

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._building = False
        # Initialise meta up front — _apply_page_size below reads it.
        self._meta = DocMeta()
        # Zoom state: tracked so set_zoom_percent can compute deltas.
        self._base_font_pt = 12
        self._body_font_pt = 12   # user-controllable body text size
        self._zoom_percent = 100
        self._zoom_delta = 0
        self._fit_to_width = True
        # Current colour theme. Block formats for tables / figures
        # / raw blocks read this when constructing their palettes so
        # the cells stay readable against the editor's dark / light
        # page background.
        self._dark = False

        # MS Word look: a white "page" card centered on a grey desk, sized
        # to real A4/Letter/Legal paper at 96 DPI. The text flows as one
        # editable surface but page-break lines mark the paginations Latex
        # will produce in the PDF.
        self._edit = PagedTextEdit()
        self._edit.setAcceptRichText(False)
        self._edit.setFrameShape(QFrame.NoFrame)
        f = QFont("Georgia"); f.setPointSize(12)
        self._edit.setFont(f)
        # ~1 inch of inner padding at 100% zoom; scaled by set_zoom_percent
        # so the number of characters per line stays constant when zooming.
        self._base_doc_margin = 72
        self._edit.document().setDocumentMargin(self._base_doc_margin)
        self._edit.setStyleSheet("QTextEdit { background: white; border: none; }")
        self._edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self._edit.customContextMenuRequested.connect(self._show_context_menu)
        self._extra_context_actions: list[tuple[str, object]] = []

        self._page = QFrame()
        self._page.setObjectName("page")
        self._page.setStyleSheet(
            "#page { background: white; border: 1px solid #b8bcc1; }")
        page_layout = QVBoxLayout(self._page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        page_layout.addWidget(self._edit, 1)
        self._apply_page_size(page_sizes.by_code(self._meta.page_size))

        # Attach the live spell-check highlighter. The class is a
        # graceful no-op when pyspellchecker isn't installed, so this
        # always returns SOMETHING the View > Check spelling toggle
        # can call into.
        from .spellcheck import SpellHighlighter
        self._spell_highlighter = SpellHighlighter(self._edit.document())

        desk = QWidget()
        desk.setObjectName("desk")
        desk.setStyleSheet("#desk { background: #d0d4d8; }")
        # Vertical outer layout anchors the page row to the top of the
        # desk, so the white card sits at the top of the visible area
        # rather than being stretched to fill the entire scroll viewport.
        desk_layout = QVBoxLayout(desk)
        desk_layout.setContentsMargins(0, 24, 0, 32)
        page_row = QHBoxLayout()
        page_row.addStretch(1)
        page_row.addWidget(self._page, 0, Qt.AlignTop)
        page_row.addStretch(1)
        desk_layout.addLayout(page_row)
        desk_layout.addStretch(1)

        self._scroll = QScrollArea(self)
        self._scroll.setWidget(desk)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

        # Resize the QTextEdit to its document height so the outer scrollbar
        # is the only one — like a real page in Word that grows downward.
        self._edit.document().documentLayout().documentSizeChanged.connect(
            self._resize_to_document)

        self._fit_debounce = QTimer(self)
        self._fit_debounce.setSingleShot(True)
        self._fit_debounce.setInterval(150)
        self._fit_debounce.timeout.connect(self._apply_fit_to_width)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(450)
        self._debounce.timeout.connect(self.documentChanged)

        self._math_refresh = QTimer(self)
        self._math_refresh.setSingleShot(True)
        self._math_refresh.setInterval(600)
        self._math_refresh.timeout.connect(self._refresh_math_images)

        self._edit.textChanged.connect(self._on_text_changed)

        # Per-session image scratch dir. Pasted clipboard images and dropped
        # image files land here; the figure stub points at the saved path.
        # save_kdocz will bundle them into the archive on Save As .kdocz.
        self._images_dir = Path(tempfile.mkdtemp(prefix="khervedoc-imgs-"))
        self._equations_dir: Path | None = None
        self._edit.set_images_dir(self._images_dir)
        self._edit.imageReceived.connect(self._on_image_received)
        self._source_dir: Path | None = None

    # ---------- public ----------

    @property
    def text_edit(self) -> PagedTextEdit:
        return self._edit

    def cursor_snippet(self, max_chars: int = 30) -> str:
        """Return a short text snippet around the cursor for cross-tab nav."""
        cursor = self._edit.textCursor()
        block = cursor.block()
        text = block.text().strip()
        # Strip object replacement chars and control chars
        text = text.replace("\ufffc", "").replace("\u2028", " ").strip()
        if len(text) > max_chars:
            # Centre the snippet around the cursor position within the block
            pos_in_block = cursor.positionInBlock()
            start = max(0, pos_in_block - max_chars // 2)
            text = text[start:start + max_chars]
        return text

    def scroll_to_snippet(self, snippet: str) -> bool:
        """Find *snippet* in the document and scroll to it. Returns True
        if found."""
        if not snippet:
            return False
        doc = self._edit.document()
        cursor = doc.find(snippet)
        if cursor.isNull():
            return False
        self._edit.setTextCursor(cursor)
        self._edit.centerCursor()
        return True

    def set_source_dir(self, path: Path | None) -> None:
        self._source_dir = path

    def set_document_dir(self, doc_dir: Path) -> None:
        """Point image storage at permanent subdirs next to the document.

        Creates ``equations/`` and ``figures/`` folders under *doc_dir*
        and migrates any images that were in the previous temp dirs."""
        import shutil

        eq_dir = doc_dir / "equations"
        fig_dir = doc_dir / "figures"
        eq_dir.mkdir(exist_ok=True)
        fig_dir.mkdir(exist_ok=True)

        # Migrate existing equation PNGs
        old_eq = self._equations_dir or _math_tmp_dir
        if old_eq and old_eq.exists() and old_eq != eq_dir:
            for f in old_eq.glob("math_*.png"):
                dest = eq_dir / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)

        # Migrate existing figure images
        old_fig = self._images_dir
        if old_fig.exists() and old_fig != fig_dir:
            for f in old_fig.iterdir():
                if f.is_file():
                    dest = fig_dir / f.name
                    if not dest.exists():
                        shutil.copy2(f, dest)

        self._equations_dir = eq_dir
        self._images_dir = fig_dir
        self._edit.set_images_dir(fig_dir)

        # Update cached math paths so they point at the new location
        for latex_key, old_path in list(_MATH_IMAGE_CACHE.items()):
            if old_path is None:
                continue
            new_path = eq_dir / old_path.name
            if new_path.exists():
                _MATH_IMAGE_CACHE[latex_key] = new_path

    def meta(self) -> DocMeta:
        return self._meta

    def set_meta(self, meta: DocMeta) -> None:
        prev_size = self._meta.page_size if self._meta else None
        self._meta = meta
        if meta.page_size != prev_size:
            self._apply_page_size(page_sizes.by_code(meta.page_size))
        self._on_text_changed()

    def set_page_size(self, code: str) -> None:
        self._meta.page_size = code
        self._apply_page_size(page_sizes.by_code(code))
        self._on_text_changed()

    def _apply_page_size(self, page: "page_sizes.PageSize") -> None:
        # Honour the current zoom so switching page sizes while zoomed in
        # doesn't snap the card back to 100%.
        scale = self._zoom_percent / 100 if self._zoom_percent else 1.0
        w = round(page.width_px * scale)
        h = round(page.height_px * scale)
        self._page.setFixedWidth(w)
        self._edit.set_page_size_px(w, h)
        self._resize_to_document()

    def _resize_to_document(self, size=None) -> None:
        """Size the QTextEdit to its actual content so the cursor lands at
        the top of the page card. Now that PagedTextEdit no longer calls
        QTextDocument.setPageSize, document().size().height() reports the
        real content height rather than a minimum-one-page reading, so a
        new document gets a short card with the title at the top and the
        card grows downward as the user types.
        """
        doc_h = max(1, int(self._edit.document().size().height()))
        # A small minimum so the card always has a visible outline; small
        # enough that content stays anchored to the top.
        total_h = max(doc_h + 24, 240)
        self._edit.setMinimumHeight(total_h)
        self._edit.setMaximumHeight(total_h)
        # The page frame also needs explicit height clamps; without these
        # the QHBoxLayout that centres it would stretch the frame to fill
        # the available vertical space, painting white below the text.
        self._page.setMinimumHeight(total_h)
        self._page.setMaximumHeight(total_h)

    def set_document(self, doc: Document) -> None:
        self._building = True
        try:
            self._meta = doc.meta
            self._edit.clear()
            cursor = self._edit.textCursor()
            cursor.movePosition(QTextCursor.Start)

            first = True
            for block in doc.children:
                if not first:
                    cursor.insertBlock(QTextBlockFormat(), QTextCharFormat())
                first = False
                self._render_block(cursor, block)
        finally:
            self._building = False
        self.documentChanged.emit()

    def get_document(self) -> Document:
        qdoc = self._edit.document()
        blocks: list = []
        # QTextLists span multiple QTextBlocks. We coalesce them.
        seen_lists: dict[int, list] = {}
        seen_tables: set[int] = set()
        block = qdoc.firstBlock()
        while block.isValid():
            # Detect QTextTable frames — all blocks inside a table belong
            # to the same QTextTable object. We extract the whole table on
            # the first block we encounter and skip the rest.
            cursor = QTextCursor(block)
            qtable = cursor.currentTable()
            if qtable is not None:
                tid = id(qtable)
                if tid not in seen_tables:
                    seen_tables.add(tid)
                    tfmt = qtable.format()
                    if tfmt.property(_P_IS_FIGURE):
                        blocks.append(self._figure_from_qtexttable(qtable))
                    else:
                        blocks.append(self._table_from_qtexttable(qtable))
                block = block.next()
                continue

            text_list = block.textList()
            if text_list is not None:
                tl_id = id(text_list)
                if tl_id not in seen_lists:
                    ordered = text_list.format().style() in (
                        QTextListFormat.ListDecimal, QTextListFormat.ListLowerAlpha,
                        QTextListFormat.ListUpperAlpha, QTextListFormat.ListLowerRoman,
                        QTextListFormat.ListUpperRoman,
                    )
                    node = ListNode(ordered=ordered, items=[])
                    seen_lists[tl_id] = node
                    blocks.append(node)
                seen_lists[tl_id].items.append(
                    ListItem(children=self._inlines_from_block(block))
                )
            else:
                state = block.userState()
                text = block.text()
                if state == _STATE_MATH_BLOCK:
                    raw = text.replace("\ufffc", "").strip(_LINE_SEP).strip()
                    blocks.append(MathBlock(latex=raw.replace(_LINE_SEP, "\n")))
                elif state == _STATE_FIGURE:
                    blocks.append(self._figure_from_stub(text))
                elif state == _STATE_TABLE:
                    # Legacy stub-based tables (from older documents).
                    blocks.append(self._table_from_stub(text))
                elif state == _STATE_RAW:
                    # Strip whichever prefix is present; supports
                    # documents saved before the typed prefixes existed.
                    raw = text
                    for prefix in _RAW_PREFIXES:
                        if raw.startswith(prefix):
                            raw = raw[len(prefix):]
                            break
                    # Restore the real newlines we substituted on render
                    # so the LaTeX serializer emits a well-formed verbatim
                    # / lstlisting / etc. environment.
                    raw = raw.replace(_LINE_SEP, "\n")
                    blocks.append(RawLatex(text=raw))
                else:
                    # Text blocks: determine the paragraph style from how
                    # the block CURRENTLY looks, not the stored state.
                    # When a user presses Enter after a heading the new
                    # block inherits the heading's font but its state
                    # stays unset (-1), and vice versa for manual format
                    # changes. Trusting the visible formatting keeps the
                    # PDF in sync with what the user sees on screen.
                    blocks.append(self._classify_text_block(block))
            block = block.next()
        return Document(children=blocks, meta=self._meta)

    # ---------- block rendering ----------

    def _render_block(self, cursor: QTextCursor, block) -> None:
        if isinstance(block, Title):
            cursor.setBlockFormat(_title_block_format())
            cursor.block().setUserState(_STATE_TITLE)
            for inline in block.children:
                self._insert_inline(cursor, inline, base_format=_title_char_format())
            return
        if isinstance(block, Author):
            cursor.setBlockFormat(_author_block_format())
            cursor.block().setUserState(_STATE_AUTHOR)
            for inline in block.children:
                self._insert_inline(cursor, inline, base_format=_author_char_format())
            return
        if isinstance(block, Abstract):
            cursor.setBlockFormat(_abstract_block_format())
            cursor.block().setUserState(_STATE_ABSTRACT)
            for inline in block.children:
                self._insert_inline(cursor, inline, base_format=_abstract_char_format())
            return
        if isinstance(block, Keywords):
            cursor.setBlockFormat(_keywords_block_format())
            cursor.block().setUserState(_STATE_KEYWORDS)
            for inline in block.children:
                self._insert_inline(cursor, inline, base_format=_keywords_char_format())
            return
        if isinstance(block, Frame):
            cursor.block().setUserState(_STATE_FRAME)
            cfmt = _frame_char_format()
            for inline in block.children:
                self._insert_inline(cursor, inline, base_format=cfmt)
            return
        if isinstance(block, Section):
            # level=0 represents \chapter; the rest map directly to
            # the QTextBlock's userState (which is what _classify_
            # text_block reads back).
            state = _STATE_CHAPTER if block.level == 0 else block.level
            cursor.block().setUserState(state)
            cfmt = _heading_char_format(block.level)
            for inline in block.children:
                self._insert_inline(cursor, inline, base_format=cfmt)
        elif isinstance(block, Paragraph):
            cursor.block().setUserState(_STATE_PARAGRAPH)
            bfmt = QTextBlockFormat()
            bfmt.setAlignment(_QT_ALIGNMENT.get(block.alignment, Qt.AlignLeft))
            cursor.setBlockFormat(bfmt)
            # Pass an explicit body char format so every Text run
            # carries Georgia + body_font_pt as its baseline. Without
            # this, _insert_inline emits Text fragments with an empty
            # font, which inherits whatever the cursor's current font
            # happens to be — which can be the previous block's font
            # (a heading, a code span, the last block of a different
            # body size) and produces visibly mismatched paragraphs
            # when the user presses Enter to start a new one.
            body_fmt = self._body_char_format()
            for inline in block.children:
                self._insert_inline(cursor, inline, base_format=body_fmt)
        elif isinstance(block, MathBlock):
            cursor.block().setUserState(_STATE_MATH_BLOCK)
            self._insert_math_image(cursor, block.latex)
            visible = block.latex.replace("\n", _LINE_SEP)
            cursor.insertText(visible, _math_block_char_format())
        elif isinstance(block, ListNode):
            lfmt = QTextListFormat()
            lfmt.setStyle(QTextListFormat.ListDecimal if block.ordered
                          else QTextListFormat.ListDisc)
            # Capture the QTextList from createList(); cursor.currentList()
            # returns None right after an insertBlock, which crashed the
            # previous implementation on every list with more than one item.
            text_list = None
            for item in block.items:
                if text_list is None:
                    text_list = cursor.createList(lfmt)
                else:
                    cursor.insertBlock(QTextBlockFormat(), QTextCharFormat())
                    text_list.add(cursor.block())
                cursor.block().setUserState(_STATE_PARAGRAPH)
                for inline in item.children:
                    self._insert_inline(cursor, inline)
        elif isinstance(block, Figure):
            self._insert_figure_widget(cursor, block)
        elif isinstance(block, Table):
            self._insert_table_widget(cursor, block)
        elif isinstance(block, RawLatex):
            # Pick the background colour from the content so code
            # listings, bibliography blocks and generic raw LaTeX are
            # each immediately recognisable. The block's userState +
            # background style already says "this is raw LaTeX", so we
            # don't prepend a "[RAW] " / "[CODE] " label any more — it
            # was developer noise on screen.
            cursor.block().setUserState(_STATE_RAW)
            text = block.text
            if "\\begin{lstlisting}" in text or "\\begin{verbatim}" in text:
                cursor.setBlockFormat(_code_block_format())
                color = "#1a3a8c"      # slate / blue
            elif "\\begin{thebibliography}" in text:
                cursor.setBlockFormat(_bibliography_block_format())
                color = "#6a1b9a"      # purple
            else:
                cursor.setBlockFormat(_raw_block_format())
                color = "#b71c1c"      # red
            # Multi-line content: substitute U+2028 for '\n' so Qt keeps
            # every line in the same block; the readback undoes it.
            visible = text.replace("\n", _LINE_SEP)
            cursor.insertText(visible, _typed_stub_char_format(color))

    # ---------- figure thumbnail ----------

    _THUMB_MAX_WIDTH = 320
    _THUMB_MAX_HEIGHT = 200

    def _insert_figure_thumbnail(self, cursor: QTextCursor, img_path: str) -> None:
        """Try to load the image and insert a scaled thumbnail below the stub."""
        resolved = self._resolve_image_path(img_path)
        if resolved is None:
            return
        img = QImage(str(resolved))
        if img.isNull():
            return
        # Scale to thumbnail size preserving aspect ratio.
        if img.width() > self._THUMB_MAX_WIDTH or img.height() > self._THUMB_MAX_HEIGHT:
            img = img.scaled(
                self._THUMB_MAX_WIDTH, self._THUMB_MAX_HEIGHT,
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
        url = QUrl.fromLocalFile(str(resolved))
        self._edit.document().addResource(2, url, img)  # 2 = ImageResource
        cursor.insertText("\n")
        img_fmt = QTextImageFormat()
        img_fmt.setName(url.toString())
        img_fmt.setWidth(img.width())
        img_fmt.setHeight(img.height())
        cursor.insertImage(img_fmt)

    def _insert_table_widget(self, cursor: QTextCursor, table: Table) -> None:
        """Insert a Table model node as a real QTextTable in the editor."""
        nrows = len(table.rows) if table.rows else 1
        ncols = max((len(r) for r in table.rows), default=1) if table.rows else 1
        p = _palette(self._dark)
        tfmt = _make_table_format(ncols, dark=self._dark)
        tfmt.setProperty(_P_TABLE_CAPTION, table.caption or "")
        tfmt.setProperty(_P_TABLE_LABEL, table.label or "")
        tfmt.setProperty(_P_TABLE_ALIGNMENT, table.alignment or "")
        # Add an extra row for caption if present.
        has_caption = bool(table.caption)
        total_rows = nrows + (1 if has_caption else 0)
        qtable = cursor.insertTable(total_rows, ncols, tfmt)
        # Header row: bold accent colour on darker amber background.
        header_char = QTextCharFormat()
        header_char.setFontWeight(QFont.Bold)
        header_char.setForeground(QColor(p["table_header_fg"]))
        cell_char = QTextCharFormat()
        cell_char.setForeground(QColor(p["table_cell_fg"]))
        for r, row in enumerate(table.rows):
            for c in range(ncols):
                cell = qtable.cellAt(r, c)
                if r == 0:
                    cf = cell.format()
                    cf.setBackground(QColor(p["table_header_bg"]))
                    cell.setFormat(cf)
                cell_cursor = cell.firstCursorPosition()
                text = row[c] if c < len(row) else ""
                fmt = header_char if r == 0 else cell_char
                cell_cursor.insertText(text, fmt)
        if has_caption:
            # Merge all cells in the last row for the caption.
            qtable.mergeCells(nrows, 0, 1, ncols)
            cap_cell = qtable.cellAt(nrows, 0)
            cap_cursor = cap_cell.firstCursorPosition()
            cap_fmt = QTextCharFormat()
            cap_fmt.setFontItalic(True)
            cap_fmt.setForeground(QColor(p["table_caption_fg"]))
            cap_cursor.insertText(f"Caption: {table.caption}", cap_fmt)
        # Move the cursor past the table so subsequent content goes after it.
        cursor.movePosition(QTextCursor.End)

    def _insert_math_image(self, cursor: QTextCursor, latex: str) -> None:
        """Render math to a PNG and insert it into the document."""
        png_path = _render_math_image(latex, cache_dir=self._equations_dir)
        if png_path is None or not png_path.exists():
            return
        img = QImage(str(png_path))
        if img.isNull():
            return
        url = QUrl.fromLocalFile(str(png_path))
        self._edit.document().addResource(2, url, img)
        img_fmt = QTextImageFormat()
        img_fmt.setName(url.toString())
        img_fmt.setWidth(img.width())
        img_fmt.setHeight(img.height())
        cursor.insertImage(img_fmt)
        cursor.insertText(_LINE_SEP)

    def _insert_figure_widget(self, cursor: QTextCursor, figure: Figure) -> None:
        """Insert a Figure model node as a centered QTextTable with image,
        caption, and label rows."""
        has_caption = bool(figure.caption)
        has_label = bool(figure.label)
        total_rows = 1 + int(has_caption) + int(has_label)
        p = _palette(self._dark)
        tfmt = _make_figure_table_format(dark=self._dark)
        tfmt.setProperty(_P_FIGURE_PATH, figure.path or "")
        tfmt.setProperty(_P_FIGURE_LABEL, figure.label or "")
        tfmt.setProperty(_P_FIGURE_WIDTH, figure.width or "0.8\\textwidth")
        qtable = cursor.insertTable(total_rows, 1, tfmt)
        # Row 0: centered image.
        img_cursor = qtable.cellAt(0, 0).firstCursorPosition()
        bf = img_cursor.blockFormat()
        bf.setAlignment(Qt.AlignHCenter)
        img_cursor.setBlockFormat(bf)
        resolved = self._resolve_image_path(figure.path)
        if resolved is not None:
            img = QImage(str(resolved))
            if not img.isNull():
                max_w, max_h = 400, 300
                if img.width() > max_w or img.height() > max_h:
                    img = img.scaled(max_w, max_h, Qt.KeepAspectRatio,
                                     Qt.SmoothTransformation)
                url = QUrl.fromLocalFile(str(resolved))
                self._edit.document().addResource(2, url, img)
                img_fmt = QTextImageFormat()
                img_fmt.setName(url.toString())
                img_fmt.setWidth(img.width())
                img_fmt.setHeight(img.height())
                img_cursor.insertImage(img_fmt)
            else:
                img_cursor.insertText(
                    f"[Image not found: {figure.path}]",
                    _typed_stub_char_format("#999999"))
        else:
            img_cursor.insertText(
                f"[Image: {figure.path}]",
                _typed_stub_char_format("#999999"))
        # Row 1: caption (if present).
        row_idx = 1
        if has_caption:
            cap_cursor = qtable.cellAt(row_idx, 0).firstCursorPosition()
            bf = cap_cursor.blockFormat()
            bf.setAlignment(Qt.AlignHCenter)
            cap_cursor.setBlockFormat(bf)
            cap_fmt = QTextCharFormat()
            cap_fmt.setFontItalic(True)
            cap_fmt.setForeground(QColor(p["figure_caption_fg"]))
            cap_cursor.insertText(f"Figure: {figure.caption}", cap_fmt)
            row_idx += 1
        # Row 2: label (if present).
        if has_label:
            lbl_cursor = qtable.cellAt(row_idx, 0).firstCursorPosition()
            bf = lbl_cursor.blockFormat()
            bf.setAlignment(Qt.AlignHCenter)
            lbl_cursor.setBlockFormat(bf)
            lbl_fmt = QTextCharFormat()
            lbl_fmt.setForeground(QColor(p["table_caption_fg"]))
            f = lbl_fmt.font(); f.setPointSize(9); lbl_fmt.setFont(f)
            lbl_cursor.insertText(f"Label: {figure.label}", lbl_fmt)
        cursor.movePosition(QTextCursor.End)

    def _figure_from_qtexttable(self, qtable: QTextTable) -> Figure:
        """Read a Figure model back from its QTextTable representation."""
        tfmt = qtable.format()
        path = tfmt.property(_P_FIGURE_PATH) or ""
        label = tfmt.property(_P_FIGURE_LABEL) or None
        width = tfmt.property(_P_FIGURE_WIDTH) or "0.8\\textwidth"
        caption = ""
        # Caption is in a row after the image row; look for "Figure: " prefix.
        for r in range(1, qtable.rows()):
            cell_text = qtable.cellAt(r, 0).firstCursorPosition().block().text()
            if cell_text.startswith("Figure: "):
                caption = cell_text[len("Figure: "):]
                break
        return Figure(path=path, caption=caption, label=label or None, width=width)

    def _resolve_image_path(self, img_path: str) -> Path | None:
        """Resolve a figure path to an absolute file, checking common bases."""
        if not img_path:
            return None
        p = Path(img_path)
        if p.is_absolute() and p.exists():
            return p
        # Try relative to source dir.
        if self._source_dir:
            candidate = self._source_dir / p
            if candidate.exists():
                return candidate
        # Try relative to images scratch dir.
        candidate = self._images_dir / p
        if candidate.exists():
            return candidate
        return None

    # ---------- inline rendering ----------

    def _insert_inline(self, cursor: QTextCursor, node,
                       base_format: QTextCharFormat | None = None) -> None:
        if isinstance(node, Text):
            fmt = QTextCharFormat(base_format) if base_format else QTextCharFormat()
            f = fmt.font()
            if "bold" in node.marks: f.setBold(True)
            if "italic" in node.marks: f.setItalic(True)
            if "underline" in node.marks: f.setUnderline(True)
            if "strikethrough" in node.marks: f.setStrikeOut(True)
            if "smallcaps" in node.marks: f.setCapitalization(QFont.SmallCaps)
            if "code" in node.marks:
                f.setFamily("Consolas"); f.setStyleHint(QFont.Monospace)
            fmt.setFont(f)
            if "subscript" in node.marks:
                fmt.setVerticalAlignment(QTextCharFormat.AlignSubScript)
            elif "superscript" in node.marks:
                fmt.setVerticalAlignment(QTextCharFormat.AlignSuperScript)
            cursor.insertText(node.text, fmt)
        elif isinstance(node, MathInline):
            cursor.insertText(node.latex, _math_inline_format(node.latex))
        elif isinstance(node, Link):
            text = "".join(c.text for c in node.children if isinstance(c, Text)) or node.url
            cursor.insertText(text, _link_format(node.url))
        elif isinstance(node, Footnote):
            text = "".join(c.text for c in node.children if isinstance(c, Text)) or "footnote"
            cursor.insertText(text, _footnote_format(text))
        elif isinstance(node, Citation):
            payload = f"{','.join(node.keys)}|{node.style}"
            display = f"[{','.join(node.keys)}]"
            cursor.insertText(display, _citation_format(payload))
        elif isinstance(node, CrossRef):
            payload = f"{node.label}|{node.kind}"
            display = f"<{node.kind}:{node.label}>"
            cursor.insertText(display, _crossref_format(payload))
        elif isinstance(node, InlineRaw):
            cursor.insertText(node.latex, _raw_inline_format(node.latex))
        elif isinstance(node, Highlight):
            fmt = _highlight_format(node.color)
            for child in node.children:
                if isinstance(child, Text):
                    child_fmt = QTextCharFormat(fmt)
                    f = child_fmt.font()
                    if "bold" in child.marks: f.setBold(True)
                    if "italic" in child.marks: f.setItalic(True)
                    if "underline" in child.marks: f.setUnderline(True)
                    if "strikethrough" in child.marks: f.setStrikeOut(True)
                    if "smallcaps" in child.marks: f.setCapitalization(QFont.SmallCaps)
                    if "code" in child.marks:
                        f.setFamily("Consolas"); f.setStyleHint(QFont.Monospace)
                    child_fmt.setFont(f)
                    cursor.insertText(child.text, child_fmt)
                else:
                    self._insert_inline(cursor, child, fmt)
        elif isinstance(node, Comment):
            fmt = _comment_format(node.note, node.author,
                                  node.timestamp, node.resolved)
            for child in node.children:
                if isinstance(child, Text):
                    child_fmt = QTextCharFormat(fmt)
                    f = child_fmt.font()
                    if "bold" in child.marks: f.setBold(True)
                    if "italic" in child.marks: f.setItalic(True)
                    child_fmt.setFont(f)
                    cursor.insertText(child.text, child_fmt)
                else:
                    self._insert_inline(cursor, child, fmt)

    # ---------- model rebuilding ----------

    def _inlines_from_block(self, block) -> list:
        out: list = []
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                fmt = frag.charFormat()
                text = frag.text()
                if fmt.property(_P_MATH):
                    out.append(MathInline(latex=text))
                elif fmt.property(_P_LINK):
                    out.append(Link(url=fmt.property(_P_LINK), children=[Text(text=text)]))
                elif fmt.property(_P_FOOTNOTE):
                    out.append(Footnote(children=[Text(text=fmt.property(_P_FOOTNOTE))]))
                elif fmt.property(_P_CITATION):
                    raw = fmt.property(_P_CITATION)
                    keys, _, style = raw.partition("|")
                    out.append(Citation(keys=[k for k in keys.split(",") if k],
                                        style=style or "cite"))
                elif fmt.property(_P_CROSSREF):
                    raw = fmt.property(_P_CROSSREF)
                    label, _, kind = raw.partition("|")
                    out.append(CrossRef(label=label, kind=kind or "ref"))
                elif fmt.property(_P_RAW):
                    out.append(InlineRaw(latex=fmt.property(_P_RAW)))
                elif fmt.property(_P_HIGHLIGHT):
                    color = fmt.property(_P_HIGHLIGHT)
                    marks: list = []
                    f = fmt.font()
                    if f.bold(): marks.append("bold")
                    if f.italic(): marks.append("italic")
                    if f.underline(): marks.append("underline")
                    if f.strikeOut(): marks.append("strikethrough")
                    if f.capitalization() == QFont.SmallCaps: marks.append("smallcaps")
                    if f.styleHint() == QFont.Monospace and f.family().lower() == "consolas":
                        marks.append("code")
                    out.append(Highlight(
                        children=[Text(text=text, marks=marks)],
                        color=color,
                    ))
                elif fmt.property(_P_COMMENT):
                    raw = fmt.property(_P_COMMENT)
                    parts = raw.split("|")
                    note = parts[0] if len(parts) > 0 else ""
                    author = parts[1] if len(parts) > 1 else ""
                    timestamp = parts[2] if len(parts) > 2 else ""
                    resolved = (parts[3] == "1") if len(parts) > 3 else False
                    out.append(Comment(
                        children=[Text(text=text)],
                        note=note,
                        author=author,
                        timestamp=timestamp,
                        resolved=resolved,
                    ))
                else:
                    marks: list = []
                    f = fmt.font()
                    if f.bold(): marks.append("bold")
                    if f.italic(): marks.append("italic")
                    if f.underline(): marks.append("underline")
                    if f.strikeOut(): marks.append("strikethrough")
                    if f.capitalization() == QFont.SmallCaps: marks.append("smallcaps")
                    if f.styleHint() == QFont.Monospace and f.family().lower() == "consolas":
                        marks.append("code")
                    va = fmt.verticalAlignment()
                    if va == QTextCharFormat.AlignSubScript: marks.append("subscript")
                    elif va == QTextCharFormat.AlignSuperScript: marks.append("superscript")
                    out.append(Text(text=text, marks=marks))
            it += 1
        return out

    @staticmethod
    def _strip_implicit_marks(children: list, marks: list[str]) -> list:
        """Remove marks that are *implied* by the surrounding paragraph
        style (e.g. Headings are bold by definition, so a Heading's child
        Text shouldn't also carry a "bold" mark — otherwise the serializer
        would wrap it in `\\textbf{...}` and the next reparse would see
        literal LaTeX text).
        """
        for c in children:
            if isinstance(c, Text) and c.marks:
                c.marks = [m for m in c.marks if m not in marks]
        return children

    def _classify_text_block(self, block):
        """Build the right Block model for `block` based on what it LOOKS
        like in the editor right now: alignment, font weight, font size,
        italic. The stored userState is used as a tie-breaker only.

        Heuristics tuned to the styles applied by apply_heading():
          * Title      = centered, bold, ≥ ~24pt (base size, pre-zoom)
          * Author     = centered, italic, ~14pt
          * Heading N  = bold, point size within ~3pt of the canonical size
          * Paragraph  = anything else, alignment preserved
        """
        state = block.userState()
        align_flag = block.blockFormat().alignment() & Qt.AlignHorizontal_Mask
        align_name = _ALIGNMENT_FROM_QT.get(align_flag, "justify")
        children = self._inlines_from_block(block)

        # State-driven dispatch for paragraph styles that aren't visually
        # distinguishable from Body (Abstract / Keywords share the body
        # font and only differ by indentation/italic).
        if state == _STATE_ABSTRACT:
            return Abstract(children=children)
        if state == _STATE_KEYWORDS:
            # Italic is implied by the Keywords style.
            return Keywords(children=self._strip_implicit_marks(children, ["italic"]))
        if state == _STATE_CHAPTER:
            return Section(level=0, children=self._strip_implicit_marks(children, ["bold"]))
        if state == _STATE_FRAME:
            return Frame(children=self._strip_implicit_marks(children, ["bold"]))
        if 1 <= state <= 5:
            return Section(level=state,
                           children=self._strip_implicit_marks(children, ["bold"]))

        # Empty block: no fragments to inspect — fall back to state.
        it = block.begin()
        if it.atEnd():
            if state == _STATE_TITLE: return Title(children=children)
            if state == _STATE_AUTHOR: return Author(children=children)
            return Paragraph(children=children, alignment=align_name)

        # Note: bold/italic that come from the *style itself* are stripped
        # below; user-applied bold/italic ON TOP of the style is still kept
        # because it would have been recorded in the QTextCharFormat as
        # explicit weight / italic above the style's defaults.

        fmt = it.fragment().charFormat()
        f = fmt.font()
        size = f.pointSizeF()
        bold = f.bold()
        italic = f.italic()
        # Normalise by zoom so heading detection survives the user dragging
        # the zoom slider.
        zoom = self._zoom_percent / 100 if self._zoom_percent else 1.0
        base = size / zoom if zoom > 0 else size

        # Title: large + bold + centered (with state hint relaxes the size threshold).
        if align_flag == Qt.AlignHCenter and bold and (base >= 24 or state == _STATE_TITLE):
            return Title(children=self._strip_implicit_marks(children, ["bold"]))

        # Author: centered, italic, small-ish.
        if align_flag == Qt.AlignHCenter and italic and (base <= 17 or state == _STATE_AUTHOR):
            return Author(children=self._strip_implicit_marks(children, ["italic"]))

        # Heading: bold + size near one of the canonical heading sizes.
        if bold and base >= 12:
            best_level: int | None = None
            best_diff = 99.0
            for level, expected in _HEADING_FONT_SIZES.items():
                d = abs(base - expected)
                if d < best_diff:
                    best_diff = d; best_level = level
            # 3pt tolerance — generous enough to absorb minor user-typed
            # changes without misclassifying body text.
            if best_level is not None and best_diff < 3:
                return Section(level=best_level,
                               children=self._strip_implicit_marks(children, ["bold"]))

        return Paragraph(children=children, alignment=align_name)

    def _alignment_of(self, block) -> str:
        # QTextBlockFormat.alignment() returns a Qt.AlignmentFlag bitmask;
        # mask to the horizontal portion before looking up.
        horiz = block.blockFormat().alignment() & Qt.AlignHorizontal_Mask
        for flag, name in _ALIGNMENT_FROM_QT.items():
            if horiz == flag:
                return name
        return "left"

    def _figure_from_stub(self, text: str) -> Figure:
        # Strip the trailing image object char (U+FFFC) Qt inserts for
        # the thumbnail and any trailing newlines.
        body = text.rstrip("\n\ufffc")
        # Legacy format: "[FIGURE] path | caption | label | width".
        if body.startswith(_FIGURE_PREFIX):
            legacy = body[len(_FIGURE_PREFIX):]
            parts = legacy.split("|")
            while len(parts) < 4: parts.append("")
            return Figure(path=parts[0], caption=parts[1],
                          label=parts[2] or None,
                          width=parts[3] or "0.8\\textwidth")
        # New format: path on the first line, then Caption/Label/Width
        # meta lines. _split_stub_meta peels the meta lines off the end.
        lines, meta = _split_stub_meta(body)
        path = lines[0] if lines else ""
        return Figure(
            path=path,
            caption=meta.get("Caption", ""),
            label=(meta.get("Label", "") or None),
            width=meta.get("Width", "") or "0.8\\textwidth",
        )

    def _table_from_stub(self, text: str) -> Table:
        # Legacy format: "[TABLE] rows || cap | label | align".
        if text.startswith(_TABLE_PREFIX):
            legacy = text[len(_TABLE_PREFIX):]
            rows_str, sep, meta = legacy.partition("||")
            if rows_str:
                row_sources = rows_str.split(_LINE_SEP)
                if len(row_sources) == 1 and "\n" in rows_str:
                    row_sources = rows_str.split("\n")
                rows = [r.split("\t") for r in row_sources]
            else:
                rows = []
            parts = meta.split("|") if sep else []
            while len(parts) < 3: parts.append("")
            return Table(rows=rows, caption=parts[0],
                         label=parts[1] or None, alignment=parts[2])
        # New format: rows (TAB-separated cells, U+2028-separated rows)
        # followed by Caption/Label/Alignment meta lines.
        lines, meta = _split_stub_meta(text)
        rows = [r.split("\t") for r in lines] if lines else []
        return Table(
            rows=rows,
            caption=meta.get("Caption", ""),
            label=(meta.get("Label", "") or None),
            alignment=meta.get("Alignment", ""),
        )

    def _table_from_qtexttable(self, qtable: QTextTable) -> Table:
        """Extract a Table model node from a live QTextTable widget."""
        tfmt = qtable.format()
        caption = tfmt.property(_P_TABLE_CAPTION) or ""
        label = tfmt.property(_P_TABLE_LABEL) or None
        alignment = tfmt.property(_P_TABLE_ALIGNMENT) or ""
        nrows = qtable.rows()
        ncols = qtable.columns()
        # If last row is a merged caption row, exclude it from data rows.
        has_caption_row = False
        if caption and nrows > 1:
            cell = qtable.cellAt(nrows - 1, 0)
            text = cell.firstCursorPosition().block().text()
            if text.startswith("Caption: "):
                has_caption_row = True
        data_rows = nrows - (1 if has_caption_row else 0)
        rows: list[list[str]] = []
        for r in range(data_rows):
            row: list[str] = []
            for c in range(ncols):
                cell = qtable.cellAt(r, c)
                row.append(cell.firstCursorPosition().block().text())
            rows.append(row)
        return Table(rows=rows, caption=caption, label=label,
                     alignment=alignment)

    # ---------- formatting actions (called by mainwindow) ----------

    def apply_heading(self, level: int) -> None:
        """Apply a paragraph style by level code:
            -1 = Title,  -2 = Author,  -3 = Abstract,  -4 = Keywords,
            -5 = Chapter (\\chapter — only valid in report/book/memoir),
            -6 = Frame (\\begin{frame} — only valid in beamer),
             0 = Body,  1..5 = Heading 1..5."""
        cursor = self._edit.textCursor()
        block = cursor.block()
        block_cursor = QTextCursor(block)
        block_cursor.select(QTextCursor.BlockUnderCursor)
        if level == -1:
            block.setUserState(_STATE_TITLE)
            QTextCursor(block).setBlockFormat(_title_block_format())
            block_cursor.mergeCharFormat(_title_char_format())
        elif level == -2:
            block.setUserState(_STATE_AUTHOR)
            QTextCursor(block).setBlockFormat(_author_block_format())
            block_cursor.mergeCharFormat(_author_char_format())
        elif level == -3:
            block.setUserState(_STATE_ABSTRACT)
            QTextCursor(block).setBlockFormat(_abstract_block_format())
            block_cursor.setCharFormat(_abstract_char_format())
        elif level == -4:
            block.setUserState(_STATE_KEYWORDS)
            QTextCursor(block).setBlockFormat(_keywords_block_format())
            block_cursor.setCharFormat(_keywords_char_format())
        elif level == -5:
            block.setUserState(_STATE_CHAPTER)
            QTextCursor(block).setBlockFormat(QTextBlockFormat())
            block_cursor.mergeCharFormat(_heading_char_format(0))
        elif level == -6:
            block.setUserState(_STATE_FRAME)
            QTextCursor(block).setBlockFormat(QTextBlockFormat())
            block_cursor.mergeCharFormat(_frame_char_format())
        elif level >= 1:
            block.setUserState(level)
            QTextCursor(block).setBlockFormat(QTextBlockFormat())
            block_cursor.mergeCharFormat(_heading_char_format(level))
        else:
            block.setUserState(_STATE_PARAGRAPH)
            QTextCursor(block).setBlockFormat(QTextBlockFormat())
            # Use setCharFormat (not merge) so EVERY font property —
            # family, size, weight, italic, smallcaps, super/subscript —
            # gets wiped back to the document defaults. Anything less and a
            # paragraph carrying an inherited heading font would still
            # render larger than its neighbours.
            fmt = QTextCharFormat()
            f = QFont("Georgia")
            f.setPointSizeF(self._body_font_pt * (self._zoom_percent / 100))
            fmt.setFont(f)
            block_cursor.setCharFormat(fmt)
        self._on_text_changed()

    def apply_alignment(self, name: str) -> None:
        """name ∈ {"left", "center", "right", "justify"}."""
        flag = _QT_ALIGNMENT.get(name, Qt.AlignLeft)
        cursor = self._edit.textCursor()
        bfmt = cursor.blockFormat()
        bfmt.setAlignment(flag)
        cursor.setBlockFormat(bfmt)
        self._on_text_changed()

    def current_alignment(self) -> str:
        return self._alignment_of(self._edit.textCursor().block())

    # ----- zoom -----

    def body_font_pt(self) -> int:
        return self._body_font_pt

    def is_dark(self) -> bool:
        return self._dark

    def set_dark(self, dark: bool) -> None:
        """Switch the colour theme used by table / figure block
        widgets. Rebuilds the document so existing tables and
        figures get re-rendered with the new palette — their cell
        backgrounds and text colours otherwise remain stuck on the
        theme they were created under, which is what made tables
        invisible in dark mode (light text on light-orange cells).

        Preserves cursor position and scroll offset across the
        rebuild so the user isn't bounced to the top of the
        document when they toggle the theme."""
        dark = bool(dark)
        if dark == self._dark:
            return
        self._dark = dark
        # Snapshot, rebuild, restore.
        cursor_pos = self._edit.textCursor().position()
        scroll_y = self._edit.verticalScrollBar().value()
        doc = self.get_document()
        self.set_document(doc)
        # Restore cursor + scroll.
        new_cursor = self._edit.textCursor()
        new_cursor.setPosition(min(cursor_pos,
                                   self._edit.document().characterCount() - 1))
        self._edit.setTextCursor(new_cursor)
        self._edit.verticalScrollBar().setValue(scroll_y)

    def is_spell_check_enabled(self) -> bool:
        return self._spell_highlighter.is_enabled()

    def set_spell_check_enabled(self, enabled: bool) -> None:
        self._spell_highlighter.set_enabled(enabled)

    def _body_char_format(self) -> QTextCharFormat:
        """The baseline char format every body Text fragment uses on
        render. Carrying it explicitly (instead of letting Qt inherit
        from the cursor) keeps fonts consistent when the user starts a
        new paragraph after a heading or a code span. Honours the
        current zoom so scaled-up text on screen still matches the
        body when the user presses Enter and types."""
        fmt = QTextCharFormat()
        f = QFont("Georgia")
        zoom = self._zoom_percent / 100 if self._zoom_percent else 1.0
        f.setPointSizeF(self._body_font_pt * zoom)
        fmt.setFont(f)
        return fmt

    def set_body_font_pt(self, pt: int) -> None:
        """Change the default body text size and re-apply it to every
        Paragraph block, so existing body text grows/shrinks with the
        new default. Headings keep their own sizes."""
        pt = max(6, min(72, int(pt)))
        if pt == self._body_font_pt:
            return
        self._body_font_pt = pt
        # Sync the document meta so the serialized LaTeX preamble
        # matches what the editor actually shows. Without this, the
        # toolbar font-size combo changed the on-screen size but the
        # exported / previewed .tex kept the dialog's old size.
        self._meta.body_font_pt = pt
        self._building = True
        try:
            doc = self._edit.document()
            block = doc.firstBlock()
            zoom = self._zoom_percent / 100 if self._zoom_percent else 1.0
            while block.isValid():
                state = block.userState()
                if state in (0, -1):    # Paragraph or uninitialised
                    bc = QTextCursor(block)
                    bc.select(QTextCursor.BlockUnderCursor)
                    fmt = QTextCharFormat()
                    f = QFont("Georgia")
                    f.setPointSizeF(pt * zoom)
                    fmt.setFont(f)
                    bc.setCharFormat(fmt)
                block = block.next()
        finally:
            self._building = False
        self._on_text_changed()

    def zoom_percent(self) -> int:
        return self._zoom_percent

    def set_zoom_percent(self, percent: int) -> None:
        percent = max(25, min(400, int(percent)))
        if percent == self._zoom_percent:
            return
        # QTextEdit.zoomIn only scales the WIDGET's default font, which has
        # no effect on text that carries an explicit character-format point
        # size (every heading, every Title, every formatted run). To make
        # zoom actually grow the text on screen we walk every fragment and
        # rescale its point size by the ratio of new-to-old zoom.
        prev_factor = self._zoom_percent / 100 if self._zoom_percent else 1.0
        new_factor = percent / 100
        ratio = new_factor / prev_factor

        self._building = True   # suppress textChanged → debounced recompile
        try:
            doc = self._edit.document()
            block = doc.firstBlock()
            while block.isValid():
                it = block.begin()
                while not it.atEnd():
                    frag = it.fragment()
                    if frag.isValid():
                        fmt = frag.charFormat()
                        f = fmt.font()
                        size = f.pointSizeF()
                        if size > 0:
                            f.setPointSizeF(size * ratio)
                            fmt.setFont(f)
                            c = QTextCursor(doc)
                            c.setPosition(frag.position())
                            c.setPosition(frag.position() + frag.length(),
                                          QTextCursor.KeepAnchor)
                            c.mergeCharFormat(fmt)
                    it += 1
                block = block.next()
            # Scale the widget's default font too so freshly-typed text uses
            # the same scale as the surrounding content.
            wf = self._edit.font()
            if wf.pointSizeF() > 0:
                wf.setPointSizeF(wf.pointSizeF() * ratio)
                self._edit.setFont(wf)
        finally:
            self._building = False

        self._zoom_percent = percent
        # Page card grows/shrinks proportionally so paper proportions are
        # preserved. The document margin also scales so the number of
        # characters per line stays constant — zoom should make everything
        # bigger uniformly, not reflow the text.
        page = page_sizes.by_code(self._meta.page_size)
        scaled_w = round(page.width_px * percent / 100)
        scaled_h = round(page.height_px * percent / 100)
        self._page.setFixedWidth(scaled_w)
        self._edit.set_page_size_px(scaled_w, scaled_h)
        self._edit.document().setDocumentMargin(
            self._base_doc_margin * percent / 100)
        self._resize_to_document()

    def set_fit_to_width(self, enabled: bool) -> None:
        self._fit_to_width = enabled
        if enabled:
            self._apply_fit_to_width()

    def fit_to_width(self) -> bool:
        return self._fit_to_width

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_to_width:
            self._fit_debounce.start()

    def _apply_fit_to_width(self) -> None:
        if not self._fit_to_width:
            return
        page = page_sizes.by_code(self._meta.page_size)
        viewport_w = self._scroll.viewport().width()
        # Leave 48px padding on each side for the desk margins.
        available = viewport_w - 48
        if available < 100:
            return
        target_pct = max(25, min(300, round(available / page.width_px * 100)))
        # Snap to 5% grid to match slider granularity.
        target_pct = 5 * round(target_pct / 5)
        if target_pct == self._zoom_percent:
            return
        self.set_zoom_percent(target_pct)
        self.zoomChanged.emit(target_pct)

    def toggle_mark(self, mark: str) -> None:
        fmt = QTextCharFormat()
        f = self._edit.currentFont()
        if mark == "bold":
            fmt.setFontWeight(QFont.Normal if f.bold() else QFont.Bold)
        elif mark == "italic":
            fmt.setFontItalic(not f.italic())
        elif mark == "underline":
            fmt.setFontUnderline(not f.underline())
        elif mark == "strikethrough":
            fmt.setFontStrikeOut(not f.strikeOut())
        elif mark == "code":
            f2 = QFont("Consolas") if f.family().lower() != "consolas" else QFont()
            if f2.family() == "": f2.setPointSize(12)
            f2.setStyleHint(QFont.Monospace if f.family().lower() != "consolas" else QFont.AnyStyle)
            fmt.setFont(f2)
        elif mark == "smallcaps":
            new_cap = (QFont.MixedCase if f.capitalization() == QFont.SmallCaps else QFont.SmallCaps)
            f3 = QFont(f); f3.setCapitalization(new_cap); fmt.setFont(f3)
        elif mark == "subscript":
            current = self._edit.currentCharFormat().verticalAlignment()
            fmt.setVerticalAlignment(
                QTextCharFormat.AlignNormal if current == QTextCharFormat.AlignSubScript
                else QTextCharFormat.AlignSubScript)
        elif mark == "superscript":
            current = self._edit.currentCharFormat().verticalAlignment()
            fmt.setVerticalAlignment(
                QTextCharFormat.AlignNormal if current == QTextCharFormat.AlignSuperScript
                else QTextCharFormat.AlignSuperScript)
        self._merge_format(fmt)

    def clear_formatting(self) -> None:
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        fmt = QTextCharFormat()
        f = QFont(); f.setPointSize(12); fmt.setFont(f)
        cursor.setCharFormat(fmt)

    def insert_inline_math(self) -> None:
        latex, ok = QInputDialog.getText(self, "Insert inline math", "LaTeX:")
        if ok and latex:
            self.insert_inline_math_with(latex)

    def insert_inline_math_with(self, latex: str) -> None:
        """Insert the given LaTeX as inline math without prompting. Used
        by the symbol picker so a click on a glyph drops the symbol in
        immediately."""
        if not latex:
            return
        self._edit.textCursor().insertText(latex, _math_inline_format(latex))

    def insert_raw_inline_with(self, latex: str) -> None:
        """Insert the given LaTeX verbatim at the cursor (no $...$ wrap).
        Used for text-mode macros like \\Kstroke that wouldn't render
        correctly inside an inline math span and for round-tripping
        unknown commands captured from imported .tex files."""
        if not latex:
            return
        self._edit.textCursor().insertText(latex, _raw_inline_format(latex))

    def insert_math_block(self) -> None:
        latex, ok = QInputDialog.getMultiLineText(self, "Insert math block", "LaTeX:")
        if ok and latex.strip():
            self.insert_math_block_with(latex)

    def insert_math_block_with(self, latex: str) -> None:
        """Insert a display math block at the cursor without prompting.
        Used by the equation builder so multi-line templates drop in
        directly."""
        if not latex.strip():
            return
        c = self._edit.textCursor()
        c.insertBlock()
        c.block().setUserState(_STATE_MATH_BLOCK)
        c.setBlockFormat(QTextBlockFormat())
        self._insert_math_image(c, latex)
        c.insertText(latex.replace("\n", _LINE_SEP), _math_block_char_format())
        c.insertBlock(); c.block().setUserState(_STATE_PARAGRAPH)

    def insert_bullet_list(self) -> None:
        self._edit.textCursor().createList(QTextListFormat.ListDisc)

    def insert_numbered_list(self) -> None:
        self._edit.textCursor().createList(QTextListFormat.ListDecimal)

    def insert_link(self) -> None:
        url, ok = QInputDialog.getText(self, "Insert link", "URL:")
        if not ok or not url: return
        text, ok = QInputDialog.getText(self, "Link text", "Display text:", text=url)
        if not ok: return
        self._edit.textCursor().insertText(text or url, _link_format(url))

    def insert_footnote(self) -> None:
        note, ok = QInputDialog.getMultiLineText(self, "Insert footnote", "Note text:")
        if ok and note.strip():
            self._edit.textCursor().insertText(note, _footnote_format(note))

    def insert_citation(self) -> None:
        keys, ok = QInputDialog.getText(self, "Insert citation",
                                        "BibTeX key(s), comma-separated:")
        if not ok or not keys.strip(): return
        style, ok = QInputDialog.getItem(self, "Citation style", "Command:",
                                         ["cite", "citep", "citet"], 0, False)
        if not ok: return
        payload = f"{keys.strip()}|{style}"
        display = f"[{keys.strip()}]"
        self._edit.textCursor().insertText(display, _citation_format(payload))

    def insert_crossref(self) -> None:
        label, ok = QInputDialog.getText(self, "Cross-reference", "Label:")
        if not ok or not label: return
        kind, ok = QInputDialog.getItem(self, "Reference type", "Command:",
                                        ["ref", "eqref", "pageref"], 0, False)
        if not ok: return
        self._edit.textCursor().insertText(
            f"<{kind}:{label}>", _crossref_format(f"{label}|{kind}"))

    # ---- review: highlight & comments ----

    def insert_highlight(self, color: str = "yellow") -> None:
        """Apply a highlight to the current selection."""
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            return
        fmt = _highlight_format(color)
        cursor.mergeCharFormat(fmt)
        self._edit.setTextCursor(cursor)

    def remove_highlight(self) -> None:
        """Remove highlight from the current selection."""
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            return
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(Qt.transparent))
        fmt.setProperty(_P_HIGHLIGHT, "")
        cursor.mergeCharFormat(fmt)
        self._edit.setTextCursor(cursor)

    def insert_comment(self, author: str = "") -> None:
        """Insert a reviewer comment on the selected text."""
        from datetime import datetime
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            return
        note, ok = QInputDialog.getMultiLineText(
            self, "New comment", "Comment:")
        if not ok or not note.strip():
            return
        ts = datetime.now().isoformat(timespec="seconds")
        fmt = _comment_format(note.strip(), author, ts, False)
        cursor.mergeCharFormat(fmt)
        self._edit.setTextCursor(cursor)

    def accept_comment(self) -> None:
        """Accept (resolve) the comment at cursor — remove comment
        formatting but keep the text."""
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        # Walk the selection and clear comment properties
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(Qt.transparent))
        fmt.setProperty(_P_COMMENT, "")
        fmt.setUnderlineStyle(QTextCharFormat.NoUnderline)
        fmt.setToolTip("")
        cursor.mergeCharFormat(fmt)
        self._edit.setTextCursor(cursor)

    def reject_comment(self) -> None:
        """Reject the comment at cursor — delete the commented text."""
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        cursor.removeSelectedText()

    def _find_comment_span(self, forward: bool = True) -> bool:
        """Move cursor to the next/previous comment span. Returns True
        if a comment was found."""
        doc = self._edit.document()
        cursor = self._edit.textCursor()
        pos = cursor.position()
        block = doc.begin() if forward else doc.end().previous()
        found_pos = -1
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.charFormat().property(_P_COMMENT):
                    frag_start = frag.position()
                    frag_end = frag_start + frag.length()
                    if forward and frag_start > pos:
                        found_pos = frag_start
                        break
                    elif not forward and frag_end < pos:
                        found_pos = frag_start
                it += 1
            if found_pos >= 0:
                break
            block = block.next() if forward else block.previous()
        if found_pos >= 0:
            cursor.setPosition(found_pos)
            cursor.movePosition(QTextCursor.NextCharacter,
                                QTextCursor.KeepAnchor, 1)
            # Extend to cover the full comment span
            while (cursor.position() < doc.characterCount() - 1):
                test = QTextCursor(cursor)
                test.movePosition(QTextCursor.NextCharacter)
                fmt = test.charFormat()
                if not fmt.property(_P_COMMENT):
                    break
                cursor.movePosition(QTextCursor.NextCharacter,
                                    QTextCursor.KeepAnchor)
            self._edit.setTextCursor(cursor)
            return True
        return False

    def next_comment(self) -> None:
        self._find_comment_span(forward=True)

    def prev_comment(self) -> None:
        self._find_comment_span(forward=False)

    def _on_image_received(self, path: str) -> None:
        """Slot for PagedTextEdit.imageReceived. Drops a Figure block at
        the cursor pointing at the freshly-saved image."""
        c = self._edit.textCursor()
        fig = Figure(path=path, caption="", label=None, width="0.6\\textwidth")
        self._insert_figure_widget(c, fig)
        self._on_text_changed()

    def insert_figure(self) -> None:
        path, ok = QInputDialog.getText(self, "Insert figure", "Image path:")
        if not ok or not path: return
        cap, _ = QInputDialog.getText(self, "Figure caption", "Caption:")
        label, _ = QInputDialog.getText(self, "Figure label", "Label (optional):")
        c = self._edit.textCursor()
        fig = Figure(path=path, caption=cap, label=label or None,
                     width="0.8\\textwidth")
        self._insert_figure_widget(c, fig)

    def insert_drawing(self) -> None:
        """Open the freehand drawing dialog. On OK, write the result
        into the document's images folder and drop a Figure block at
        the cursor pointing at it — same as a normal figure, just
        the source happens to be a sketch the user made in-app."""
        from .drawing_dialog import DrawingDialog
        dlg = DrawingDialog(self._images_dir, self)
        if dlg.exec() != QDialog.Accepted:
            return
        path = dlg.saved_path()
        if path is None:
            return
        cap, _ = QInputDialog.getText(
            self, "Drawing caption", "Caption (optional):")
        label, _ = QInputDialog.getText(
            self, "Drawing label", "Label (optional, for cross-references):")
        c = self._edit.textCursor()
        fig = Figure(path=str(path), caption=cap, label=label or None,
                     width="0.7\\textwidth")
        self._insert_figure_widget(c, fig)
        self._on_text_changed()

    def insert_table(self) -> None:
        rows, ok = QInputDialog.getInt(self, "Insert table", "Rows:", 3, 1, 50)
        if not ok: return
        cols, ok = QInputDialog.getInt(self, "Insert table", "Columns:", 3, 1, 20)
        if not ok: return
        cap, _ = QInputDialog.getText(self, "Caption", "Caption:")
        c = self._edit.textCursor()
        table = Table(rows=[["cell"] * cols for _ in range(rows)],
                      caption=cap, label=None, alignment="")
        self._insert_table_widget(c, table)

    # ---- table context menu & manipulation ----

    def _current_table(self) -> QTextTable | None:
        """Return the QTextTable under the cursor, or None."""
        return self._edit.textCursor().currentTable()

    def _show_context_menu(self, pos) -> None:
        menu = self._edit.createStandardContextMenu()
        # Spell-check suggestions for the word at the right-click. The
        # word boundary is found via Qt's WordUnderCursor selection;
        # if the cursor is in whitespace this just produces an empty
        # selection and we skip the suggestion block entirely.
        word_cursor = self._edit.cursorForPosition(pos)
        word_cursor.select(QTextCursor.WordUnderCursor)
        word = word_cursor.selectedText().strip()
        if word and self._spell_highlighter.is_misspelled(word):
            self._prepend_spell_suggestions(menu, word_cursor, word)
        qtable = self._current_table()
        if qtable is not None:
            menu.addSeparator()
            cursor = self._edit.textCursor()
            cell = qtable.cellAt(cursor)
            row, col = cell.row(), cell.column()

            menu.addAction("Insert row above",
                           lambda: self._table_insert_row(qtable, row))
            menu.addAction("Insert row below",
                           lambda: self._table_insert_row(qtable, row + 1))
            menu.addAction("Insert column left",
                           lambda: self._table_insert_col(qtable, col))
            menu.addAction("Insert column right",
                           lambda: self._table_insert_col(qtable, col + 1))
            menu.addSeparator()
            if qtable.rows() > 1:
                menu.addAction("Delete row",
                               lambda: self._table_delete_row(qtable, row))
            if qtable.columns() > 1:
                menu.addAction("Delete column",
                               lambda: self._table_delete_col(qtable, col))
        if self._extra_context_actions:
            menu.addSeparator()
            for label, callback in self._extra_context_actions:
                menu.addAction(label, callback)
        menu.exec(self._edit.viewport().mapToGlobal(pos))

    def _prepend_spell_suggestions(self, menu, word_cursor, word: str) -> None:
        """Insert spell-check suggestions at the top of the context
        menu for a misspelled `word`. Selecting a suggestion replaces
        the word in place; the "Add to dictionary" entry stops
        flagging it for the rest of the session."""
        suggestions = self._spell_highlighter.suggestions(word)
        # Capture the start/end of the word so the action callbacks
        # can replace it even if the user clicks elsewhere first.
        start = word_cursor.selectionStart()
        end = word_cursor.selectionEnd()
        existing_actions = menu.actions()
        first = existing_actions[0] if existing_actions else None

        def _replace_with(new_word: str):
            c = QTextCursor(self._edit.document())
            c.setPosition(start)
            c.setPosition(end, QTextCursor.KeepAnchor)
            # Preserve the existing char format of the word — bold,
            # italic, font — so the correction inherits the same
            # styling instead of falling back to a plain insert.
            fmt = c.charFormat()
            c.insertText(new_word, fmt)

        if suggestions:
            for s in suggestions:
                act = QAction(s, menu)
                act.triggered.connect(lambda checked=False, w=s: _replace_with(w))
                menu.insertAction(first, act)
        else:
            no_sug = QAction("(no suggestions)", menu)
            no_sug.setEnabled(False)
            menu.insertAction(first, no_sug)

        menu.insertSeparator(first)
        add_act = QAction(f"Add “{word}” to dictionary", menu)
        add_act.triggered.connect(
            lambda checked=False, w=word: self._spell_highlighter.add_to_dictionary(w))
        menu.insertAction(first, add_act)
        menu.insertSeparator(first)

    def _table_insert_row(self, qtable: QTextTable, at: int) -> None:
        qtable.insertRows(at, 1)

    def _table_insert_col(self, qtable: QTextTable, at: int) -> None:
        qtable.insertColumns(at, 1)
        # Update column width constraints so they stay even.
        ncols = qtable.columns()
        tfmt = qtable.format()
        constraints = [QTextLength(QTextLength.PercentageLength, 100 / ncols)
                       for _ in range(ncols)]
        tfmt.setColumnWidthConstraints(constraints)
        qtable.setFormat(tfmt)

    def _table_delete_row(self, qtable: QTextTable, at: int) -> None:
        qtable.removeRows(at, 1)

    def _table_delete_col(self, qtable: QTextTable, at: int) -> None:
        qtable.removeColumns(at, 1)
        ncols = qtable.columns()
        tfmt = qtable.format()
        constraints = [QTextLength(QTextLength.PercentageLength, 100 / ncols)
                       for _ in range(ncols)]
        tfmt.setColumnWidthConstraints(constraints)
        qtable.setFormat(tfmt)

    def insert_raw_latex(self) -> None:
        text, ok = QInputDialog.getMultiLineText(self, "Insert raw LaTeX",
                                                 "LaTeX (verbatim):")
        if not ok or not text.strip(): return
        self._insert_raw_block(text)

    def insert_code_block(self) -> None:
        """Insert a syntax-highlighted code listing (lstlisting) at the
        cursor. Wraps the user's content in \\begin{lstlisting}...
        \\end{lstlisting}; relies on the listings package + user's
        \\lstset configuration for frame / line numbers / colours."""
        text, ok = QInputDialog.getMultiLineText(
            self, "Insert code block", "Code:")
        if not ok or not text.strip(): return
        body = text.rstrip("\n")
        wrapped = f"\\begin{{lstlisting}}\n{body}\n\\end{{lstlisting}}"
        self._insert_raw_block(wrapped)

    def _insert_raw_block(self, latex: str) -> None:
        """Shared helper: drop a RawLatex block at the cursor with the
        right per-type colour based on the content. No "[RAW] " /
        "[CODE] " label is prepended — the coloured background and
        the userState already mark this as a raw block."""
        c = self._edit.textCursor()
        c.insertBlock()
        c.block().setUserState(_STATE_RAW)
        if "\\begin{lstlisting}" in latex or "\\begin{verbatim}" in latex:
            c.setBlockFormat(_code_block_format())
            color = "#1a3a8c"
        elif "\\begin{thebibliography}" in latex:
            c.setBlockFormat(_bibliography_block_format())
            color = "#6a1b9a"
        else:
            c.setBlockFormat(_raw_block_format())
            color = "#b71c1c"
        visible = latex.replace("\n", _LINE_SEP)
        c.insertText(visible, _typed_stub_char_format(color))
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
        c.block().setUserState(_STATE_PARAGRAPH)

    def insert_page_break(self) -> None:
        self._insert_raw_block(r"\newpage")

    def insert_multicol_region(self) -> None:
        """Insert a 2-column \\begin{multicols}{2}...\\end{multicols} block
        with placeholder text. Only the content inside the environment
        flows in two columns; the rest of the document stays one-column.
        For a whole-document two-column layout, use
        File > Document settings > Layout > Two-column document."""
        self._insert_raw_block(
            "\\begin{multicols}{2}\n"
            "Replace this paragraph with the content that should flow "
            "across two columns. Add as many paragraphs as you like — "
            "everything between \\begin{multicols} and \\end{multicols} "
            "is balanced into the two columns automatically.\n"
            "\\end{multicols}")

    def insert_horizontal_rule(self) -> None:
        self._insert_raw_block(r"\hrulefill")

    def current_heading_level(self) -> int:
        """Returns -1 = Title, -2 = Author, -3 = Abstract, -4 = Keywords,
        -5 = Chapter, -6 = Frame, 0 = Body, 1..5 = Heading,
        -99 = non-text block."""
        state = self._edit.textCursor().block().userState()
        if state == _STATE_TITLE: return -1
        if state == _STATE_AUTHOR: return -2
        if state == _STATE_ABSTRACT: return -3
        if state == _STATE_KEYWORDS: return -4
        if state == _STATE_CHAPTER: return -5
        if state == _STATE_FRAME: return -6
        if 1 <= state <= 5: return state
        if state == _STATE_PARAGRAPH: return 0
        return -99

    def is_mark_active(self, mark: str) -> bool:
        f = self._edit.currentFont()
        fmt = self._edit.currentCharFormat()
        if mark == "bold": return f.bold()
        if mark == "italic": return f.italic()
        if mark == "underline": return f.underline()
        if mark == "strikethrough": return f.strikeOut()
        if mark == "smallcaps": return f.capitalization() == QFont.SmallCaps
        if mark == "code": return f.family().lower() == "consolas"
        if mark == "subscript": return fmt.verticalAlignment() == QTextCharFormat.AlignSubScript
        if mark == "superscript": return fmt.verticalAlignment() == QTextCharFormat.AlignSuperScript
        return False

    # ---------- internals ----------

    def _merge_format(self, fmt: QTextCharFormat) -> None:
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self._edit.mergeCurrentCharFormat(fmt)

    def _on_text_changed(self) -> None:
        if self._building: return
        self._debounce.start()
        block = self._edit.textCursor().block()
        if block.userState() == _STATE_MATH_BLOCK:
            self._math_refresh.start()

    def _refresh_math_images(self) -> None:
        """Re-render math preview images for any math block whose LaTeX
        source has changed since the image was last generated."""
        if self._building:
            return
        doc = self._edit.document()
        block = doc.begin()
        while block.isValid():
            if block.userState() == _STATE_MATH_BLOCK:
                text = block.text()
                raw = text.replace("\ufffc", "").strip(_LINE_SEP).strip()
                latex = raw.replace(_LINE_SEP, "\n")
                if latex:
                    self._update_math_image_in_block(block, latex)
            block = block.next()

    def _update_math_image_in_block(self, block, latex: str) -> None:
        """Replace the existing math preview image in *block* with a
        freshly rendered one for *latex*."""
        png_path = _render_math_image(latex, cache_dir=self._equations_dir)
        if png_path is None or not png_path.exists():
            return
        img = QImage(str(png_path))
        if img.isNull():
            return
        url = QUrl.fromLocalFile(str(png_path))
        self._edit.document().addResource(2, url, img)
        # Walk fragments to find the existing image char (\ufffc) and
        # update its QTextImageFormat to point at the new PNG.
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.text() == "\ufffc":
                fmt = frag.charFormat()
                if fmt.isImageFormat():
                    img_fmt = fmt.toImageFormat()
                    if img_fmt.name() == url.toString():
                        return  # already up to date
                    img_fmt.setName(url.toString())
                    img_fmt.setWidth(img.width())
                    img_fmt.setHeight(img.height())
                    cursor = QTextCursor(block)
                    cursor.setPosition(frag.position())
                    cursor.setPosition(frag.position() + frag.length(),
                                       QTextCursor.KeepAnchor)
                    self._building = True
                    cursor.setCharFormat(img_fmt)
                    self._building = False
                    return
            it += 1


def _stub_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(10)
    fmt.setFont(f); fmt.setForeground(QColor("#444"))
    return fmt
