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
