"""Equation-editor dialog UX: placeholder highlighting/selection, the
live slot hint, and the display-equation checkbox."""
import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from khervedoc.equation_editor import (  # noqa: E402
    EquationEditorDialog, ChemistryEditorDialog, _EquationLatexEdit,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------ placeholders

def test_placeholder_spans(qapp):
    e = _EquationLatexEdit(r"\square")
    e.setPlainText(r"\frac{\square}{\square} + x")
    spans = e.placeholder_spans()
    assert len(spans) == 2
    text = e.toPlainText()
    for start, end in spans:
        assert text[start:end] == r"\square"


def test_click_position_selects_whole_placeholder(qapp):
    e = _EquationLatexEdit(r"\square")
    e.setPlainText(r"x + \square")
    # Anywhere inside the token — start, middle, end — selects all of it.
    for pos in (4, 7, 11):
        cur = e.textCursor()
        cur.clearSelection()
        e.setTextCursor(cur)
        assert e._select_placeholder_at(pos) is True
        assert e.textCursor().selectedText() == r"\square"
    assert e._select_placeholder_at(1) is False


def test_placeholders_are_highlighted(qapp):
    e = _EquationLatexEdit(r"\square")
    e.setPlainText(r"\sqrt{\square}")
    sels = e.extraSelections()
    assert len(sels) == 1
    assert sels[0].cursor.selectedText() == r"\square"


def test_seeded_dialog_preselects_first_placeholder(qapp):
    d = EquationEditorDialog(initial_latex=r"\frac{\square}{\square}")
    try:
        assert d._edit.textCursor().selectedText() == r"\square"
    finally:
        d.close()


def test_slot_hint_counts_placeholders(qapp):
    d = EquationEditorDialog()
    try:
        d._edit.setPlainText(r"\frac{\square}{\square}")
        assert d._ph_hint.text().startswith("2 empty slots")
        d._edit.setPlainText("x + y")
        assert d._ph_hint.text() == ""
    finally:
        d.close()


# ------------------------------------------------------- display checkbox

def test_display_checkbox_defaults_on_for_new_equations(qapp):
    d = EquationEditorDialog()
    try:
        assert d.is_display() is True
        assert not d._display_cb.isHidden()
    finally:
        d.close()


def test_display_checkbox_hidden_when_re_editing(qapp):
    d = EquationEditorDialog(initial_latex=r"\sqrt{x}")
    try:
        assert d._display_cb.isHidden()
    finally:
        d.close()


def test_chemistry_placeholder_click_selects_math_islanded_token(qapp):
    # The chemistry placeholder is "$\square$" — the click must select the
    # whole token including the $s or the replacement breaks the math island.
    d = ChemistryEditorDialog()
    try:
        d._edit.setPlainText(r"$\square$ -> $\square$")
        assert d._edit._select_placeholder_at(3) is True
        assert d._edit.textCursor().selectedText() == r"$\square$"
    finally:
        d.close()
