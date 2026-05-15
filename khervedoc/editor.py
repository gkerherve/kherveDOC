"""WYSIWYG editor widget — QTextEdit driving the document model.

Heading level is tracked as a per-block user state. Inline math is stored as
text with a custom char-format property holding the LaTeX source; the
displayed text *is* the LaTeX, with a distinctive background so users can see
which spans are math. A math block is a paragraph with block-state = -1.

The model is rebuilt from the QTextDocument on every change.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction, QFont, QKeySequence, QTextBlockFormat, QTextCharFormat,
    QTextCursor, QColor,
)
from PySide6.QtWidgets import (
    QComboBox, QInputDialog, QTextEdit, QToolBar, QVBoxLayout, QWidget,
)

from .model import (
    Document, DocMeta, Section, Paragraph, MathBlock, Text, MathInline,
)


# Custom property id for storing LaTeX on a char format. QTextFormat lets
# clients attach arbitrary properties at ids >= UserProperty.
_MATH_PROP = QTextCharFormat.UserProperty + 1

# Block "user state" values map to model node types.
# 0..5 → Paragraph(0) / Section(level=N).  -1 → MathBlock.
_STATE_PARAGRAPH = 0
_STATE_MATH_BLOCK = 99  # sentinel; Qt's default user state is -1, so we avoid that


_HEADING_FONT_SIZES = {1: 22, 2: 18, 3: 15, 4: 13, 5: 12}


def _heading_block_format(level: int) -> QTextBlockFormat:
    fmt = QTextBlockFormat()
    fmt.setTopMargin(12.0)
    fmt.setBottomMargin(6.0)
    return fmt


def _heading_char_format(level: int) -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont()
    f.setBold(True)
    f.setPointSize(_HEADING_FONT_SIZES.get(level, 12))
    fmt.setFont(f)
    return fmt


def _math_block_char_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont("Consolas")
    f.setStyleHint(QFont.Monospace)
    f.setPointSize(11)
    fmt.setFont(f)
    fmt.setBackground(QColor("#eef3ff"))
    fmt.setForeground(QColor("#1a3a8c"))
    return fmt


def _math_inline_char_format(latex: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    f = QFont("Consolas")
    f.setStyleHint(QFont.Monospace)
    fmt.setFont(f)
    fmt.setBackground(QColor("#fff5d6"))
    fmt.setForeground(QColor("#7a4c00"))
    fmt.setProperty(_MATH_PROP, latex)
    return fmt


class DocumentEditor(QWidget):
    """Editor pane: toolbar + QTextEdit, exposing a Document model."""

    documentChanged = Signal()  # debounced — fires ~400ms after user stops typing

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._building = False  # suppress signals while we mutate programmatically

        self._edit = QTextEdit(self)
        self._edit.setAcceptRichText(False)
        f = QFont()
        f.setPointSize(12)
        self._edit.setFont(f)

        self._heading_combo = QComboBox(self)
        self._heading_combo.addItem("Body text", _STATE_PARAGRAPH)
        for level in range(1, 6):
            self._heading_combo.addItem(f"Heading {level}", level)
        self._heading_combo.currentIndexChanged.connect(self._apply_heading)

        toolbar = QToolBar(self)
        toolbar.addWidget(self._heading_combo)
        toolbar.addSeparator()

        self._act_bold = self._make_action(
            toolbar, "Bold", QKeySequence.Bold, self._toggle_bold, checkable=True)
        self._act_italic = self._make_action(
            toolbar, "Italic", QKeySequence.Italic, self._toggle_italic, checkable=True)
        toolbar.addSeparator()
        self._make_action(toolbar, "Inline math", QKeySequence("Ctrl+M"),
                          self._insert_inline_math)
        self._make_action(toolbar, "Math block", QKeySequence("Ctrl+Shift+M"),
                          self._insert_math_block)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar)
        layout.addWidget(self._edit)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self._emit_changed)

        self._edit.textChanged.connect(self._on_text_changed)
        self._edit.cursorPositionChanged.connect(self._sync_toolbar_from_cursor)

        # Document metadata kept alongside the QTextDocument.
        self._meta = DocMeta()

    # ----- public API -----

    def set_document(self, doc: Document) -> None:
        """Replace editor contents with `doc`."""
        self._building = True
        try:
            self._meta = doc.meta
            self._edit.clear()
            cursor = self._edit.textCursor()
            cursor.movePosition(QTextCursor.Start)

            first = True
            for block in doc.children:
                if not first:
                    cursor.insertBlock()
                first = False
                if isinstance(block, Section):
                    bfmt = _heading_block_format(block.level)
                    cursor.setBlockFormat(bfmt)
                    cursor.block().setUserState(block.level)
                    cfmt = _heading_char_format(block.level)
                    for inline in block.children:
                        self._insert_inline(cursor, inline, base_format=cfmt)
                elif isinstance(block, Paragraph):
                    cursor.block().setUserState(_STATE_PARAGRAPH)
                    for inline in block.children:
                        self._insert_inline(cursor, inline)
                elif isinstance(block, MathBlock):
                    cursor.setBlockFormat(QTextBlockFormat())
                    cursor.block().setUserState(_STATE_MATH_BLOCK)
                    cursor.insertText(block.latex, _math_block_char_format())
                # RawLatex blocks are not editable in MVP — skip them on load.
        finally:
            self._building = False
        self.documentChanged.emit()

    def get_document(self) -> Document:
        """Build a fresh Document model from the current QTextDocument."""
        qdoc = self._edit.document()
        blocks: list = []
        block = qdoc.firstBlock()
        while block.isValid():
            state = block.userState()
            text = block.text()
            if state == _STATE_MATH_BLOCK:
                blocks.append(MathBlock(latex=text))
            elif 1 <= state <= 5:
                blocks.append(Section(level=state, children=self._inlines_from_block(block)))
            else:
                # state is 0 (paragraph), -1 (uninitialised after Enter), or unknown.
                blocks.append(Paragraph(children=self._inlines_from_block(block)))
            block = block.next()
        return Document(children=blocks, meta=self._meta)

    # ----- helpers -----

    def _make_action(self, toolbar: QToolBar, text: str, shortcut, slot,
                     checkable: bool = False) -> QAction:
        act = QAction(text, self)
        act.setShortcut(shortcut)
        act.setCheckable(checkable)
        act.triggered.connect(slot)
        toolbar.addAction(act)
        return act

    def _insert_inline(self, cursor: QTextCursor, node, base_format: QTextCharFormat | None = None) -> None:
        if isinstance(node, Text):
            fmt = QTextCharFormat(base_format) if base_format else QTextCharFormat()
            f = fmt.font()
            if "bold" in node.marks:
                f.setBold(True)
            if "italic" in node.marks:
                f.setItalic(True)
            fmt.setFont(f)
            cursor.insertText(node.text, fmt)
        elif isinstance(node, MathInline):
            cursor.insertText(node.latex, _math_inline_char_format(node.latex))

    def _inlines_from_block(self, block) -> list:
        inlines: list = []
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            if fragment.isValid():
                text = fragment.text()
                fmt = fragment.charFormat()
                math_latex = fmt.property(_MATH_PROP)
                if math_latex:
                    # The stored LaTeX may have been edited; trust the visible text.
                    inlines.append(MathInline(latex=text))
                else:
                    marks: list = []
                    f = fmt.font()
                    if f.bold():
                        marks.append("bold")
                    if f.italic():
                        marks.append("italic")
                    inlines.append(Text(text=text, marks=marks))
            it += 1
        return inlines

    # ----- toolbar actions -----

    def _apply_heading(self, idx: int) -> None:
        level = self._heading_combo.itemData(idx)
        cursor = self._edit.textCursor()
        block = cursor.block()
        block.setUserState(level if level else _STATE_PARAGRAPH)
        # Apply heading char-format to the whole block.
        block_cursor = QTextCursor(block)
        block_cursor.select(QTextCursor.BlockUnderCursor)
        if level and level >= 1:
            block_cursor.mergeCharFormat(_heading_char_format(level))
        else:
            # Reset to default font.
            fmt = QTextCharFormat()
            f = QFont()
            f.setPointSize(12)
            fmt.setFont(f)
            block_cursor.setCharFormat(fmt)
        self._on_text_changed()

    def _toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        f = self._edit.currentFont()
        fmt.setFontWeight(QFont.Normal if f.bold() else QFont.Bold)
        self._merge_format(fmt)

    def _toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self._edit.currentFont().italic())
        self._merge_format(fmt)

    def _merge_format(self, fmt: QTextCharFormat) -> None:
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self._edit.mergeCurrentCharFormat(fmt)

    def _insert_inline_math(self) -> None:
        latex, ok = QInputDialog.getText(self, "Insert inline math", "LaTeX:")
        if not ok or not latex:
            return
        cursor = self._edit.textCursor()
        cursor.insertText(latex, _math_inline_char_format(latex))

    def _insert_math_block(self) -> None:
        latex, ok = QInputDialog.getMultiLineText(
            self, "Insert math block", "LaTeX:")
        if not ok or not latex.strip():
            return
        cursor = self._edit.textCursor()
        cursor.insertBlock()
        cursor.block().setUserState(_STATE_MATH_BLOCK)
        cursor.setBlockFormat(QTextBlockFormat())
        cursor.insertText(latex, _math_block_char_format())
        cursor.insertBlock()
        cursor.block().setUserState(_STATE_PARAGRAPH)

    # ----- signals -----

    def _on_text_changed(self) -> None:
        if self._building:
            return
        self._debounce.start()

    def _emit_changed(self) -> None:
        self.documentChanged.emit()

    def _sync_toolbar_from_cursor(self) -> None:
        if self._building:
            return
        f = self._edit.currentFont()
        self._act_bold.setChecked(f.bold())
        self._act_italic.setChecked(f.italic())
        state = self._edit.textCursor().block().userState()
        if state and 1 <= state <= 5:
            idx = state  # combo: 0 = body, 1..5 = headings
        else:
            idx = 0
        if self._heading_combo.currentIndex() != idx:
            self._heading_combo.blockSignals(True)
            self._heading_combo.setCurrentIndex(idx)
            self._heading_combo.blockSignals(False)
