"""Tests for the .tex importer. .docx importer is exercised manually because
generating a meaningful .docx fixture costs more than the test is worth."""

from khervedoc.importers import import_tex
from khervedoc.model import (
    Citation, CrossRef, Figure, Footnote, Link, List as ListNode, MathBlock,
    MathInline, Paragraph, Section, Table, Text, Title,
)


def _round_trip(src: str):
    return import_tex(src)


def test_extracts_documentclass_and_packages():
    src = r"""\documentclass{report}
\usepackage[a4paper]{geometry}
\usepackage{amsmath}
\usepackage{hyperref}
\begin{document}
hello
\end{document}
"""
    doc = _round_trip(src)
    assert doc.meta.documentclass == "report"
    assert "amsmath" in doc.meta.packages
    assert "hyperref" in doc.meta.packages
    assert "geometry" not in doc.meta.packages  # tracked separately
    assert doc.meta.page_size == "A4"


def test_letter_paper_detected():
    src = r"""\documentclass{article}
\usepackage[letterpaper]{geometry}
\begin{document}body\end{document}"""
    assert _round_trip(src).meta.page_size == "Letter"


def test_title_preamble_creates_title_block():
    src = r"""\documentclass{article}
\title{Hello World}
\author{Me}
\begin{document}\maketitle body\end{document}"""
    doc = _round_trip(src)
    titles = [b for b in doc.children if isinstance(b, Title)]
    assert len(titles) == 1
    assert any(isinstance(c, Text) and c.text == "Hello World" for c in titles[0].children)
    # meta.title is cleared once a Title block has taken over.
    assert doc.meta.title == ""
    assert doc.meta.author == "Me"


def test_section_levels():
    src = r"""\documentclass{article}\begin{document}
\section{Intro}
\subsection{Background}
\subsubsection*{Detail}
\end{document}"""
    doc = _round_trip(src)
    sections = [b for b in doc.children if isinstance(b, Section)]
    levels = [s.level for s in sections]
    assert levels == [1, 2, 3]
    # The starred subsubsection should not be numbered.
    assert sections[2].numbered is False


def test_marks_parsed():
    src = r"""\documentclass{article}\begin{document}
This is \textbf{bold} and \textit{italic} and \texttt{code}.
\end{document}"""
    doc = _round_trip(src)
    paras = [b for b in doc.children if isinstance(b, Paragraph)]
    assert paras, "expected a paragraph"
    marks_seen = set()
    for c in paras[0].children:
        if isinstance(c, Text):
            marks_seen.update(c.marks)
    assert "bold" in marks_seen
    assert "italic" in marks_seen
    assert "code" in marks_seen


def test_inline_math():
    src = r"\documentclass{article}\begin{document}E = $mc^2$ done\end{document}"
    doc = _round_trip(src)
    inline = doc.children[0].children
    assert any(isinstance(c, MathInline) and c.latex == "mc^2" for c in inline)


def test_display_math_block():
    src = r"""\documentclass{article}\begin{document}
\begin{equation}
x = 1
\end{equation}
\end{document}"""
    doc = _round_trip(src)
    maths = [b for b in doc.children if isinstance(b, MathBlock)]
    assert len(maths) == 1
    assert maths[0].numbered is True
    assert "x = 1" in maths[0].latex


def test_itemize_becomes_unordered_list():
    src = r"""\documentclass{article}\begin{document}
\begin{itemize}
\item first
\item second
\end{itemize}
\end{document}"""
    doc = _round_trip(src)
    lists = [b for b in doc.children if isinstance(b, ListNode)]
    assert len(lists) == 1
    assert lists[0].ordered is False
    assert len(lists[0].items) == 2


def test_link_footnote_citation_crossref():
    src = r"""\documentclass{article}\begin{document}
See \href{https://x.com}{here}\footnote{a note} and \cite{key1,key2} and \ref{sec:1}.
\end{document}"""
    doc = _round_trip(src)
    inline = doc.children[0].children
    assert any(isinstance(c, Link) and c.url == "https://x.com" for c in inline)
    assert any(isinstance(c, Footnote) for c in inline)
    assert any(isinstance(c, Citation) and c.keys == ["key1", "key2"] for c in inline)
    assert any(isinstance(c, CrossRef) and c.label == "sec:1" for c in inline)


def test_figure_with_includegraphics():
    src = r"""\documentclass{article}\begin{document}
\begin{figure}[h]
\centering
\includegraphics[width=0.5\textwidth]{img/foo.png}
\caption{A photo}
\label{fig:foo}
\end{figure}
\end{document}"""
    doc = _round_trip(src)
    figs = [b for b in doc.children if isinstance(b, Figure)]
    assert len(figs) == 1
    assert figs[0].path == "img/foo.png"
    assert figs[0].caption == "A photo"
    assert figs[0].label == "fig:foo"


def test_align_environment_preserved_in_mathblock():
    src = r"""\documentclass{article}\begin{document}
\begin{align}
x &= 1 \\
y &= 2
\end{align}
\end{document}"""
    doc = _round_trip(src)
    maths = [b for b in doc.children if isinstance(b, MathBlock)]
    assert len(maths) == 1
    # The align environment must survive the round-trip — otherwise it
    # downgrades to a plain equation and loses its alignment column.
    assert r"\begin{align}" in maths[0].latex
    assert r"x &= 1" in maths[0].latex


def test_gather_starred_is_unnumbered():
    src = r"""\documentclass{article}\begin{document}
\begin{gather*}
a + b = c
\end{gather*}
\end{document}"""
    doc = _round_trip(src)
    maths = [b for b in doc.children if isinstance(b, MathBlock)]
    assert maths[0].numbered is False
    assert r"\begin{gather*}" in maths[0].latex


def test_multline_environment_imported():
    src = r"""\documentclass{article}\begin{document}
\begin{multline}
\alpha + \beta \\ + \gamma = \delta
\end{multline}
\end{document}"""
    doc = _round_trip(src)
    maths = [b for b in doc.children if isinstance(b, MathBlock)]
    assert r"\begin{multline}" in maths[0].latex


def test_displaymath_brackets_form():
    src = r"\documentclass{article}\begin{document}\[ E = mc^2 \]\end{document}"
    doc = _round_trip(src)
    maths = [b for b in doc.children if isinstance(b, MathBlock)]
    assert len(maths) == 1
    assert maths[0].latex == "E = mc^2"


def test_table_environment_produces_table_node():
    src = r"""\documentclass{article}\begin{document}
\begin{table}[h]
\centering
\begin{tabular}{lcr}
\hline
A & B & C \\
1 & 2 & 3 \\
4 & 5 & 6 \\
\hline
\end{tabular}
\caption{Some data}
\label{tab:demo}
\end{table}
\end{document}"""
    doc = _round_trip(src)
    tables = [b for b in doc.children if isinstance(b, Table)]
    assert len(tables) == 1
    t = tables[0]
    assert t.rows == [["A", "B", "C"], ["1", "2", "3"], ["4", "5", "6"]]
    assert t.alignment == "lcr"
    assert t.caption == "Some data"
    assert t.label == "tab:demo"


def test_standalone_tabular_is_imported():
    src = r"""\documentclass{article}\begin{document}
\begin{tabular}{ll}
foo & bar \\
baz & qux \\
\end{tabular}
\end{document}"""
    doc = _round_trip(src)
    tables = [b for b in doc.children if isinstance(b, Table)]
    assert len(tables) == 1
    assert tables[0].rows == [["foo", "bar"], ["baz", "qux"]]


def test_figure_caption_with_inline_macros_preserved():
    src = r"""\documentclass{article}\begin{document}
\begin{figure}
\centering
\includegraphics[width=0.5\textwidth]{img/plot.png}
\caption{Result for \textbf{T=300K}}
\label{fig:r}
\end{figure}
\end{document}"""
    doc = _round_trip(src)
    figs = [b for b in doc.children if isinstance(b, Figure)]
    assert len(figs) == 1
    # The full caption is preserved verbatim, including the textbf macro.
    assert "Result for" in figs[0].caption and r"\textbf" in figs[0].caption


def test_escapes_unescaped():
    src = r"""\documentclass{article}\begin{document}
100\% \& \$5 plus a\_b
\end{document}"""
    doc = _round_trip(src)
    text = "".join(c.text for c in doc.children[0].children if isinstance(c, Text))
    assert "100% & $5" in text
    assert "a_b" in text
