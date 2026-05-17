"""Editable LaTeX source view with syntax highlighting and autocompletion.

When the user edits this view kherveDOC reparses the source through
khervedoc.importers.import_tex and updates the Formatted tab + PDF
preview, giving you a two-way binding between the rendered document
and its LaTeX source.
"""
from __future__ import annotations

from PySide6.QtCore import QRegularExpression, QStringListModel, QTimer, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QCompleter, QPlainTextEdit, QVBoxLayout, QWidget,
)


# ---- colour schemes ----

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


# ---- multi-line block state encoding ----
# QSyntaxHighlighter stores an int per block via setCurrentBlockState.
# We use bits to track which environment(s) we're inside.
_STATE_NORMAL = 0
_STATE_MATH = 1
_STATE_FIGURE = 2
_STATE_TABLE = 3


_MATH_ENVS = (
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "displaymath",
    "eqnarray", "eqnarray*", "split",
)

# Precompiled regexes for \begin{env} / \end{env}.
_BEGIN_MATH_RE = QRegularExpression(
    r"^\s*\\begin\{(" + "|".join(_MATH_ENVS).replace("*", r"\*") + r")\}")
_END_MATH_RE = QRegularExpression(
    r"^\s*\\end\{(" + "|".join(_MATH_ENVS).replace("*", r"\*") + r")\}")
_BEGIN_FIGURE_RE = QRegularExpression(r"^\s*\\begin\{figure\*?\}")
_END_FIGURE_RE = QRegularExpression(r"^\s*\\end\{figure\*?\}")
_BEGIN_TABLE_RE = QRegularExpression(r"^\s*\\begin\{table\*?\}")
_END_TABLE_RE = QRegularExpression(r"^\s*\\end\{table\*?\}")
_SECTION_RE = QRegularExpression(
    r"^\s*\\(section|subsection|subsubsection|paragraph|subparagraph|chapter|part)\*?"
    r"(\{|\[)")


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

        # Block-level formats.
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

    def highlightBlock(self, text: str) -> None:
        prev = self.previousBlockState()
        if prev < 0:
            prev = _STATE_NORMAL
        state = prev

        # Check for environment opens/closes on this line.
        if state == _STATE_NORMAL:
            if _BEGIN_MATH_RE.match(text).hasMatch():
                state = _STATE_MATH
            elif _BEGIN_FIGURE_RE.match(text).hasMatch():
                state = _STATE_FIGURE
            elif _BEGIN_TABLE_RE.match(text).hasMatch():
                state = _STATE_TABLE

        # Determine which block-level format applies (if any).
        block_fmt = None
        is_section = False
        if state == _STATE_MATH:
            block_fmt = self._math_block_fmt
            if _END_MATH_RE.match(text).hasMatch():
                state = _STATE_NORMAL
        elif state == _STATE_FIGURE:
            block_fmt = self._figure_fmt
            if _END_FIGURE_RE.match(text).hasMatch():
                state = _STATE_NORMAL
        elif state == _STATE_TABLE:
            block_fmt = self._table_fmt
            if _END_TABLE_RE.match(text).hasMatch():
                state = _STATE_NORMAL
        elif _SECTION_RE.match(text).hasMatch():
            block_fmt = self._section_fmt
            is_section = True

        self.setCurrentBlockState(state)

        # Apply token-level highlights first.
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

        # Overlay block background on every character without touching the
        # foreground colour set by the token rules above.
        if block_fmt is not None:
            bg = block_fmt.background().color()
            for i in range(len(text)):
                f = self.format(i)
                f.setBackground(bg)
                # For section lines, also apply bold + section foreground
                # to characters that weren't coloured by a token rule
                # (i.e. the plain-text portion of the heading).
                if is_section and not f.fontWeight() > QFont.Normal:
                    f.setForeground(block_fmt.foreground())
                    f.setFontWeight(QFont.Bold)
                self.setFormat(i, 1, f)


# ---- LaTeX command dictionary for autocomplete ----

_LATEX_COMMANDS = [
    r"\section{}", r"\subsection{}", r"\subsubsection{}",
    r"\paragraph{}", r"\subparagraph{}", r"\chapter{}",
    r"\begin{}", r"\end{}",
    r"\begin{equation}", r"\end{equation}",
    r"\begin{align}", r"\end{align}",
    r"\begin{figure}", r"\end{figure}",
    r"\begin{table}", r"\end{table}",
    r"\begin{itemize}", r"\end{itemize}",
    r"\begin{enumerate}", r"\end{enumerate}",
    r"\begin{tabular}{}", r"\end{tabular}",
    r"\begin{center}", r"\end{center}",
    r"\begin{flushleft}", r"\end{flushleft}",
    r"\begin{flushright}", r"\end{flushright}",
    r"\begin{abstract}", r"\end{abstract}",
    r"\begin{multicols}{}", r"\end{multicols}",
    r"\begin{lstlisting}", r"\end{lstlisting}",
    r"\begin{verbatim}", r"\end{verbatim}",
    r"\begin{thebibliography}{}", r"\end{thebibliography}",
    r"\textbf{}", r"\textit{}", r"\texttt{}", r"\underline{}",
    r"\emph{}", r"\textsc{}", r"\textrm{}", r"\textsf{}",
    r"\includegraphics{}", r"\includegraphics[width=]{}",
    r"\caption{}", r"\label{}", r"\ref{}", r"\eqref{}", r"\pageref{}",
    r"\cite{}", r"\citep{}", r"\citet{}",
    r"\footnote{}", r"\href{}{}", r"\url{}",
    r"\frac{}{}", r"\sqrt{}", r"\sum", r"\prod", r"\int",
    r"\alpha", r"\beta", r"\gamma", r"\delta", r"\epsilon",
    r"\theta", r"\lambda", r"\mu", r"\sigma", r"\omega",
    r"\pi", r"\phi", r"\psi", r"\chi", r"\rho", r"\tau",
    r"\partial", r"\nabla", r"\infty", r"\forall", r"\exists",
    r"\mathbb{}", r"\mathcal{}", r"\mathfrak{}",
    r"\left", r"\right", r"\bigl", r"\bigr",
    r"\hspace{}", r"\vspace{}", r"\quad", r"\qquad",
    r"\newpage", r"\clearpage", r"\newline",
    r"\title{}", r"\author{}", r"\date{}", r"\maketitle",
    r"\tableofcontents", r"\listoffigures", r"\listoftables",
    r"\usepackage{}", r"\documentclass{}",
    r"\newcommand{}{}", r"\renewcommand{}{}",
    r"\providecommand{}{}",
    r"\setlength{}{}", r"\addtolength{}{}",
    r"\hrulefill", r"\dotfill",
    r"\centering", r"\raggedright", r"\raggedleft",
    r"\item", r"\bibitem{}",
    r"\Kstroke",
]


class LatexView(QWidget):
    """Two-way editable LaTeX source view with autocomplete."""

    latexEdited = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._edit = QPlainTextEdit(self)
        f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(11)
        self._edit.setFont(f)
        self._highlighter = LatexHighlighter(self._edit.document())

        # Autocomplete for LaTeX commands.
        self._completer = QCompleter(self)
        self._completer.setWidget(self._edit)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitive)
        self._completer.setModel(QStringListModel(_LATEX_COMMANDS, self._completer))
        self._completer.activated.connect(self._insert_completion)

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

    # ----- autocomplete -----

    def _text_under_cursor(self) -> str:
        """Return the current word being typed, including the leading backslash."""
        cursor = self._edit.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        line_to_cursor = cursor.selectedText()
        # Find the last backslash and return everything from it.
        idx = line_to_cursor.rfind("\\")
        if idx < 0:
            return ""
        return line_to_cursor[idx:]

    def _insert_completion(self, completion: str) -> None:
        prefix = self._completer.completionPrefix()
        cursor = self._edit.textCursor()
        # Remove the prefix the user already typed, then insert the full completion.
        cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
        cursor.insertText(completion)
        self._edit.setTextCursor(cursor)

    # ----- signal plumbing -----

    def _on_text_changed(self) -> None:
        if self._suppress_signal:
            return
        self._debounce.start()

        # Drive the completer from the current prefix.
        prefix = self._text_under_cursor()
        if len(prefix) >= 2:  # at least \ + one letter
            self._completer.setCompletionPrefix(prefix)
            if self._completer.completionCount() > 0:
                popup = self._completer.popup()
                popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
                cr = self._edit.cursorRect()
                cr.setWidth(280)
                self._completer.complete(cr)
            else:
                self._completer.popup().hide()
        else:
            self._completer.popup().hide()

    def _emit_edited(self) -> None:
        self.latexEdited.emit(self._edit.toPlainText())
