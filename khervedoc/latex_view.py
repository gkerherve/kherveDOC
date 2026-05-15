"""Read-only LaTeX source view with very lightweight syntax highlighting."""
from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression, Qt
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
    """Shows the generated LaTeX source. Updated via `set_source`."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._edit = QPlainTextEdit(self)
        self._edit.setReadOnly(True)
        f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(11)
        self._edit.setFont(f)
        self._highlighter = LatexHighlighter(self._edit.document())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)

    def set_source(self, src: str) -> None:
        scroll = self._edit.verticalScrollBar().value()
        self._edit.setPlainText(src)
        self._edit.verticalScrollBar().setValue(scroll)
