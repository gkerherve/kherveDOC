"""Examples menu / starter document smoke tests.

Each factory in khervedoc.examples must produce a Document that the
serializer can turn into LaTeX without raising and that the JSON
round-trip preserves. Catching this here means a model change that
breaks an example (mismatched field rename, new required arg) fails
CI instead of crashing on app startup."""

import pytest

from khervedoc import examples
from khervedoc.model import Document, from_json, to_json
from khervedoc.serializer import serialize_document


@pytest.mark.parametrize("label,factory", examples.EXAMPLES)
def test_example_serializes_to_latex(label, factory):
    doc = factory()
    assert isinstance(doc, Document)
    out = serialize_document(doc)
    # Every example should produce a self-contained document.
    assert "\\documentclass" in out
    assert "\\begin{document}" in out
    assert "\\end{document}" in out


@pytest.mark.parametrize("label,factory", examples.EXAMPLES)
def test_example_json_round_trip(label, factory):
    doc = factory()
    # Round-tripping through JSON is what kdocz does on save/load;
    # if it loses data, the user opens an empty document next session.
    assert from_json(to_json(doc)) == doc


def test_welcome_is_long_enough_to_span_multiple_pages():
    """The welcome doc should be substantial enough to feel like more
    than a stub. Counting top-level blocks as a rough proxy for length."""
    doc = examples.welcome()
    assert len(doc.children) >= 15


def test_two_column_example_has_column_count_2():
    assert examples.two_column_article().meta.column_count == 2


def test_three_column_example_has_column_count_3():
    assert examples.three_column_document().meta.column_count == 3


def test_blank_example_is_minimal():
    """Blank doc must still have a title and at least one paragraph so
    the user has somewhere to click first."""
    doc = examples.blank()
    assert len(doc.children) >= 2
