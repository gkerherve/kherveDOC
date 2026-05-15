"""WYSIWYG editor widget — QTextEdit driving the document model.

Per-block: user-state encodes node type (0=Paragraph, 1-5=Section, 99=MathBlock,
other sentinels for figure/table/raw whose body is stored as block text).

Inlines: special spans (math, link, footnote, citation, cross-ref) are stored
as text fragments with a custom char-format property holding the payload. The
visible text is the human-readable representation; serialization rebuilds the
LaTeX from the property.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import (
    QAction, QColor, QFont, QKeySequence, QTextBlockFormat, QTextCharFormat,
    QTextCursor, QTextListFormat,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QTextEdit,
    QVBoxLayout, QWidget,
)

from .model import (
    Citation, CrossRef, Document, DocMeta, Figure, Footnote, Link,
    List as ListNode, ListItem, MathBlock, MathInline, Paragraph, RawLatex,
    Section, Table, Text,
)


# ---- per-block user state encoding ----
_STATE_PARAGRAPH = 0
_STATE_MATH_BLOCK = 99
_STATE_FIGURE = 100
_STATE_TABLE = 101
_STATE_RAW = 102


# ---- char-format custom property ids ----
_P_MATH = QTextCharFormat.UserProperty + 1
_P_LINK = QTextCharFormat.UserProperty + 2     # value = url
_P_FOOTNOTE = QTextCharFormat.UserProperty + 3  # value = note text
_P_CITATION = QTextCharFormat.UserProperty + 4  # value = "key1,key2|style"
_P_CROSSREF = QTextCharFormat.UserProperty + 5  # value = "label|kind"


# ---- block payload storage (figures/tables/raw) ----
# Block-text holds a compact serialization the editor doesn't try to render
# visually beyond a one-line "stub". Format examples:
#   Figure: "[FIGURE] path | caption | label | width"
#   Table:  "[TABLE] rows-as-tsv-newline-separated || caption | label | alignment"
#   Raw:    raw LaTeX text on one or multiple lines (joined with \n).
_FIGURE_PREFIX = "[FIGURE] "
_TABLE_PREFIX = "[TABLE] "
_RAW_PREFIX = "[RAW] "


_HEADING_FONT_SIZES = {1: 22, 2: 18, 3: 15, 4: 13, 5: 12}


def _heading_char_format(level: int) -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont()
    f.setBold(True)
    f.setPointSize(_HEADING_FONT_SIZES.get(level, 12))
    fmt.setFont(f)
    return fmt


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


def _stub_block_format() -> QTextBlockFormat:
    bfmt = QTextBlockFormat()
    bfmt.setTopMargin(6); bfmt.setBottomMargin(6)
    bfmt.setBackground(QColor("#f5f5f7"))
    return bfmt


class DocumentEditor(QWidget):
    """Rich-text editor that maintains a bidirectional binding with Document."""

    documentChanged = Signal()  # debounced after the user stops typing

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._building = False

        # Header strip — title + author, always visible at the top of the
        # editor so users can edit the document metadata in place (these
        # become \title / \author / \maketitle in the LaTeX output).
        self._title_edit = QLineEdit(self)
        self._title_edit.setPlaceholderText("Document title")
        title_font = QFont(); title_font.setPointSize(22); title_font.setBold(True)
        self._title_edit.setFont(title_font)
        self._title_edit.setStyleSheet(
            "QLineEdit { border: none; background: transparent; padding: 4px 8px; }")

        self._author_edit = QLineEdit(self)
        self._author_edit.setPlaceholderText("Author")
        author_font = QFont(); author_font.setPointSize(13); author_font.setItalic(True)
        self._author_edit.setFont(author_font)
        self._author_edit.setStyleSheet(
            "QLineEdit { border: none; background: transparent; "
            "padding: 0 8px; color: #555; }")

        self._title_edit.textChanged.connect(self._on_meta_changed)
        self._author_edit.textChanged.connect(self._on_meta_changed)

        header = QFrame(self)
        header.setStyleSheet(
            "QFrame { background: #fafbfc; border-bottom: 1px solid #d0d4d8; }")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(2)
        header_layout.addWidget(self._title_edit)
        header_layout.addWidget(self._author_edit)

        self._edit = QTextEdit(self)
        self._edit.setAcceptRichText(False)
        f = QFont(); f.setPointSize(12)
        self._edit.setFont(f)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._edit, 1)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(450)
        self._debounce.timeout.connect(self.documentChanged)

        self._edit.textChanged.connect(self._on_text_changed)

        self._meta = DocMeta()

    # ---------- public ----------

    @property
    def text_edit(self) -> QTextEdit:
        return self._edit

    def meta(self) -> DocMeta:
        return self._meta

    def set_meta(self, meta: DocMeta) -> None:
        self._meta = meta
        self._sync_header_from_meta()
        self._on_text_changed()

    def _sync_header_from_meta(self) -> None:
        # Suppress signals while we set the text so we don't loop back into
        # _on_meta_changed and mark the document dirty during a load.
        self._title_edit.blockSignals(True)
        self._author_edit.blockSignals(True)
        self._title_edit.setText(self._meta.title)
        self._author_edit.setText(self._meta.author)
        self._title_edit.blockSignals(False)
        self._author_edit.blockSignals(False)

    def _on_meta_changed(self) -> None:
        if self._building:
            return
        self._meta.title = self._title_edit.text()
        self._meta.author = self._author_edit.text()
        self._debounce.start()

    def set_document(self, doc: Document) -> None:
        self._building = True
        try:
            self._meta = doc.meta
            self._sync_header_from_meta()
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
        block = qdoc.firstBlock()
        while block.isValid():
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
                    blocks.append(MathBlock(latex=text))
                elif state == _STATE_FIGURE:
                    blocks.append(self._figure_from_stub(text))
                elif state == _STATE_TABLE:
                    blocks.append(self._table_from_stub(text))
                elif state == _STATE_RAW:
                    raw = text[len(_RAW_PREFIX):] if text.startswith(_RAW_PREFIX) else text
                    blocks.append(RawLatex(text=raw))
                elif 1 <= state <= 5:
                    blocks.append(Section(level=state, children=self._inlines_from_block(block)))
                else:
                    blocks.append(Paragraph(children=self._inlines_from_block(block)))
            block = block.next()
        return Document(children=blocks, meta=self._meta)

    # ---------- block rendering ----------

    def _render_block(self, cursor: QTextCursor, block) -> None:
        if isinstance(block, Section):
            cursor.block().setUserState(block.level)
            cfmt = _heading_char_format(block.level)
            for inline in block.children:
                self._insert_inline(cursor, inline, base_format=cfmt)
        elif isinstance(block, Paragraph):
            cursor.block().setUserState(_STATE_PARAGRAPH)
            for inline in block.children:
                self._insert_inline(cursor, inline)
        elif isinstance(block, MathBlock):
            cursor.block().setUserState(_STATE_MATH_BLOCK)
            cursor.insertText(block.latex, _math_block_char_format())
        elif isinstance(block, ListNode):
            lfmt = QTextListFormat()
            lfmt.setStyle(QTextListFormat.ListDecimal if block.ordered
                          else QTextListFormat.ListDisc)
            first_item = True
            for item in block.items:
                if first_item:
                    cursor.createList(lfmt)
                    first_item = False
                else:
                    cursor.insertBlock(QTextBlockFormat(), QTextCharFormat())
                    cursor.currentList().add(cursor.block())
                cursor.block().setUserState(_STATE_PARAGRAPH)
                for inline in item.children:
                    self._insert_inline(cursor, inline)
        elif isinstance(block, Figure):
            cursor.block().setUserState(_STATE_FIGURE)
            cursor.setBlockFormat(_stub_block_format())
            label = block.label or ""
            stub = f"{_FIGURE_PREFIX}{block.path}|{block.caption}|{label}|{block.width}"
            cursor.insertText(stub, _stub_char_format())
        elif isinstance(block, Table):
            cursor.block().setUserState(_STATE_TABLE)
            cursor.setBlockFormat(_stub_block_format())
            label = block.label or ""
            # rows-as-tsv with \n between rows, '|' between metadata fields.
            rows_tsv = "\n".join("\t".join(r) for r in block.rows)
            stub = f"{_TABLE_PREFIX}{rows_tsv}||{block.caption}|{label}|{block.alignment}"
            cursor.insertText(stub, _stub_char_format())
        elif isinstance(block, RawLatex):
            cursor.block().setUserState(_STATE_RAW)
            cursor.setBlockFormat(_stub_block_format())
            cursor.insertText(_RAW_PREFIX + block.text, _stub_char_format())

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

    def _figure_from_stub(self, text: str) -> Figure:
        body = text[len(_FIGURE_PREFIX):] if text.startswith(_FIGURE_PREFIX) else text
        parts = body.split("|")
        while len(parts) < 4: parts.append("")
        return Figure(path=parts[0], caption=parts[1], label=parts[2] or None,
                      width=parts[3] or "0.8\\textwidth")

    def _table_from_stub(self, text: str) -> Table:
        body = text[len(_TABLE_PREFIX):] if text.startswith(_TABLE_PREFIX) else text
        rows_str, sep, meta = body.partition("||")
        rows = [r.split("\t") for r in rows_str.split("\n")] if rows_str else []
        parts = meta.split("|") if sep else []
        while len(parts) < 3: parts.append("")
        return Table(rows=rows, caption=parts[0], label=parts[1] or None,
                     alignment=parts[2])

    # ---------- formatting actions (called by mainwindow) ----------

    def apply_heading(self, level: int) -> None:
        cursor = self._edit.textCursor()
        block = cursor.block()
        block.setUserState(level if level else _STATE_PARAGRAPH)
        block_cursor = QTextCursor(block)
        block_cursor.select(QTextCursor.BlockUnderCursor)
        if level >= 1:
            block_cursor.mergeCharFormat(_heading_char_format(level))
        else:
            fmt = QTextCharFormat(); f = QFont(); f.setPointSize(12); fmt.setFont(f)
            block_cursor.setCharFormat(fmt)
        self._on_text_changed()

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
            self._edit.textCursor().insertText(latex, _math_inline_format(latex))

    def insert_math_block(self) -> None:
        latex, ok = QInputDialog.getMultiLineText(self, "Insert math block", "LaTeX:")
        if ok and latex.strip():
            c = self._edit.textCursor()
            c.insertBlock()
            c.block().setUserState(_STATE_MATH_BLOCK)
            c.setBlockFormat(QTextBlockFormat())
            c.insertText(latex, _math_block_char_format())
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

    def insert_figure(self) -> None:
        path, ok = QInputDialog.getText(self, "Insert figure", "Image path:")
        if not ok or not path: return
        cap, _ = QInputDialog.getText(self, "Figure caption", "Caption:")
        label, _ = QInputDialog.getText(self, "Figure label", "Label (optional):")
        c = self._edit.textCursor()
        c.insertBlock()
        c.block().setUserState(_STATE_FIGURE)
        c.setBlockFormat(_stub_block_format())
        c.insertText(f"{_FIGURE_PREFIX}{path}|{cap}|{label}|0.8\\textwidth",
                     _stub_char_format())
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
        c.block().setUserState(_STATE_PARAGRAPH)

    def insert_table(self) -> None:
        rows, ok = QInputDialog.getInt(self, "Insert table", "Rows:", 3, 1, 50)
        if not ok: return
        cols, ok = QInputDialog.getInt(self, "Insert table", "Columns:", 3, 1, 20)
        if not ok: return
        cap, _ = QInputDialog.getText(self, "Caption", "Caption:")
        empty_rows = "\n".join("\t".join(["cell"] * cols) for _ in range(rows))
        c = self._edit.textCursor()
        c.insertBlock()
        c.block().setUserState(_STATE_TABLE)
        c.setBlockFormat(_stub_block_format())
        c.insertText(f"{_TABLE_PREFIX}{empty_rows}||{cap}||", _stub_char_format())
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
        c.block().setUserState(_STATE_PARAGRAPH)

    def insert_raw_latex(self) -> None:
        text, ok = QInputDialog.getMultiLineText(self, "Insert raw LaTeX",
                                                 "LaTeX (verbatim):")
        if not ok or not text.strip(): return
        c = self._edit.textCursor()
        c.insertBlock()
        c.block().setUserState(_STATE_RAW)
        c.setBlockFormat(_stub_block_format())
        c.insertText(_RAW_PREFIX + text, _stub_char_format())
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
        c.block().setUserState(_STATE_PARAGRAPH)

    def insert_page_break(self) -> None:
        # Implemented as RawLatex \newpage.
        c = self._edit.textCursor()
        c.insertBlock()
        c.block().setUserState(_STATE_RAW)
        c.setBlockFormat(_stub_block_format())
        c.insertText(_RAW_PREFIX + r"\newpage", _stub_char_format())
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
        c.block().setUserState(_STATE_PARAGRAPH)

    def insert_horizontal_rule(self) -> None:
        c = self._edit.textCursor()
        c.insertBlock()
        c.block().setUserState(_STATE_RAW)
        c.setBlockFormat(_stub_block_format())
        c.insertText(_RAW_PREFIX + r"\hrulefill", _stub_char_format())
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
        c.block().setUserState(_STATE_PARAGRAPH)

    def current_heading_level(self) -> int:
        """Return 0 for body / 1-5 for headings / -1 if cursor is on a non-text block."""
        state = self._edit.textCursor().block().userState()
        if 1 <= state <= 5: return state
        if state == _STATE_PARAGRAPH: return 0
        return -1

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


def _stub_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(10)
    fmt.setFont(f); fmt.setForeground(QColor("#444"))
    return fmt
