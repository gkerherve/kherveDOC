"""Tests for the .tex importer. .docx importer is exercised manually because
generating a meaningful .docx fixture costs more than the test is worth."""

from khervedoc.importers import import_tex
from khervedoc.model import (
    Abstract, Citation, CrossRef, Figure, Footnote, Keywords, Link,
    List as ListNode, MathBlock, MathInline, Paragraph, RawLatex, Section,
    Table, Text, Title,
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


def test_flushleft_env_produces_left_aligned_paragraphs():
    src = r"""\documentclass{article}\begin{document}
\begin{flushleft}
Hello world.
\end{flushleft}
\end{document}"""
    doc = _round_trip(src)
    paras = [b for b in doc.children if isinstance(b, Paragraph)]
    assert len(paras) == 1
    assert paras[0].alignment == "left"


def test_center_env_produces_centered_paragraphs():
    src = r"""\documentclass{article}\begin{document}
\begin{center}
Heading-ish text.
\end{center}
\end{document}"""
    doc = _round_trip(src)
    paras = [b for b in doc.children if isinstance(b, Paragraph)]
    assert paras[0].alignment == "center"


def test_flushright_env_produces_right_aligned_paragraphs():
    src = r"""\documentclass{article}\begin{document}
\begin{flushright}
Aligned right.
\end{flushright}
\end{document}"""
    doc = _round_trip(src)
    paras = [b for b in doc.children if isinstance(b, Paragraph)]
    assert paras[0].alignment == "right"


def test_title_with_inline_textbf_is_parsed_to_marks_not_left_as_literal():
    # When the serializer round-trips a Title block whose text had an
    # inline emphasised run, the next reparse must convert the \textbf{}
    # back into a mark instead of leaving the raw LaTeX in the title.
    src = r"\documentclass{article}\title{Hello \emph{World}}\begin{document}body\end{document}"
    doc = _round_trip(src)
    title = next((b for b in doc.children if isinstance(b, Title)), None)
    assert title is not None
    flat = "".join(c.text for c in title.children if isinstance(c, Text))
    # The literal "\emph{" or "\textbf{" must NOT be in the Title text.
    assert "\\emph" not in flat
    assert "\\textbf" not in flat
    assert "Hello" in flat and "World" in flat


def test_strips_percent_line_comments():
    src = r"""\documentclass{article}\begin{document}
%% ============================================
\section{Intro}
%% banner
Body text here.
\end{document}"""
    doc = _round_trip(src)
    # The %% banners must not have leaked into the body as paragraphs.
    body_texts = [c.text for b in doc.children if isinstance(b, Paragraph)
                  for c in b.children if isinstance(c, Text)]
    flat = " ".join(body_texts)
    assert "===" not in flat
    assert "banner" not in flat
    assert "Body text here." in flat


def test_url_macro_becomes_link():
    src = r"\documentclass{article}\begin{document}See \url{https://x.com/y} for more.\end{document}"
    doc = _round_trip(src)
    inlines = doc.children[0].children
    assert any(isinstance(c, Link) and c.url == "https://x.com/y" for c in inlines)


def test_verbatim_environment_preserved_as_rawlatex():
    src = r"""\documentclass{article}\begin{document}
Example:
\begin{verbatim}
def foo(): return 1
\end{verbatim}
After.
\end{document}"""
    doc = _round_trip(src)
    raws = [b for b in doc.children if isinstance(b, RawLatex)]
    assert len(raws) == 1
    assert "verbatim" in raws[0].text
    assert "def foo()" in raws[0].text


def test_lstlisting_with_caption_preserved():
    src = r"""\documentclass{article}\begin{document}
\begin{lstlisting}[caption={Demo}]
print("hi")
\end{lstlisting}
\end{document}"""
    doc = _round_trip(src)
    raws = [b for b in doc.children if isinstance(b, RawLatex)]
    assert len(raws) == 1
    assert r"\begin{lstlisting}[caption={Demo}]" in raws[0].text
    assert 'print("hi")' in raws[0].text


def test_thebibliography_preserved_as_rawlatex():
    src = r"""\documentclass{article}\begin{document}
body
\begin{thebibliography}{9}
\bibitem{key}
A reference.
\end{thebibliography}
\end{document}"""
    doc = _round_trip(src)
    raws = [b for b in doc.children if isinstance(b, RawLatex)]
    assert any("thebibliography" in r.text for r in raws)
    assert any(r"\bibitem{key}" in r.text for r in raws)


def test_abstract_becomes_abstract_blocks():
    src = r"""\documentclass{article}\begin{document}
\begin{abstract}
Short summary of the work.

A second paragraph with more detail.
\end{abstract}
\section{Intro}
body
\end{document}"""
    doc = _round_trip(src)
    abstracts = [b for b in doc.children if isinstance(b, Abstract)]
    assert len(abstracts) == 2   # one per paragraph in the source env
    text0 = " ".join(c.text for c in abstracts[0].children if isinstance(c, Text))
    assert "Short summary" in text0
    text1 = " ".join(c.text for c in abstracts[1].children if isinstance(c, Text))
    assert "second paragraph" in text1


def test_keyword_environment_becomes_keywords_blocks():
    src = r"""\documentclass{article}\begin{document}
\begin{keyword}
XPS \sep PHI \sep Python
\end{keyword}
\end{document}"""
    doc = _round_trip(src)
    kws = [b for b in doc.children if isinstance(b, Keywords)]
    # Three keyword groups split on \sep.
    assert len(kws) == 3
    flat = [" ".join(c.text for c in k.children if isinstance(c, Text)) for k in kws]
    assert "XPS" in flat[0]
    assert "PHI" in flat[1]
    assert "Python" in flat[2]


def test_frontmatter_wrapper_is_flattened():
    src = r"""\documentclass{elsarticle}\begin{document}
\begin{frontmatter}
\title{Real Title}
\author[ic]{Some Author\corref{cor1}}
\begin{abstract}
Summary.
\end{abstract}
\end{frontmatter}
\section{Body}
content
\end{document}"""
    doc = _round_trip(src)
    # Title is captured (either in meta or promoted to a Title block) and
    # there must be no stray "frontmatter" text.
    title_blocks = [b for b in doc.children if isinstance(b, Title)]
    title_seen = doc.meta.title or "".join(
        c.text for t in title_blocks for c in t.children if isinstance(c, Text))
    assert "Real Title" in title_seen
    # No raw "begin{frontmatter}" should survive as text.
    all_text = " ".join(
        c.text for b in doc.children if isinstance(b, Paragraph)
        for c in b.children if isinstance(c, Text))
    assert "frontmatter" not in all_text
    # The Abstract should have been extracted as an Abstract block.
    abstracts = [b for b in doc.children if isinstance(b, Abstract)]
    assert len(abstracts) >= 1
    flat = " ".join(c.text for a in abstracts for c in a.children if isinstance(c, Text))
    assert "Summary" in flat


def test_unknown_macro_with_braced_arg_does_not_leak_args():
    src = r"\documentclass{article}\begin{document}\journal{SoftwareX} Body.\end{document}"
    doc = _round_trip(src)
    text = "".join(
        c.text for b in doc.children if isinstance(b, Paragraph)
        for c in b.children if isinstance(c, Text))
    # The \journal argument must not appear as a stray paragraph.
    assert "SoftwareX" not in text
    assert "Body." in text


def test_author_with_nested_corref_returns_clean_name():
    src = r"\documentclass{elsarticle}\author[ic]{Gwilherm Kerherve\corref{cor1}}\begin{document}body\end{document}"
    doc = _round_trip(src)
    assert "Gwilherm Kerherve" in doc.meta.author
    assert "corref" not in doc.meta.author
    assert "{" not in doc.meta.author


def test_escapes_unescaped():
    src = r"""\documentclass{article}\begin{document}
100\% \& \$5 plus a\_b
\end{document}"""
    doc = _round_trip(src)
    text = "".join(c.text for c in doc.children[0].children if isinstance(c, Text))
    assert "100% & $5" in text
    assert "a_b" in text
