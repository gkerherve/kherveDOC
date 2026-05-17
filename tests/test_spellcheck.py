"""SpellHighlighter behaviour — tested via the underlying SpellChecker
calls; no QSyntaxHighlighter machinery needed at this layer."""

import pytest

from khervedoc import spellcheck


pytestmark = pytest.mark.skipif(
    not spellcheck.is_available(),
    reason="pyspellchecker not installed",
)


def test_is_available_when_module_imports():
    assert spellcheck.is_available() is True


def test_is_checkable_filters_obvious_non_words():
    assert spellcheck.SpellChecker  # type: ignore
    assert spellcheck._is_checkable("hello")
    assert spellcheck._is_checkable("don't")
    # Too short.
    assert not spellcheck._is_checkable("a")
    assert not spellcheck._is_checkable("ok")  # 2 letters
    # Digits present.
    assert not spellcheck._is_checkable("h2o")


def test_known_words_are_recognised():
    """The bundled English dictionary should know "hello" and
    "machine". If pyspellchecker ever changes default language, this
    test will catch it."""
    sc = spellcheck.SpellChecker()
    assert "hello" not in sc.unknown(["hello"])
    assert "machine" not in sc.unknown(["machine"])


def test_misspelled_words_are_flagged():
    sc = spellcheck.SpellChecker()
    bad = sc.unknown(["wrold", "helo", "machne"])
    assert "wrold" in bad
    assert "helo" in bad
    assert "machne" in bad


@pytest.fixture
def highlighter():
    """SpellHighlighter with a real QTextDocument owned by the fixture.
    Avoids the libshiboken "already deleted" trap when the highlighter
    outlives an inline-constructed QTextDocument."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QTextDocument
    if QApplication.instance() is None:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "minimal")
        QApplication([])
    doc = QTextDocument()
    sh = spellcheck.SpellHighlighter(doc)
    yield sh
    # Keep `doc` alive until after the test — the local ref above is
    # enough but make it explicit.
    del sh, doc


def test_is_misspelled_true_for_obvious_typo(highlighter):
    assert highlighter.is_misspelled("wrold")
    assert highlighter.is_misspelled("helo")


def test_is_misspelled_false_for_known_word(highlighter):
    assert highlighter.is_misspelled("hello") is False
    assert highlighter.is_misspelled("editor") is False


def test_is_misspelled_false_for_too_short_word(highlighter):
    """Two-letter words aren't checked at all (too many false positives
    from acronyms / units), so they always count as not-misspelled."""
    assert highlighter.is_misspelled("ok") is False


def test_suggestions_for_typo_include_correct_word(highlighter):
    sugs = highlighter.suggestions("wrold")
    assert "world" in sugs
    assert len(sugs) <= 7


def test_suggestions_preserve_capitalisation(highlighter):
    assert highlighter.suggestions("Wrold")[0] == "World"
    assert highlighter.suggestions("WROLD")[0] == "WORLD"


def test_add_to_dictionary_stops_flagging(highlighter):
    highlighter.add_to_dictionary("kherveDOC")
    assert highlighter.is_misspelled("kherveDOC") is False
    # Lowercased version also accepted since the ignore-set is keyed
    # by lowercase form.
    assert highlighter.is_misspelled("KHERVEDOC") is False
