from khervedoc.model import (
    Abstract, Author, Citation, CrossRef, Document, DocMeta, Figure, Footnote,
    InlineRaw, Keywords, Link, List as ListNode, ListItem, MathBlock,
    MathInline, Paragraph, RawLatex, Section, Table, Text, Title,
    from_json, to_json,
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
                InlineRaw(latex=r"\Kstroke"),
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


def test_legacy_two_column_bool_loads_as_column_count_2():
    """v0.17 docs stored a boolean `two_column`; v0.18+ uses
    `column_count`. Loading an older JSON must map True -> 2 so the
    user's existing files don't lose their two-column layout."""
    legacy = (
        '{"type":"Document","meta":{"two_column":true},"children":[]}'
    )
    doc = from_json(legacy)
    assert doc.meta.column_count == 2


def test_legacy_two_column_false_loads_as_column_count_1():
    legacy = (
        '{"type":"Document","meta":{"two_column":false},"children":[]}'
    )
    doc = from_json(legacy)
    assert doc.meta.column_count == 1


def test_unknown_block_type_raises():
    import pytest
    bad = '{"type":"Document","meta":{},"children":[{"type":"Sparkle"}]}'
    with pytest.raises(ValueError, match="Sparkle"):
        from_json(bad)
