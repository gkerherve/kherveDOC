from khervedoc.model import (
    Document, DocMeta, Paragraph, Section, MathBlock, MathInline,
    RawLatex, Text,
)
from khervedoc.serializer import (
    escape_text, serialize_block, serialize_document, serialize_inline,
)


def test_escape_text_handles_specials():
    assert escape_text("100% & $5") == r"100\% \& \$5"
    assert escape_text("a_b^c") == r"a\_b\textasciicircum{}c"
    assert escape_text("{x}") == r"\{x\}"


def test_text_with_marks_nests_in_stable_order():
    n = Text(text="hi", marks=["italic", "bold"])
    # bold is applied first (outermost) regardless of input order.
    assert serialize_inline(n) == r"\textbf{\textit{hi}}"


def test_math_inline_is_not_escaped():
    assert serialize_inline(MathInline(latex="a_1 + b^2")) == "$a_1 + b^2$"


def test_section_numbered_vs_starred():
    numbered = Section(level=1, children=[Text(text="Intro")])
    starred = Section(level=2, children=[Text(text="Aside")], numbered=False)
    assert serialize_block(numbered).startswith(r"\section{Intro}")
    assert serialize_block(starred).startswith(r"\subsection*{Aside}")


def test_section_label_emitted_when_present():
    n = Section(level=1, children=[Text(text="X")], label="sec:x")
    out = serialize_block(n)
    assert r"\label{sec:x}" in out


def test_math_block_numbered_uses_equation_env():
    n = MathBlock(latex="x=1", numbered=True, label="eq:one")
    out = serialize_block(n)
    assert r"\begin{equation}" in out and r"\end{equation}" in out
    assert r"\label{eq:one}" in out


def test_math_block_unnumbered_uses_starred_env():
    n = MathBlock(latex="x=1", numbered=False)
    out = serialize_block(n)
    assert r"\begin{equation*}" in out


def test_raw_latex_passes_through_verbatim():
    n = RawLatex(text=r"\includegraphics{foo.png}")
    assert serialize_block(n).strip() == r"\includegraphics{foo.png}"


def test_full_document_has_preamble_and_body():
    doc = Document(
        meta=DocMeta(title="My Doc", author="Me", packages=["amsmath"]),
        children=[Paragraph(children=[Text(text="hello")])],
    )
    out = serialize_document(doc)
    assert r"\documentclass{article}" in out
    assert r"\usepackage{amsmath}" in out
    assert r"\title{My Doc}" in out
    assert r"\author{Me}" in out
    assert r"\begin{document}" in out
    assert "hello" in out
    assert r"\end{document}" in out


def test_title_with_specials_is_escaped():
    doc = Document(meta=DocMeta(title="A & B"), children=[])
    out = serialize_document(doc)
    assert r"\title{A \& B}" in out
