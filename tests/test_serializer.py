from khervedoc.model import (
    Abstract, Author, Citation, CrossRef, Document, DocMeta, Figure, Footnote,
    Keywords, Link, List as ListNode, ListItem, MathBlock, MathInline,
    Paragraph, RawLatex, Section, Table, Text, Title,
)
from khervedoc.serializer import (
    escape_text, serialize_block, serialize_document, serialize_inline,
)


def test_escape_text_handles_specials():
    assert escape_text("100% & $5") == r"100\% \& \$5"
    assert escape_text("a_b^c") == r"a\_b\textasciicircum{}c"
    assert escape_text("{x}") == r"\{x\}"


def test_text_with_marks_nests_in_stable_order():
    assert serialize_inline(Text(text="hi", marks=["italic", "bold"])) == \
        r"\textbf{\textit{hi}}"


def test_math_inline_is_not_escaped():
    assert serialize_inline(MathInline(latex="a_1 + b^2")) == "$a_1 + b^2$"


def test_link_serializes_with_href():
    n = Link(url="https://example.com", children=[Text(text="click here")])
    assert serialize_inline(n) == r"\href{https://example.com}{click here}"


def test_link_without_children_uses_url_as_text():
    assert serialize_inline(Link(url="https://x.com", children=[])) == \
        r"\href{https://x.com}{https://x.com}"


def test_footnote_serializes():
    n = Footnote(children=[Text(text="see page 5")])
    assert serialize_inline(n) == r"\footnote{see page 5}"


def test_citation_default_style_is_cite():
    n = Citation(keys=["smith2020", "doe2019"])
    assert serialize_inline(n) == r"\cite{smith2020,doe2019}"


def test_citation_alternative_styles():
    assert serialize_inline(Citation(keys=["a"], style="citep")) == r"\citep{a}"
    assert serialize_inline(Citation(keys=["a"], style="citet")) == r"\citet{a}"


def test_crossref_serializes():
    assert serialize_inline(CrossRef(label="sec:intro", kind="ref")) == r"\ref{sec:intro}"
    assert serialize_inline(CrossRef(label="eq:1", kind="eqref")) == r"\eqref{eq:1}"


def test_paragraph_left_uses_flushleft_env():
    # Left-aligned in the editor must produce flushleft in LaTeX, otherwise
    # LaTeX's default justify would silently make both edges flush in the PDF.
    n = Paragraph(children=[Text(text="hello")], alignment="left")
    out = serialize_block(n)
    assert r"\begin{flushleft}" in out
    assert r"\end{flushleft}" in out


def test_paragraph_justify_is_unwrapped():
    # "justify" is LaTeX's default — no wrapper, both edges flush.
    n = Paragraph(children=[Text(text="hello")], alignment="justify")
    assert r"\begin" not in serialize_block(n)


def test_paragraph_center_uses_center_env():
    n = Paragraph(children=[Text(text="hi")], alignment="center")
    out = serialize_block(n)
    assert r"\begin{center}" in out and r"\end{center}" in out


def test_paragraph_right_uses_flushright_env():
    n = Paragraph(children=[Text(text="hi")], alignment="right")
    out = serialize_block(n)
    assert r"\begin{flushright}" in out and r"\end{flushright}" in out


def test_section_numbered_vs_starred():
    assert serialize_block(Section(level=1, children=[Text(text="X")])).startswith(r"\section{X}")
    assert serialize_block(
        Section(level=2, children=[Text(text="X")], numbered=False)
    ).startswith(r"\subsection*{X}")


def test_math_block_envs():
    out_num = serialize_block(MathBlock(latex="x=1", numbered=True, label="eq:one"))
    assert r"\begin{equation}" in out_num and r"\label{eq:one}" in out_num
    out_unnum = serialize_block(MathBlock(latex="x=1", numbered=False))
    assert r"\begin{equation*}" in out_unnum


def test_multi_item_list_serializes_every_item():
    # Regression: rendering a List with N>1 items used to crash in the
    # editor because cursor.currentList() returned None after insertBlock.
    # The serializer side never had the bug, but the test guards the model
    # path that the (now fixed) editor flow re-builds.
    n = ListNode(ordered=False, items=[
        ListItem(children=[Text(text="alpha")]),
        ListItem(children=[Text(text="beta")]),
        ListItem(children=[Text(text="gamma")]),
    ])
    out = serialize_block(n)
    for word in ("alpha", "beta", "gamma"):
        assert f"\\item {word}" in out


def test_list_unordered_uses_itemize():
    n = ListNode(ordered=False, items=[
        ListItem(children=[Text(text="one")]),
        ListItem(children=[Text(text="two")]),
    ])
    out = serialize_block(n)
    assert r"\begin{itemize}" in out
    assert r"\item one" in out
    assert r"\item two" in out
    assert r"\end{itemize}" in out


def test_list_ordered_uses_enumerate():
    n = ListNode(ordered=True, items=[ListItem(children=[Text(text="x")])])
    assert r"\begin{enumerate}" in serialize_block(n)


def test_figure_serializes_with_includegraphics_and_caption():
    n = Figure(path="img/foo.png", caption="Hello", label="fig:foo", width="0.5\\textwidth")
    out = serialize_block(n)
    assert r"\begin{figure}" in out
    assert r"\includegraphics[width=0.5\textwidth]{img/foo.png}" in out
    assert r"\caption{Hello}" in out
    assert r"\label{fig:foo}" in out


def test_figure_normalises_backslashes_in_path():
    n = Figure(path=r"img\foo.png", caption="", label=None)
    assert "img/foo.png" in serialize_block(n)


def test_table_serializes_tabular_with_alignment():
    n = Table(rows=[["a", "b"], ["c", "d"]], caption="Cap", alignment="lr")
    out = serialize_block(n)
    assert r"\begin{tabular}{lr}" in out
    assert r"a & b \\" in out
    assert r"\caption{Cap}" in out


def test_table_auto_alignment_is_all_left():
    n = Table(rows=[["a", "b", "c"]])
    assert r"\begin{tabular}{lll}" in serialize_block(n)


def test_raw_latex_passes_through_verbatim():
    assert serialize_block(RawLatex(text=r"\includegraphics{foo.png}")).strip() == \
        r"\includegraphics{foo.png}"


def test_empty_title_and_author_omits_maketitle():
    doc = Document(meta=DocMeta(title="", author=""),
                   children=[Paragraph(children=[Text(text="hi")])])
    out = serialize_document(doc)
    assert r"\title" not in out
    assert r"\maketitle" not in out


def test_title_block_drives_title_and_maketitle():
    doc = Document(
        meta=DocMeta(title="", author=""),
        children=[
            Title(children=[Text(text="My Document")]),
            Paragraph(children=[Text(text="body")]),
        ],
    )
    out = serialize_document(doc)
    assert r"\title{My Document}" in out
    assert r"\maketitle" in out
    # \maketitle should come from the Title block in the body, not the
    # fallback prepend — verify by checking it appears after \begin{document}.
    body_start = out.index(r"\begin{document}")
    assert out.index(r"\maketitle", body_start) > body_start


def test_title_block_with_inline_marks():
    doc = Document(
        children=[Title(children=[
            Text(text="Bold "), Text(text="title", marks=["italic"])
        ])])
    out = serialize_document(doc)
    assert r"\title{Bold \textit{title}}" in out


def test_author_block_drives_author_in_preamble():
    doc = Document(
        meta=DocMeta(title="", author=""),
        children=[
            Title(children=[Text(text="T")]),
            Author(children=[Text(text="Jane Doe")]),
            Paragraph(children=[Text(text="body")]),
        ],
    )
    out = serialize_document(doc)
    assert r"\author{Jane Doe}" in out
    # The Author block itself produces no body output (Title handles \maketitle).
    body_start = out.index(r"\begin{document}")
    body = out[body_start:]
    assert "Jane Doe" not in body


def test_author_block_overrides_meta_author():
    doc = Document(
        meta=DocMeta(title="", author="Old Author"),
        children=[Author(children=[Text(text="New Author")])],
    )
    assert r"\author{New Author}" in serialize_document(doc)


def test_meta_title_fallback_when_no_title_block():
    doc = Document(meta=DocMeta(title="From meta", author="x"),
                   children=[Paragraph(children=[Text(text="body")])])
    out = serialize_document(doc)
    assert r"\title{From meta}" in out
    assert r"\maketitle" in out


def test_consecutive_abstract_blocks_merge_into_one_env():
    doc = Document(
        meta=DocMeta(),
        children=[
            Abstract(children=[Text(text="First paragraph.")]),
            Abstract(children=[Text(text="Second paragraph.")]),
            Paragraph(children=[Text(text="body")]),
        ],
    )
    out = serialize_document(doc)
    # Exactly one abstract env, even though there are two Abstract blocks.
    assert out.count(r"\begin{abstract}") == 1
    assert out.count(r"\end{abstract}") == 1
    assert "First paragraph." in out and "Second paragraph." in out


def test_keywords_blocks_join_with_sep():
    # Legacy form: one Keywords block per term — serializer still produces
    # a single keyword env with \sep between.
    doc = Document(
        meta=DocMeta(),
        children=[
            Keywords(children=[Text(text="XPS")]),
            Keywords(children=[Text(text="PHI")]),
            Keywords(children=[Text(text="Python")]),
        ],
    )
    out = serialize_document(doc)
    assert out.count(r"\begin{keyword}") == 1
    assert r"XPS \sep PHI \sep Python" in out


def test_single_keywords_block_with_bullet_separator_splits_back_to_sep():
    # Preferred shape: one Keywords block with terms joined by ' · '.
    doc = Document(
        meta=DocMeta(),
        children=[Keywords(children=[Text(text="XPS · PHI · Python")])],
    )
    out = serialize_document(doc)
    assert r"XPS \sep PHI \sep Python" in out


def test_elsarticle_wraps_metadata_in_frontmatter():
    doc = Document(
        meta=DocMeta(documentclass="elsarticle", title="", author=""),
        children=[
            Title(children=[Text(text="My title")]),
            Author(children=[Text(text="Jane Doe")]),
            Abstract(children=[Text(text="Short summary.")]),
            Keywords(children=[Text(text="alpha · beta")]),
            Section(level=1, children=[Text(text="Intro")]),
        ],
    )
    out = serialize_document(doc)
    # Everything from title to keywords must live inside the frontmatter env.
    fm_start = out.index(r"\begin{frontmatter}")
    fm_end = out.index(r"\end{frontmatter}")
    front = out[fm_start:fm_end]
    assert r"\title{My title}" in front
    assert r"\author{Jane Doe}" in front
    assert r"\begin{abstract}" in front and r"\end{abstract}" in front
    assert r"\begin{keyword}" in front and r"\end{keyword}" in front
    assert r"alpha \sep beta" in front
    # And the body section comes AFTER the closing of frontmatter.
    assert out.index(r"\section{Intro}") > fm_end
    # No \maketitle in elsarticle — frontmatter handles it.
    assert r"\maketitle" not in out


def test_article_class_still_uses_preamble_title_and_maketitle():
    doc = Document(
        meta=DocMeta(documentclass="article"),
        children=[
            Title(children=[Text(text="T")]),
            Abstract(children=[Text(text="Body")]),
        ],
    )
    out = serialize_document(doc)
    assert r"\title{T}" in out
    assert r"\begin{frontmatter}" not in out


def test_geometry_package_emitted_for_a4_by_default():
    doc = Document(meta=DocMeta(), children=[Paragraph(children=[Text(text="x")])])
    out = serialize_document(doc)
    assert "\\usepackage[a4paper,top=2.5cm,bottom=2.5cm,left=2.5cm,right=2.5cm]{geometry}" in out


def test_geometry_package_changes_with_page_size():
    doc = Document(meta=DocMeta(page_size="Letter"),
                   children=[Paragraph(children=[Text(text="x")])])
    out = serialize_document(doc)
    assert r"\usepackage[letterpaper," in out
    assert r"top=2.5cm" in out


def test_geometry_package_for_legal():
    doc = Document(meta=DocMeta(page_size="Legal"),
                   children=[Paragraph(children=[Text(text="x")])])
    assert r"\usepackage[legalpaper," in serialize_document(doc)


def test_custom_margins_flow_into_geometry():
    doc = Document(
        meta=DocMeta(margin_top_cm=1.0, margin_bottom_cm=1.5,
                     margin_left_cm=3.0, margin_right_cm=2.0),
        children=[Paragraph(children=[Text(text="x")])])
    out = serialize_document(doc)
    assert "top=1.0cm" in out and "bottom=1.5cm" in out
    assert "left=3.0cm" in out and "right=2.0cm" in out


def test_body_font_pt_becomes_documentclass_option():
    doc = Document(meta=DocMeta(body_font_pt=11), children=[])
    assert r"\documentclass[11pt]{article}" in serialize_document(doc)


def test_line_spacing_one_half_uses_onehalfspacing():
    doc = Document(meta=DocMeta(line_spacing=1.5),
                   children=[Paragraph(children=[Text(text="x")])])
    out = serialize_document(doc)
    assert r"\onehalfspacing" in out


def test_double_spacing_uses_doublespacing():
    doc = Document(meta=DocMeta(line_spacing=2.0),
                   children=[Paragraph(children=[Text(text="x")])])
    assert r"\doublespacing" in serialize_document(doc)


def test_font_family_helvetica_loads_helvet_package():
    doc = Document(meta=DocMeta(body_font_family="helvetica"),
                   children=[Paragraph(children=[Text(text="x")])])
    out = serialize_document(doc)
    assert r"\usepackage{helvet}" in out


def test_set_title_emits_maketitle():
    doc = Document(meta=DocMeta(title="X", author=""),
                   children=[Paragraph(children=[Text(text="hi")])])
    out = serialize_document(doc)
    assert r"\title{X}" in out
    assert r"\maketitle" in out
