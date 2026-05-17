"""Tests for the Review feature: Highlight and Comment nodes."""
from khervedoc.model import (
    Comment, Document, DocMeta, Highlight, Paragraph, Text,
    from_json, to_json,
)
from khervedoc.serializer import serialize_document, serialize_inline


# --- Model round-trip ---

def test_highlight_round_trip():
    doc = Document(
        meta=DocMeta(title="Test"),
        children=[
            Paragraph(children=[
                Highlight(children=[Text(text="important")], color="green"),
            ]),
        ],
    )
    assert from_json(to_json(doc)) == doc


def test_comment_round_trip():
    doc = Document(
        meta=DocMeta(title="Test"),
        children=[
            Paragraph(children=[
                Comment(
                    children=[Text(text="some text")],
                    note="Please rephrase",
                    author="Alice",
                    timestamp="2026-05-17T10:00:00",
                    resolved=False,
                ),
            ]),
        ],
    )
    assert from_json(to_json(doc)) == doc


def test_comment_resolved_round_trip():
    doc = Document(
        meta=DocMeta(title="Test"),
        children=[
            Paragraph(children=[
                Comment(
                    children=[Text(text="ok")],
                    note="Checked",
                    author="Bob",
                    timestamp="2026-05-17T11:00:00",
                    resolved=True,
                ),
            ]),
        ],
    )
    assert from_json(to_json(doc)) == doc


# --- Serializer ---

def test_highlight_serializes_to_colorbox():
    node = Highlight(children=[Text(text="word")], color="yellow")
    assert serialize_inline(node) == r"\colorbox{hlYellow}{word}"


def test_highlight_green_serializes():
    node = Highlight(children=[Text(text="ok")], color="green")
    assert serialize_inline(node) == r"\colorbox{hlGreen}{ok}"


def test_highlight_with_marks_inside():
    node = Highlight(
        children=[Text(text="bold", marks=["bold"])],
        color="blue",
    )
    assert serialize_inline(node) == r"\colorbox{hlBlue}{\textbf{bold}}"


def test_comment_serializes_to_todo():
    node = Comment(
        children=[Text(text="some text")],
        note="Fix this",
        author="Alice",
    )
    expected = r"some text\todo[color=blue!20, author={Alice}]{Fix this}"
    assert serialize_inline(node) == expected


def test_comment_without_author():
    node = Comment(children=[Text(text="text")], note="A note")
    expected = r"text\todo[color=blue!20]{A note}"
    assert serialize_inline(node) == expected


def test_comment_escapes_braces_in_note():
    node = Comment(children=[Text(text="x")], note="use {x}")
    expected = r"x\todo[color=blue!20]{use \{x\}}"
    assert serialize_inline(node) == expected


# --- Package injection ---

def test_highlight_injects_xcolor_and_definecolor():
    doc = Document(
        meta=DocMeta(title="T"),
        children=[
            Paragraph(children=[
                Highlight(children=[Text(text="hi")], color="yellow"),
            ]),
        ],
    )
    tex = serialize_document(doc)
    assert r"\usepackage{xcolor}" in tex
    assert r"\definecolor{hlYellow}{HTML}{FFFF00}" in tex


def test_comment_injects_todonotes():
    doc = Document(
        meta=DocMeta(title="T"),
        children=[
            Paragraph(children=[
                Comment(children=[Text(text="x")], note="note", author="A"),
            ]),
        ],
    )
    tex = serialize_document(doc)
    assert r"\usepackage[colorinlistoftodos]{todonotes}" in tex


def test_no_review_features_no_extra_packages():
    doc = Document(
        meta=DocMeta(title="T"),
        children=[Paragraph(children=[Text(text="plain")])],
    )
    tex = serialize_document(doc)
    assert "todonotes" not in tex
    assert "hlYellow" not in tex
