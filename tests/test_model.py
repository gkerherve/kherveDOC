from khervedoc.model import (
    Document, DocMeta, Paragraph, Section, MathBlock, MathInline,
    Text, from_json, to_json,
)


def test_round_trip_preserves_structure():
    doc = Document(
        meta=DocMeta(title="T", author="A"),
        children=[
            Section(level=2, children=[Text(text="Heading")]),
            Paragraph(children=[
                Text(text="hello ", marks=[]),
                Text(text="world", marks=["bold", "italic"]),
                MathInline(latex="x^2"),
            ]),
            MathBlock(latex=r"\int_0^1 f(x)\,dx", numbered=True, label="eq:int"),
        ],
    )
    round_tripped = from_json(to_json(doc))
    assert round_tripped == doc


def test_unknown_inline_type_raises():
    import pytest
    bad = '{"type":"Document","meta":{},"children":[{"type":"Paragraph","children":[{"type":"Sparkle"}]}]}'
    with pytest.raises(ValueError, match="Sparkle"):
        from_json(bad)
