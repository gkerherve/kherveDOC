"""class_supports_chapter — which LaTeX classes accept \\chapter."""

import pytest

# Importing the editor needs PySide6 even though we don't touch any
# widgets here; skip the module if Qt isn't installed (CI-friendly).
pytest.importorskip("PySide6")

from khervedoc.editor import class_supports_chapter, CHAPTER_CLASSES


def test_book_report_memoir_support_chapter():
    for cls in CHAPTER_CLASSES:
        assert class_supports_chapter(cls), cls


def test_article_letter_beamer_do_not_support_chapter():
    for cls in ("article", "letter", "beamer"):
        assert not class_supports_chapter(cls), cls


def test_unknown_class_does_not_support_chapter():
    assert not class_supports_chapter("")
    assert not class_supports_chapter("scrartcl")
    assert not class_supports_chapter("elsarticle")


def test_koma_and_mimosis_support_chapter():
    assert class_supports_chapter("scrreprt")
    assert class_supports_chapter("scrbook")
    assert class_supports_chapter("mimosis")


def test_class_with_options_or_variants_still_recognised():
    """A prefix match catches scrbook (and similar memoir-family
    variants) without forcing the user to register every name."""
    # 'scrbook' is in the koma-script family and DOES support chapter,
    # but our list intentionally starts conservative (book/report/memoir
    # only). What we want to verify is that an option-suffixed class
    # like 'book,11pt' still works — chapter parses the leading name.
    assert class_supports_chapter("book,11pt")
    assert class_supports_chapter("report,a4paper,12pt")
