"""Double-clicking a rendered equation reopens the equation builder.

Also pins the round-trip fix these tests uncovered: the math preview image
(U+FFFC) and its U+2028 separator must never reach the model, or they end
up verbatim in the generated LaTeX.
"""
import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402
from PySide6.QtGui import QTextCursor  # noqa: E402

from khervedoc import editor as editor_mod  # noqa: E402
from khervedoc import equation_editor  # noqa: E402
from khervedoc.editor import DocumentEditor, _STATE_MATH_BLOCK  # noqa: E402
from khervedoc.model import (  # noqa: E402
    DocMeta, Document, MathBlock, MathInline, Paragraph, Text,
)
from khervedoc.serializer import serialize_document  # noqa: E402

OBJ_REPL = chr(0xFFFC)   # the preview image's object-replacement char
LINE_SEP = chr(0x2028)   # the separator inserted after the image


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def stub_dialog(monkeypatch):
    """Replace the equation builder with one that reports its seed and
    returns a fixed replacement."""
    state = {"seed": None, "returns": r"\sqrt{z}", "accept": True}

    class FakeDlg:
        def __init__(self, parent, initial_latex=""):
            state["seed"] = initial_latex

        def exec(self):
            return QDialog.Accepted if state["accept"] else QDialog.Rejected

        def latex(self):
            return state["returns"]

    monkeypatch.setattr(equation_editor, "EquationEditorDialog", FakeDlg)
    return state


def _doc():
    return Document(meta=DocMeta(title="T"), children=[
        Paragraph(children=[
            Text(text="A "),
            MathInline(latex=r"\frac{x}{y}"),   # complex -> gets a preview image
            Text(text=" B "),
            MathInline(latex="a+b"),            # simple -> text only
            Text(text=" C"),
        ]),
        MathBlock(latex="E=mc^2"),
    ])


@pytest.fixture
def ed(qapp):
    e = DocumentEditor()
    e.set_document(_doc())
    return e


def _inlines(ed):
    para = ed.get_document().children[0]
    return [(type(k).__name__, getattr(k, "text", None) or getattr(k, "latex", ""))
            for k in para.children]


def _math_block(ed):
    return [k.latex for k in ed.get_document().children
            if isinstance(k, MathBlock)]


def _click(ed, pos):
    c = QTextCursor(ed._edit.document())
    c.setPosition(pos)
    return ed._edit_math_at(c)


def _math_block_pos(ed):
    b = ed._edit.document().begin()
    while b.isValid() and b.userState() != _STATE_MATH_BLOCK:
        b = b.next()
    assert b.isValid()
    return b


# ---------------------------------------------------------- round-trip fix

def test_preview_image_never_reaches_the_model(ed):
    """The U+FFFC image char and its U+2028 separator are chrome, not text."""
    kinds = _inlines(ed)
    assert kinds == [
        ("Text", "A "),
        ("MathInline", r"\frac{x}{y}"),
        ("Text", " B "),
        ("MathInline", "a+b"),
        ("Text", " C"),
    ]


def test_control_chars_never_reach_the_latex(ed):
    tex = serialize_document(ed.get_document())
    assert OBJ_REPL not in tex
    assert LINE_SEP not in tex
    assert r"A $\frac{x}{y}$ B $a+b$ C" in tex


def test_math_preview_image_carries_its_source(ed):
    """The back-link that makes a click on the picture resolvable."""
    block = ed._edit.document().begin()
    it = block.begin()
    found = []
    while not it.atEnd():
        f = it.fragment()
        if f.isValid() and f.charFormat().isImageFormat():
            found.append(f.charFormat().property(editor_mod._P_MATH))
        it += 1
    assert found == [r"\frac{x}{y}"]


# ---------------------------------------------------------- click to edit

def test_click_on_the_rendered_image_reopens_the_builder(ed, stub_dialog):
    # fragment 1 is the image (offsets: "A " = 0..1, image = 2)
    assert _click(ed, 2) is True
    assert stub_dialog["seed"] == r"\frac{x}{y}"
    assert ("MathInline", r"\sqrt{z}") in _inlines(ed)


def test_click_on_the_latex_text_reopens_the_builder(ed, stub_dialog):
    assert _click(ed, 6) is True
    assert stub_dialog["seed"] == r"\frac{x}{y}"
    assert ("MathInline", r"\sqrt{z}") in _inlines(ed)


def test_click_replaces_in_place_and_leaves_siblings_alone(ed, stub_dialog):
    _click(ed, 2)
    assert _inlines(ed) == [
        ("Text", "A "),
        ("MathInline", r"\sqrt{z}"),
        ("Text", " B "),
        ("MathInline", "a+b"),
        ("Text", " C"),
    ]


def test_click_on_simple_inline_math_reopens_the_builder(ed, stub_dialog):
    stub_dialog["returns"] = "c-d"
    para = ed._edit.document().begin()
    pos = para.text().index("a+b")
    assert _click(ed, pos + 1) is True
    assert stub_dialog["seed"] == "a+b"
    assert ("MathInline", "c-d") in _inlines(ed)


def test_click_on_a_math_block_reopens_the_builder(ed, stub_dialog):
    stub_dialog["returns"] = r"\int_0^1 x\,dx"
    blk = _math_block_pos(ed)
    assert _click(ed, blk.position() + 2) is True
    assert stub_dialog["seed"] == "E=mc^2"
    assert _math_block(ed) == [r"\int_0^1 x\,dx"]


def test_click_on_prose_is_not_swallowed(ed, stub_dialog):
    """Must return False so the double-click still selects a word."""
    assert _click(ed, 0) is False
    assert stub_dialog["seed"] is None
    assert _inlines(ed) == [
        ("Text", "A "),
        ("MathInline", r"\frac{x}{y}"),
        ("Text", " B "),
        ("MathInline", "a+b"),
        ("Text", " C"),
    ]


def test_cancelling_the_dialog_leaves_the_equation_untouched(ed, stub_dialog):
    stub_dialog["accept"] = False
    assert _click(ed, 2) is True          # still handled — we opened the dialog
    assert ("MathInline", r"\frac{x}{y}") in _inlines(ed)


def test_unchanged_latex_is_not_reinserted(ed, stub_dialog):
    stub_dialog["returns"] = r"\frac{x}{y}"
    assert _click(ed, 2) is True
    assert _inlines(ed) == [
        ("Text", "A "),
        ("MathInline", r"\frac{x}{y}"),
        ("Text", " B "),
        ("MathInline", "a+b"),
        ("Text", " C"),
    ]


def test_edit_survives_serialization(ed, stub_dialog):
    _click(ed, 2)
    tex = serialize_document(ed.get_document())
    assert r"$\sqrt{z}$" in tex
    assert OBJ_REPL not in tex and LINE_SEP not in tex


@pytest.mark.parametrize("pos", list(range(0, 24)))
def test_every_click_offset_is_safe(qapp, stub_dialog, pos):
    """Whatever fragment a click lands on, the paragraph must end up with
    exactly two MathInline nodes and no orphaned image or separator."""
    e = DocumentEditor()
    e.set_document(_doc())
    if pos > e._edit.document().begin().length() - 1:
        pytest.skip("beyond paragraph")
    _click(e, pos)
    doc = e.get_document()
    maths = [k for k in doc.children[0].children if isinstance(k, MathInline)]
    assert len(maths) == 2
    tex = serialize_document(doc)
    assert OBJ_REPL not in tex and LINE_SEP not in tex


# ---------------------------------------------------- chemistry round-trips

def test_clicking_a_chemical_reaction_reopens_the_chemistry_editor(
        qapp, monkeypatch):
    r"""A \ce{} formula must not reopen in the equation builder — the user
    never typed the \ce{} wrapper and shouldn't be shown it."""
    seen = {}

    class FakeChem:
        def __init__(self, parent, initial_latex=""):
            seen["chem_seed"] = initial_latex

        def exec(self):
            return QDialog.Accepted

        def latex(self):
            return r"\ce{2H2 + O2 -> 2H2O}"

    class FakeEq:
        def __init__(self, parent, initial_latex=""):
            seen["eq_seed"] = initial_latex

        def exec(self):
            return QDialog.Rejected

        def latex(self):
            return ""

    monkeypatch.setattr(equation_editor, "ChemistryEditorDialog", FakeChem)
    monkeypatch.setattr(equation_editor, "EquationEditorDialog", FakeEq)

    e = DocumentEditor()
    e.set_document(Document(meta=DocMeta(title="T"), children=[
        Paragraph(children=[Text(text="X "), MathInline(latex=r"\ce{H2O}"),
                            Text(text=" Y")]),
    ]))
    para = e._edit.document().begin()
    pos = para.text().index(r"\ce{H2O}")
    assert _click(e, pos + 1) is True

    # seeded with the *body*, not the wrapper; equation builder never opened
    assert seen.get("chem_seed") == "H2O"
    assert "eq_seed" not in seen
    assert ("MathInline", r"\ce{2H2 + O2 -> 2H2O}") in _inlines(e)


def test_clicking_ordinary_math_does_not_open_the_chemistry_editor(
        qapp, monkeypatch, stub_dialog):
    opened = []

    class FakeChem:
        def __init__(self, parent, initial_latex=""):
            opened.append(initial_latex)

        def exec(self):
            return QDialog.Rejected

        def latex(self):
            return ""

    monkeypatch.setattr(equation_editor, "ChemistryEditorDialog", FakeChem)
    e = DocumentEditor()
    e.set_document(_doc())
    _click(e, 2)
    assert opened == []
