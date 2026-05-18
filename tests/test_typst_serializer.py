from khervedoc.model import (
    Abstract, Author, Citation, CrossRef, Document, DocMeta, Figure, Footnote,
    Highlight, InlineRaw, Keywords, Link, List as ListNode, ListItem, MathBlock,
    MathInline, Paragraph, RawLatex, Section, Table, Text, Title, Comment,
)
from khervedoc.typst_serializer import (
    escape_text, serialize_block, serialize_document, serialize_inline,
)


# ---- escape_text ----

def test_escape_text_handles_specials():
    assert escape_text("#*_@$") == "\\#\\*\\_\\@\\$"
    assert escape_text("hello") == "hello"
    assert escape_text("a<b>c") == "a\\<b\\>c"
    assert escape_text("[x]") == "\\[x\\]"
    assert escape_text("~") == "\\~"
    assert escape_text("`code`") == "\\`code\\`"
    assert escape_text("a\\b") == "a\\\\b"


# ---- inline nodes ----

def test_text_bold():
    assert serialize_inline(Text(text="hi", marks=["bold"])) == "#strong[hi]"


def test_text_italic():
    assert serialize_inline(Text(text="hi", marks=["italic"])) == "#emph[hi]"


def test_text_marks_combined():
    result = serialize_inline(Text(text="hi", marks=["italic", "bold"]))
    assert result == "#strong[#emph[hi]]"


def test_text_underline():
    assert serialize_inline(Text(text="hi", marks=["underline"])) == "#underline[hi]"


def test_text_code():
    assert serialize_inline(Text(text="x", marks=["code"])) == "`x`"


def test_text_smallcaps():
    assert serialize_inline(Text(text="hi", marks=["smallcaps"])) == "#smallcaps[hi]"


def test_text_subscript():
    assert serialize_inline(Text(text="2", marks=["subscript"])) == "#sub[2]"


def test_text_superscript():
    assert serialize_inline(Text(text="2", marks=["superscript"])) == "#super[2]"


def test_text_strikethrough():
    assert serialize_inline(Text(text="old", marks=["strikethrough"])) == "#strike[old]"


def test_math_inline():
    assert serialize_inline(MathInline(latex="x^2")) == "$x^2$"


def test_link_with_children():
    n = Link(url="https://example.com", children=[Text(text="click")])
    assert serialize_inline(n) == '#link("https://example.com")[click]'


def test_link_without_children():
    assert serialize_inline(Link(url="https://x.com", children=[])) == \
        '#link("https://x.com")'


def test_footnote():
    n = Footnote(children=[Text(text="see page 5")])
    assert serialize_inline(n) == "#footnote[see page 5]"


def test_citation():
    n = Citation(keys=["smith2020", "doe2019"])
    assert serialize_inline(n) == "@smith2020 @doe2019"


def test_citation_single():
    assert serialize_inline(Citation(keys=["a"])) == "@a"


def test_crossref():
    assert serialize_inline(CrossRef(label="sec:intro")) == "@sec:intro"


def test_inline_raw():
    assert serialize_inline(InlineRaw(latex="\\Kstroke")) == "\\Kstroke"


def test_highlight():
    n = Highlight(children=[Text(text="important")], color="yellow")
    assert '#highlight(fill: rgb("#FFFF00"))[important]' == serialize_inline(n)


def test_comment():
    n = Comment(children=[Text(text="text")], note="fix this")
    assert serialize_inline(n) == "text /* fix this */"


# ---- block nodes ----

def test_paragraph_justify():
    n = Paragraph(children=[Text(text="hello")], alignment="justify")
    assert serialize_block(n) == "hello\n"


def test_paragraph_center():
    n = Paragraph(children=[Text(text="hello")], alignment="center")
    assert serialize_block(n) == "#align(center)[hello]\n"


def test_paragraph_left():
    n = Paragraph(children=[Text(text="hello")], alignment="left")
    assert serialize_block(n) == "#align(left)[hello]\n"


def test_paragraph_right():
    n = Paragraph(children=[Text(text="hello")], alignment="right")
    assert serialize_block(n) == "#align(right)[hello]\n"


def test_section_level1():
    n = Section(level=1, children=[Text(text="Intro")])
    assert serialize_block(n) == "= Intro\n"


def test_section_level2():
    n = Section(level=2, children=[Text(text="Sub")])
    assert serialize_block(n) == "== Sub\n"


def test_section_level3():
    n = Section(level=3, children=[Text(text="Subsub")])
    assert serialize_block(n) == "=== Subsub\n"


def test_section_unnumbered():
    n = Section(level=1, children=[Text(text="Appendix")], numbered=False)
    assert "#heading(level: 1, numbering: none)[Appendix]" in serialize_block(n)


def test_section_with_label():
    n = Section(level=1, children=[Text(text="Intro")], label="sec:intro")
    assert serialize_block(n) == "= Intro <sec:intro>\n"


def test_math_block_unnumbered():
    n = MathBlock(latex="x^2 + y^2 = z^2", numbered=False)
    assert serialize_block(n) == "$ x^2 + y^2 = z^2 $\n"


def test_math_block_numbered():
    n = MathBlock(latex="E = mc^2", numbered=True)
    out = serialize_block(n)
    assert "#math.equation(block: true, numbering: \"(1)\")" in out
    assert "E = m c^2" in out


def test_math_block_with_label():
    n = MathBlock(latex="x=1", numbered=True, label="eq:x")
    out = serialize_block(n)
    assert "<eq:x>" in out


def test_math_block_strips_latex_env():
    n = MathBlock(latex="\\begin{align*}\na &= b \\\\\nc &= d\n\\end{align*}",
                  numbered=False)
    out = serialize_block(n)
    assert "a &= b" in out
    assert "\\begin{align" not in out


def test_list_unordered():
    n = ListNode(ordered=False, items=[
        ListItem(children=[Text(text="one")]),
        ListItem(children=[Text(text="two")]),
    ])
    assert serialize_block(n) == "- one\n- two\n"


def test_list_ordered():
    n = ListNode(ordered=True, items=[
        ListItem(children=[Text(text="first")]),
        ListItem(children=[Text(text="second")]),
    ])
    assert serialize_block(n) == "+ first\n+ second\n"


def test_figure():
    n = Figure(path="images/cat.png", caption="A cat", width="0.8\\textwidth")
    out = serialize_block(n)
    assert 'image("images/cat.png", width: 80%)' in out
    assert "caption: [A cat]" in out


def test_figure_with_label():
    n = Figure(path="img.png", caption="X", label="fig:x")
    out = serialize_block(n)
    assert "<fig:x>" in out


def test_figure_backslash_path():
    n = Figure(path="images\\cat.png", caption="")
    out = serialize_block(n)
    assert "images/cat.png" in out


def test_table():
    n = Table(rows=[["A", "B"], ["1", "2"]], caption="Data")
    out = serialize_block(n)
    assert "table(columns: 2" in out
    assert "[A]" in out
    assert "caption: [Data]" in out


def test_table_with_label():
    n = Table(rows=[["x"]], caption="T", label="tab:t")
    out = serialize_block(n)
    assert "<tab:t>" in out


def test_table_no_caption():
    n = Table(rows=[["x", "y"]], caption="")
    out = serialize_block(n)
    assert "caption" not in out
    assert "#table(" in out


def test_raw_latex_becomes_comment():
    n = RawLatex(text="\\usepackage{foo}")
    out = serialize_block(n)
    assert "/* Raw LaTeX:" in out
    assert "\\usepackage{foo}" in out
    assert "*/" in out


def test_title_emits_nothing():
    n = Title(children=[Text(text="My Doc")])
    assert serialize_block(n) == ""


def test_author_emits_nothing():
    n = Author(children=[Text(text="Alice")])
    assert serialize_block(n) == ""


def test_abstract():
    n = Abstract(children=[Text(text="This paper...")])
    out = serialize_block(n)
    assert "Abstract." in out
    assert "This paper..." in out


def test_keywords():
    n = Keywords(children=[Text(text="AI · ML")])
    out = serialize_block(n)
    assert "Keywords:" in out
    assert "AI" in out


# ---- full document ----

def test_full_document_has_set_rules():
    doc = Document(
        meta=DocMeta(title="Test", author="Bob", page_size="A4",
                     body_font_pt=11),
        children=[
            Title(children=[Text(text="Test")]),
            Author(children=[Text(text="Bob")]),
            Paragraph(children=[Text(text="Hello world.")]),
        ],
    )
    out = serialize_document(doc)
    assert '#set document(title: "Test", author: "Bob")' in out
    assert '#set page(paper: "a4"' in out
    assert "size: 11pt" in out
    assert "#set par(" in out
    assert "#set heading(numbering:" in out
    assert "Hello world." in out


def test_document_title_and_author_centered():
    doc = Document(
        meta=DocMeta(title="My Title", author="Alice"),
        children=[
            Title(children=[Text(text="My Title")]),
            Author(children=[Text(text="Alice")]),
        ],
    )
    out = serialize_document(doc)
    assert "#align(center" in out
    assert "My Title" in out
    assert "Alice" in out


def test_document_font_family():
    doc = Document(
        meta=DocMeta(body_font_family="times"),
        children=[Paragraph(children=[Text(text="x")])],
    )
    out = serialize_document(doc)
    assert 'font: "Times New Roman"' in out


def test_document_no_indent():
    doc = Document(
        meta=DocMeta(paragraph_indent=False),
        children=[Paragraph(children=[Text(text="x")])],
    )
    out = serialize_document(doc)
    assert "first-line-indent" not in out


def test_document_columns():
    doc = Document(
        meta=DocMeta(column_count=2),
        children=[Paragraph(children=[Text(text="x")])],
    )
    out = serialize_document(doc)
    assert "columns: 2" in out


def test_document_line_spacing():
    doc = Document(
        meta=DocMeta(line_spacing=1.5),
        children=[Paragraph(children=[Text(text="x")])],
    )
    out = serialize_document(doc)
    assert "leading:" in out


def test_document_merges_abstracts():
    doc = Document(children=[
        Abstract(children=[Text(text="Para 1")]),
        Abstract(children=[Text(text="Para 2")]),
        Paragraph(children=[Text(text="Body")]),
    ])
    out = serialize_document(doc)
    assert "Para 1" in out
    assert "Para 2" in out
    assert out.count("Abstract.") == 1


def test_document_merges_keywords():
    doc = Document(children=[
        Keywords(children=[Text(text="AI")]),
        Keywords(children=[Text(text="ML")]),
    ])
    out = serialize_document(doc)
    assert "AI" in out
    assert "ML" in out
    assert out.count("Keywords:") == 1


# ---- LaTeX → Typst math translation ----

def test_math_translation_frac():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\frac{a}{b}") == "frac(a, b)"
    assert _latex_math_to_typst(r"\tfrac{b}{a}") == "frac(b, a)"


def test_math_translation_sqrt():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\sqrt{x}") == "sqrt(x)"
    assert _latex_math_to_typst(r"\sqrt[3]{x}") == "root(3, x)"


def test_math_translation_greek():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\alpha") == "alpha"
    assert _latex_math_to_typst(r"\Delta") == "Delta"
    assert _latex_math_to_typst(r"\theta") == "theta"


def test_math_translation_operators():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\cdot") == "dot"
    assert _latex_math_to_typst(r"\times") == "times"
    assert _latex_math_to_typst(r"\neq") == "eq.not"
    assert _latex_math_to_typst(r"\leq") == "lt.eq"
    assert _latex_math_to_typst(r"\infty") == "infinity"
    assert _latex_math_to_typst(r"\pm") == "plus.minus"


def test_math_translation_formatting():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\mathbf{x}") == "bold(x)"
    assert _latex_math_to_typst(r"\mathbb{R}") == "bb(R)"
    assert _latex_math_to_typst(r"\mathcal{F}") == "cal(F)"
    assert _latex_math_to_typst(r"\hat{x}") == "hat(x)"
    assert _latex_math_to_typst(r"\vec{x}") == "arrow(x)"


def test_math_translation_delimiters():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\left(x\right)") == "(x)"
    assert _latex_math_to_typst(r"\left[x\right]") == "[x]"


def test_math_translation_spacing():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\quad") == "quad"
    assert _latex_math_to_typst(r"\qquad") == "quad quad"


def test_math_translation_newline():
    from khervedoc.typst_serializer import _latex_math_to_typst
    result = _latex_math_to_typst(r"a \\ b")
    assert "\\" in result and "a" in result and "b" in result


def test_math_translation_nested():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\frac{\sqrt{x}}{y}") == "frac(sqrt(x), y)"


def test_math_translation_integrals():
    from khervedoc.typst_serializer import _latex_math_to_typst
    assert _latex_math_to_typst(r"\int") == "integral"
    assert _latex_math_to_typst(r"\sum") == "sum"
    assert _latex_math_to_typst(r"\prod") == "prod"


def test_math_translation_welcome_doc_example():
    """Test the specific math from the welcome document."""
    from khervedoc.typst_serializer import _latex_math_to_typst
    result = _latex_math_to_typst(r"a \neq 0")
    assert "eq.not" in result
    result = _latex_math_to_typst(r"\Delta = b^2 - 4ac")
    assert result == "Delta = b^2 - 4a c"


def test_math_inline_with_latex_commands():
    """MathInline nodes with LaTeX commands get translated."""
    n = MathInline(latex=r"\frac{a}{b}")
    assert serialize_inline(n) == "$frac(a, b)$"


def test_math_block_with_latex_commands():
    """MathBlock nodes with LaTeX commands get translated."""
    n = MathBlock(latex=r"E = mc^2, \quad \alpha \neq 0", numbered=False)
    out = serialize_block(n)
    assert "quad" in out
    assert "alpha" in out
    assert "eq.not" in out
    assert "\\" not in out.replace(" \\", "")  # no leftover backslash commands


def test_width_conversion():
    from khervedoc.typst_serializer import _latex_width_to_typst
    assert _latex_width_to_typst("0.8\\textwidth") == "80%"
    assert _latex_width_to_typst("0.5\\textwidth") == "50%"
    assert _latex_width_to_typst("1.0\\textwidth") == "100%"
    assert _latex_width_to_typst("whatever") == "80%"


def test_page_size_letter():
    doc = Document(
        meta=DocMeta(page_size="Letter"),
        children=[Paragraph(children=[Text(text="x")])],
    )
    out = serialize_document(doc)
    assert "us-letter" in out
