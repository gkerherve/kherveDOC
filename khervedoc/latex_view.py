"""Editable LaTeX source view with light syntax highlighting.

When the user edits this view kherveDOC reparses the source through
khervedoc.importers.import_tex and updates the Formatted tab + PDF
preview, giving you a two-way binding between the rendered document
and its LaTeX source.
"""
from __future__ import annotations

from PySide6.QtCore import QRegularExpression, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument,
)
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


# Colour schemes keyed by theme name.
_LIGHT_COLORS = {
    "command": "#1a6dd8",
    "brace": "#7a4c00",
    "math_fg": "#a04000",
    "comment": "#888888",
    "section_bg": "#e8f0fe",
    "section_fg": "#1a3a8c",
    "math_bg": "#fff5d6",
    "figure_bg": "#e8f5e9",
    "figure_fg": "#2e7d32",
    "table_bg": "#fff3e0",
    "table_fg": "#e65100",
}
_DARK_COLORS = {
    "command": "#6cb4ff",
    "brace": "#e5a835",
    "math_fg": "#f0a050",
    "comment": "#6a9955",
    "section_bg": "#1e3a5f",
    "section_fg": "#8cc4ff",
    "math_bg": "#3d3520",
    "figure_bg": "#1e3d1e",
    "figure_fg": "#66bb6a",
    "table_bg": "#3d2e1a",
    "table_fg": "#ffab40",
}


class LatexHighlighter(QSyntaxHighlighter):
    def __init__(self, parent: QTextDocument, dark: bool = False):
        super().__init__(parent)
        self._dark = dark
        self._build_rules()

    def set_dark(self, dark: bool) -> None:
        if dark == self._dark:
            return
        self._dark = dark
        self._build_rules()
        self.rehighlight()

    def _build_rules(self) -> None:
        c = _DARK_COLORS if self._dark else _LIGHT_COLORS
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        cmd_fmt = QTextCharFormat()
        cmd_fmt.setForeground(QColor(c["command"]))
        cmd_fmt.setFontWeight(QFont.Bold)
        self._rules.append((QRegularExpression(r"\\[A-Za-z@]+\*?"), cmd_fmt))

        brace_fmt = QTextCharFormat()
        brace_fmt.setForeground(QColor(c["brace"]))
        self._rules.append((QRegularExpression(r"[\{\}]"), brace_fmt))

        math_fmt = QTextCharFormat()
        math_fmt.setForeground(QColor(c["math_fg"]))
        math_fmt.setBackground(QColor(c["math_bg"]))
        math_fmt.setFontItalic(True)
        self._rules.append((QRegularExpression(r"\$[^$]*\$"), math_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor(c["comment"]))
        comment_fmt.setFontItalic(True)
        self._rules.append((QRegularExpression(r"%[^\n]*"), comment_fmt))

        # Block-level highlights: applied to the whole line.
        self._section_fmt = QTextCharFormat()
        self._section_fmt.setBackground(QColor(c["section_bg"]))
        self._section_fmt.setForeground(QColor(c["section_fg"]))
        self._section_fmt.setFontWeight(QFont.Bold)

        self._math_block_fmt = QTextCharFormat()
        self._math_block_fmt.setBackground(QColor(c["math_bg"]))
        self._math_block_fmt.setForeground(QColor(c["math_fg"]))

        self._figure_fmt = QTextCharFormat()
        self._figure_fmt.setBackground(QColor(c["figure_bg"]))
        self._figure_fmt.setForeground(QColor(c["figure_fg"]))

        self._table_fmt = QTextCharFormat()
        self._table_fmt.setBackground(QColor(c["table_bg"]))
        self._table_fmt.setForeground(QColor(c["table_fg"]))

    _SECTION_RE = QRegularExpression(
        r"\\(section|subsection|subsubsection|paragraph|subparagraph|chapter|part)\*?\{")
    _MATH_ENV_RE = QRegularExpression(
        r"\\(begin|end)\{(equation|align|gather|multline|displaymath|eqnarray|split|alignat)\*?\}")
    _FIGURE_RE = QRegularExpression(r"\\(begin|end)\{figure\*?\}")
    _TABLE_RE = QRegularExpression(r"\\(begin|end)\{table\*?\}")

    def highlightBlock(self, text: str) -> None:
        # Full-line background highlights for structural elements.
        if self._SECTION_RE.match(text).hasMatch():
            self.setFormat(0, len(text), self._section_fmt)
        elif self._MATH_ENV_RE.match(text).hasMatch():
            self.setFormat(0, len(text), self._math_block_fmt)
        elif self._FIGURE_RE.match(text).hasMatch():
            self.setFormat(0, len(text), self._figure_fmt)
        elif self._TABLE_RE.match(text).hasMatch():
            self.setFormat(0, len(text), self._table_fmt)

        # Token-level highlights (override the full-line background where they
        # match, giving the foreground colour priority).
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class LatexView(QWidget):
    """Two-way editable LaTeX source view.

    Public surface:
      - set_source(src)   set the text programmatically without firing
                          the user-edit signal (used by the Formatted ->
                          LaTeX sync path).
      - latexEdited(str)  emitted after the user stops typing.
    """

    latexEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._edit = QPlainTextEdit(self)
        f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(11)
        self._edit.setFont(f)
        self._highlighter = LatexHighlighter(self._edit.document())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)

        self._suppress_signal = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(1500)
        self._debounce.timeout.connect(self._emit_edited)
        self._edit.textChanged.connect(self._on_text_changed)

    # ----- public API -----

    def set_source(self, src: str) -> None:
        """Replace the visible source without firing latexEdited."""
        if self._edit.toPlainText() == src:
            return
        cursor_pos = self._edit.textCursor().position()
        scroll = self._edit.verticalScrollBar().value()
        self._suppress_signal = True
        try:
            self._edit.setPlainText(src)
        finally:
            self._suppress_signal = False
        self._edit.verticalScrollBar().setValue(scroll)
        cursor = self._edit.textCursor()
        cursor.setPosition(min(cursor_pos, len(src)))
        self._edit.setTextCursor(cursor)

    def source(self) -> str:
        return self._edit.toPlainText()

    def set_dark(self, dark: bool) -> None:
        self._highlighter.set_dark(dark)
        if dark:
            self._edit.setStyleSheet(
                "QPlainTextEdit { background: #1e1e1e; color: #d4d4d4; }")
        else:
            self._edit.setStyleSheet(
                "QPlainTextEdit { background: #ffffff; color: #1c1c1c; }")

    # ----- signal plumbing -----

    def _on_text_changed(self) -> None:
        if self._suppress_signal:
            return
        self._debounce.start()

    def _emit_edited(self) -> None:
        self.latexEdited.emit(self._edit.toPlainText())
