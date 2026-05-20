"""Tests for the multi-chapter project model and serializer."""

from khervedoc.model import (
    ChapterEntry, DocMeta, Document, Paragraph, Project, Section, Text,
    project_from_json, project_to_json, to_json,
)
from khervedoc.serializer import (
    serialize_chapter_body, serialize_project_master,
)


def _sample_project() -> Project:
    proj = Project()
    proj.meta = DocMeta(
        title="My Thesis",
        author="J. Doe",
        documentclass="book",
    )
    proj.chapters = [
        ChapterEntry(
            path="frontmatter.kdoc.json",
            label="Front Matter",
            enabled=True,
            start_page=1,
            last_known_pages=4,
            numbering="roman",
        ),
        ChapterEntry(
            path="ch1_intro.kdoc.json",
            label="1 — Introduction",
            enabled=True,
            start_page=1,
            last_known_pages=20,
            numbering="arabic",
        ),
        ChapterEntry(
            path="ch2_theory.kdoc.json",
            label="2 — Theory",
            enabled=False,
            last_known_pages=30,
            numbering="arabic",
        ),
        ChapterEntry(
            path="ch3_results.kdoc.json",
            label="3 — Results",
            enabled=True,
            last_known_pages=25,
            numbering="arabic",
        ),
    ]
    proj.bibliography = "refs.bib"
    proj.bib_style = "plain"
    return proj


# ---- model round-trip ----

def test_project_json_round_trip():
    proj = _sample_project()
    s = project_to_json(proj)
    proj2 = project_from_json(s)
    assert proj2.meta.title == "My Thesis"
    assert proj2.meta.documentclass == "book"
    assert len(proj2.chapters) == 4
    assert proj2.chapters[0].label == "Front Matter"
    assert proj2.chapters[0].numbering == "roman"
    assert proj2.chapters[0].start_page == 1
    assert proj2.chapters[1].enabled is True
    assert proj2.chapters[2].enabled is False
    assert proj2.bibliography == "refs.bib"
    assert proj2.bib_style == "plain"


def test_project_default_meta():
    proj = Project()
    assert proj.meta.documentclass == "book"


def test_chapter_entry_defaults():
    ch = ChapterEntry()
    assert ch.enabled is True
    assert ch.start_page is None
    assert ch.numbering == "arabic"
    assert ch.last_known_pages == 0


# ---- serializer ----

def test_serialize_chapter_body_no_preamble():
    doc = Document(
        meta=DocMeta(documentclass="book"),
        children=[
            Section(level=1, children=[Text(text="Introduction")]),
            Paragraph(children=[Text(text="Hello world.")]),
        ],
    )
    body = serialize_chapter_body(doc)
    assert "\\documentclass" not in body
    assert "\\begin{document}" not in body
    assert "\\chapter{Introduction}" in body
    assert "Hello world." in body


def test_serialize_chapter_body_skips_title_author():
    from khervedoc.model import Title, Author
    doc = Document(
        meta=DocMeta(documentclass="book"),
        children=[
            Title(children=[Text(text="My Title")]),
            Author(children=[Text(text="Me")]),
            Paragraph(children=[Text(text="Body text.")]),
        ],
    )
    body = serialize_chapter_body(doc)
    assert "\\maketitle" not in body
    assert "Body text." in body


def test_serialize_project_master_structure():
    proj = _sample_project()
    master = serialize_project_master(proj)
    assert "\\documentclass" in master
    assert "\\begin{document}" in master
    assert "\\end{document}" in master
    # All chapters appear in \include
    assert "\\include{frontmatter}" in master
    assert "\\include{ch1_intro}" in master
    assert "\\include{ch2_theory}" in master
    assert "\\include{ch3_results}" in master


def test_serialize_project_master_includeonly():
    proj = _sample_project()
    master = serialize_project_master(proj)
    # Only enabled chapters in \includeonly (ch2 is disabled)
    assert "\\includeonly{" in master
    assert "ch2_theory" not in master.split("\\includeonly{")[1].split("}")[0]
    assert "frontmatter" in master.split("\\includeonly{")[1].split("}")[0]
    assert "ch1_intro" in master.split("\\includeonly{")[1].split("}")[0]
    assert "ch3_results" in master.split("\\includeonly{")[1].split("}")[0]


def test_serialize_project_master_page_numbering():
    proj = _sample_project()
    master = serialize_project_master(proj)
    assert "\\pagenumbering{roman}" in master
    assert "\\pagenumbering{arabic}" in master
    assert "\\setcounter{page}{1}" in master


def test_serialize_project_master_bibliography():
    proj = _sample_project()
    master = serialize_project_master(proj)
    assert "\\bibliographystyle{plain}" in master
    assert "\\bibliography{refs}" in master


def test_serialize_project_master_all_enabled_no_includeonly():
    """When all chapters are enabled, no \\includeonly is emitted."""
    proj = _sample_project()
    for ch in proj.chapters:
        ch.enabled = True
    master = serialize_project_master(proj)
    assert "\\includeonly" not in master
