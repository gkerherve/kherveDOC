from khervedoc.model import (
    Abstract, Author, Citation, CrossRef, Document, DocMeta, Figure, Footnote,
    Keywords, Link, List as ListNode, ListItem, MathBlock, MathInline,
    Paragraph, RawLatex, Section, Table, Text, Title, from_json, to_json,
)


def test_round_trip_preserves_all_node_types():
    doc = Document(
        meta=DocMeta(title="T", author="A"),
        children=[
            Title(children=[Text(text="My title")]),
            Author(children=[Text(text="Jane Doe")]),
            Abstract(children=[Text(text="A short summary.")]),
            Keywords(children=[Text(text="kw1")]),
            Section(level=2, children=[Text(text="Heading")]),
            Paragraph(children=[
                Text(text="hi ", marks=["bold", "italic"]),
                MathInline(latex="x^2"),
                Link(url="https://x.com", children=[Text(text="link")]),
                Footnote(children=[Text(text="see below")]),
                Citation(keys=["a", "b"], style="citep"),
                CrossRef(label="sec:1", kind="ref"),
            ]),
            ListNode(ordered=True, items=[
                ListItem(children=[Text(text="first")]),
                ListItem(children=[Text(text="second")]),
            ]),
            Figure(path="img.png", caption="Cap", label="fig:1", width="0.5\\textwidth"),
            Table(rows=[["a", "b"], ["c", "d"]], caption="Cap", alignment="ll"),
            MathBlock(latex=r"\int x", numbered=True, label="eq:i"),
            RawLatex(text=r"\verb|x|"),
        ],
    )
    assert from_json(to_json(doc)) == doc


def test_unknown_block_type_raises():
    import pytest
    bad = '{"type":"Document","meta":{},"children":[{"type":"Sparkle"}]}'
    with pytest.raises(ValueError, match="Sparkle"):
        from_json(bad)
