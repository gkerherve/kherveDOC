"""End-to-end render test: take the two-column article example, drop
the body font to 10 pt the way Document properties does, compile via
tectonic, and assert the PDF actually contains body text in two
distinct column positions.

Skipped automatically if tectonic or pymupdf aren't available so this
doesn't break CI on a stripped-down checkout."""

import os
from pathlib import Path

import pytest

from khervedoc.compiler import compile_tex, tectonic_available
from khervedoc.examples import two_column_article
from khervedoc.serializer import serialize_document


pytestmark = pytest.mark.skipif(
    not tectonic_available(),
    reason="tectonic not installed — skip end-to-end PDF render test",
)


def _column_x_positions(pdf_path: Path) -> set[int]:
    """Return the distinct rounded x-positions of body text blocks across
    every page. A correctly two-columned PDF has at least two clearly
    distinct x bands (left ~ 70, right ~ 290 on A4 with 2.5cm margins);
    a broken single-column doc has only one."""
    import pymupdf
    xs: set[int] = set()
    with pymupdf.open(pdf_path) as pdf:
        for page in pdf:
            for block in page.get_text("blocks"):
                if not block[4].strip():
                    continue
                xs.add(round(block[0]))
    return xs


def test_two_column_article_at_10pt_actually_renders_two_columns(tmp_path):
    doc = two_column_article()
    doc.meta.body_font_pt = 10
    tex = serialize_document(doc)

    # Belt-and-braces: the documentclass options must include twocolumn.
    assert "twocolumn" in tex.splitlines()[0], (
        f"twocolumn missing from \\documentclass: {tex.splitlines()[0]!r}")

    result = compile_tex(tex, tmp_path)
    assert result.ok, f"compile failed: {result.error}\n{result.log[-400:]}"
    assert result.pdf_path and result.pdf_path.exists()

    xs = _column_x_positions(result.pdf_path)
    # On A4 with 2.5cm margins, the right column starts around x=290-310
    # and the left column around x=70. We don't pin exact numbers (font
    # metrics vary slightly across tectonic versions), just that we have
    # at least one block on each side of the page midline (~x=297pt for
    # A4 at 72dpi).
    left = [x for x in xs if x < 200]
    right = [x for x in xs if x > 280]
    assert left, f"no text blocks on the left half of any page (xs={sorted(xs)})"
    assert right, (
        f"no text blocks on the right half of any page — document is rendering "
        f"as single column despite twocolumn class option (xs={sorted(xs)})"
    )
