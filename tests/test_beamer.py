"""Tests for beamer Frame support: model, serializer, and importer."""
from khervedoc.model import (
    Document, DocMeta, Frame, Paragraph, Section, Text, Title, Author,
    from_json, to_json,
)
from khervedoc.serializer import serialize_document
from khervedoc.importers import import_tex


# --- Model round-trip ---

def test_frame_round_trip():
    doc = Document(
        meta=DocMeta(title="Test"),
        children=[
            Frame(children=[Text(text="Slide Title")]),
            Paragraph(children=[Text(text="Content")]),
        ],
    )
    assert from_json(to_json(doc)) == doc


def test_frame_empty_title_round_trip():
    doc = Document(
        meta=DocMeta(title="Test"),
        children=[Frame(children=[])],
    )
    assert from_json(to_json(doc)) == doc


# --- Serializer: beamer frames ---

def _beamer_doc(*blocks):
    return Document(
        meta=DocMeta(documentclass="beamer", title="T", author="A"),
        children=list(blocks),
    )


def test_beamer_title_becomes_titlepage_frame():
    doc = _beamer_doc(
        Title(children=[Text(text="My Talk")]),
        Author(children=[Text(text="Me")]),
    )
    tex = serialize_document(doc)
    assert "\\begin{frame}" in tex
    assert "\\titlepage" in tex
    assert "\\end{frame}" in tex


def test_beamer_frame_wraps_content():
    doc = _beamer_doc(
        Frame(children=[Text(text="Intro")]),
        Paragraph(children=[Text(text="Hello world")]),
    )
    tex = serialize_document(doc)
    assert "\\begin{frame}{Intro}" in tex
    assert "Hello world" in tex
    assert "\\end{frame}" in tex


def test_beamer_section_stays_as_section():
    doc = _beamer_doc(
        Section(level=1, children=[Text(text="Part One")]),
        Frame(children=[Text(text="Slide")]),
        Paragraph(children=[Text(text="Body")]),
    )
    tex = serialize_document(doc)
    assert "\\section{Part One}" in tex
    assert "\\begin{frame}{Slide}" in tex


def test_beamer_frame_empty_title_becomes_titlepage():
    doc = _beamer_doc(
        Frame(children=[]),
    )
    tex = serialize_document(doc)
    assert "\\titlepage" in tex


def test_beamer_multiple_frames():
    doc = _beamer_doc(
        Frame(children=[Text(text="First")]),
        Paragraph(children=[Text(text="Content 1")]),
        Frame(children=[Text(text="Second")]),
        Paragraph(children=[Text(text="Content 2")]),
    )
    tex = serialize_document(doc)
    assert tex.count("\\begin{frame}") == 2
    assert tex.count("\\end{frame}") == 2


# --- Importer: \begin{frame} ---

def test_import_frame_with_title():
    src = (
        "\\documentclass{beamer}\n"
        "\\begin{document}\n"
        "\\begin{frame}{Hello}\nSome content\n\\end{frame}\n"
        "\\end{document}\n"
    )
    doc = import_tex(src)
    frames = [b for b in doc.children if isinstance(b, Frame)]
    assert len(frames) == 1
    assert frames[0].children[0].text == "Hello"


def test_import_titlepage_frame():
    src = (
        "\\documentclass{beamer}\n"
        "\\title{Talk}\n"
        "\\begin{document}\n"
        "\\begin{frame}\n\\titlepage\n\\end{frame}\n"
        "\\end{document}\n"
    )
    doc = import_tex(src)
    titles = [b for b in doc.children if isinstance(b, Title)]
    assert len(titles) >= 1


def test_import_frame_without_title():
    src = (
        "\\documentclass{beamer}\n"
        "\\begin{document}\n"
        "\\begin{frame}\nJust content\n\\end{frame}\n"
        "\\end{document}\n"
    )
    doc = import_tex(src)
    frames = [b for b in doc.children if isinstance(b, Frame)]
    assert len(frames) == 1
