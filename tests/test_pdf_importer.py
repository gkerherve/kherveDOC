"""Tests for the .pdf importer — PDF → document model."""

import tempfile
from pathlib import Path

import pymupdf

from khervedoc.importers import import_pdf
from khervedoc.model import Figure, Paragraph, Section, Text


def _make_pdf(callback) -> Path:
    """Create a minimal PDF via PyMuPDF, calling *callback(doc)* to add pages.
    Returns the temp file path."""
    doc = pymupdf.open()
    callback(doc)
    path = Path(tempfile.mktemp(suffix=".pdf"))
    doc.save(str(path))
    doc.close()
    return path


def test_basic_paragraph():
    def build(doc):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), "Hello world.", fontsize=12)

    path = _make_pdf(build)
    image_dir = Path(tempfile.mkdtemp())
    result = import_pdf(path, image_dir)
    texts = [
        "".join(i.text for i in b.children if isinstance(i, Text)).strip()
        for b in result.children if isinstance(b, Paragraph)
    ]
    assert any("Hello world" in t for t in texts)


def test_heading_detected_by_size():
    def build(doc):
        page = doc.new_page(width=595, height=842)
        # Large text should be detected as a heading.
        page.insert_text((72, 120), "Big Title", fontsize=24,
                         fontname="helv")
        page.insert_text((72, 200), "Body text here.", fontsize=12)

    path = _make_pdf(build)
    image_dir = Path(tempfile.mkdtemp())
    result = import_pdf(path, image_dir)
    sections = [b for b in result.children if isinstance(b, Section)]
    paragraphs = [b for b in result.children if isinstance(b, Paragraph)]
    # The large text should be classified as a section (heading).
    assert len(sections) >= 1
    assert len(paragraphs) >= 1


def test_multi_page():
    def build(doc):
        for i in range(3):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 72), f"Page {i + 1} content.", fontsize=12)

    path = _make_pdf(build)
    image_dir = Path(tempfile.mkdtemp())
    result = import_pdf(path, image_dir)
    paragraphs = [b for b in result.children if isinstance(b, Paragraph)]
    assert len(paragraphs) >= 3


def test_progress_callback():
    def build(doc):
        for _ in range(2):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 72), "text", fontsize=12)

    path = _make_pdf(build)
    image_dir = Path(tempfile.mkdtemp())
    calls = []

    def on_progress(current, total):
        calls.append((current, total))

    import_pdf(path, image_dir, progress=on_progress)
    assert len(calls) == 2
    assert calls[-1] == (2, 2)


def test_image_extraction():
    def build(doc):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), "Before image.", fontsize=12)
        # Insert a small red rectangle as a pixmap image.
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), 1)
        pix.set_rect(pix.irect, (255, 0, 0, 255))
        page.insert_image(pymupdf.Rect(72, 100, 200, 200), pixmap=pix)

    path = _make_pdf(build)
    image_dir = Path(tempfile.mkdtemp())
    result = import_pdf(path, image_dir)
    figures = [b for b in result.children if isinstance(b, Figure)]
    assert len(figures) >= 1
    assert Path(figures[0].path).exists()
