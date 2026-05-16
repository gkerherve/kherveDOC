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


class LatexHighlighter(QSyntaxHighlighter):
    def __init__(self, parent: QTextDocument):
        super().__init__(parent)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        cmd_fmt = QTextCharFormat()
        cmd_fmt.setForeground(QColor("#1a6dd8")); cmd_fmt.setFontWeight(QFont.Bold)
        self._rules.append((QRegularExpression(r"\\[A-Za-z@]+\*?"), cmd_fmt))

        brace_fmt = QTextCharFormat(); brace_fmt.setForeground(QColor("#7a4c00"))
        self._rules.append((QRegularExpression(r"[\{\}]"), brace_fmt))

        math_fmt = QTextCharFormat()
        math_fmt.setForeground(QColor("#a04000")); math_fmt.setFontItalic(True)
        self._rules.append((QRegularExpression(r"\$[^$]*\$"), math_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#888")); comment_fmt.setFontItalic(True)
        self._rules.append((QRegularExpression(r"%[^\n]*"), comment_fmt))

    def highlightBlock(self, text: str) -> None:
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
      - latexEdited(str)  emitted ~600ms after the user stops typing.
    """

    latexEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._edit = QPlainTextEdit(self)
        # Editable so the user can hand-tune the LaTeX directly.
        f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(11)
        self._edit.setFont(f)
        self._highlighter = LatexHighlighter(self._edit.document())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)

        # Programmatic updates to setPlainText also fire textChanged, so we
        # gate the user-edit pipeline with a flag.
        self._suppress_signal = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(1500)
        self._debounce.timeout.connect(self._emit_edited)
        self._edit.textChanged.connect(self._on_text_changed)

    # ----- public API -----

    def set_source(self, src: str) -> None:
        """Replace the visible source without firing latexEdited. Used by
        the Formatted -> LaTeX path so the two views stay in sync without
        an infinite signal loop."""
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
        # Restore approximately where the cursor was, clamped to the new
        # length so a shorter source doesn't crash on selectPosition.
        cursor = self._edit.textCursor()
        cursor.setPosition(min(cursor_pos, len(src)))
        self._edit.setTextCursor(cursor)

    def source(self) -> str:
        return self._edit.toPlainText()

    # ----- signal plumbing -----

    def _on_text_changed(self) -> None:
        if self._suppress_signal:
            return
        self._debounce.start()

    def _emit_edited(self) -> None:
        self.latexEdited.emit(self._edit.toPlainText())
