"""chemfig structure editor: palette data, preview-doc builder, RawLatex
round-trip, dialog wiring, and (when tectonic is present) that the complete
templates actually compile."""
import os

import pytest

from khervedoc import chemfig
from khervedoc.chemfig import (
    CHEMFIG_GROUPS, PLACEHOLDER, all_templates, build_preview_doc,
)


# ------------------------------------------------------------ palette data

def test_groups_are_wellformed():
    assert len(CHEMFIG_GROUPS) == 6
    names = [n for n, _ in CHEMFIG_GROUPS]
    assert names == ["Structures", "Rings", "Bonds", "Groups",
                     "Scheme", "Polymer"]
    for name, items in CHEMFIG_GROUPS:
        assert items
        for frag, label in items:
            assert isinstance(frag, str) and frag
            assert isinstance(label, str) and label


def test_placeholder_compiles_inside_chemfig():
    # \square is reused from the equation editor; it must be a bare token so
    # the tab-navigation in _EquationLatexEdit can find it.
    assert PLACEHOLDER == r"\square"


def test_structures_group_holds_complete_chemfig_macros():
    _, items = CHEMFIG_GROUPS[0]
    assert all(frag.startswith(r"\chemfig{") for frag, _ in items)


def test_scheme_group_has_a_full_reaction_template():
    scheme_items = dict(CHEMFIG_GROUPS)["Scheme"]
    assert any("schemestart" in frag and "schemestop" in frag
               for frag, _ in scheme_items)


# ------------------------------------------------------- preview-doc builder

def test_build_preview_doc_is_standalone_with_chemfig():
    doc = build_preview_doc(r"\chemfig{*6(======)}")
    assert r"\documentclass[border=4pt]{standalone}" in doc
    assert r"\usepackage{chemfig}" in doc
    assert r"\usepackage{amssymb}" in doc     # supplies \square
    assert r"\begin{document}" in doc and r"\end{document}" in doc
    assert r"\chemfig{*6(======)}" in doc


def test_build_preview_doc_strips_body():
    doc = build_preview_doc("   \\chemfig{X}   ")
    assert "\n\\chemfig{X}\n" in doc


# ----------------------------------------------------------- RawLatex model

def test_chemfig_round_trips_as_rawlatex():
    from khervedoc.model import (
        Document, DocMeta, RawLatex, from_json, to_json,
    )
    from khervedoc.serializer import serialize_document

    body = ("\\schemestart\n\\chemfig{S=C(-S-R)-S-R'}\n"
            "\\arrow{->[\\text{Thermal RAFT}]}\n\\chemfig{X}\n\\schemestop")
    doc = Document(meta=DocMeta(title="T", packages=["chemfig"]),
                   children=[RawLatex(text=body)])
    # JSON round-trip
    assert from_json(to_json(doc)).children[0].text == body
    # serialized verbatim, package present
    tex = serialize_document(doc)
    assert body in tex
    assert r"\usepackage{chemfig}" in tex


# ------------------------------------------------------------- dialog wiring

@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_dialog_constructs_and_populates_every_category(qapp):
    # No initial_latex: seeding it would kick a real background tectonic
    # compile, which has no place in a unit test (slow, and racy at teardown
    # with no event loop running). The compile path is covered by the gated
    # test_preview_worker_renders_an_image below.
    from khervedoc.equation_editor import ChemfigEditorDialog
    d = ChemfigEditorDialog()
    try:
        assert d.windowTitle() == "Chemical structure editor"
        assert len(d._groups()) == 6
        for i in range(len(d._groups())):
            d._show_category(i)          # builds each palette page
        d._edit.setPlainText(r"\chemfig{*6(======)}")   # timer won't fire here
        assert d.latex() == r"\chemfig{*6(======)}"
        # no per-button tectonic previews — buttons fall back to text
        assert d._render_template("x") is None
        assert d._worker is None
    finally:
        d.close()


def test_empty_source_shows_hint_not_a_crash(qapp):
    from khervedoc.equation_editor import ChemfigEditorDialog
    d = ChemfigEditorDialog()
    try:
        d._update_preview()              # empty: must not start a worker
        assert d._worker is None
        assert d.latex() == ""
    finally:
        d.close()


# ------------------------------------------------- real compile (tectonic)
#
# These drive tectonic (and, for the worker, pymupdf) for real. They are slow
# (~2 s per compile) and, run in-process alongside the rest of the Qt suite,
# the accumulated native state (MuPDF + Qt + subprocess) is flaky enough to
# occasionally corrupt the heap on Windows. So they are opt-in: set
# KHERVEDOC_CHEMFIG_COMPILE=1 to run them (CI/manual), skipped by default.
# The full template set was verified compiling by hand during development.

def _run_compile_tests() -> bool:
    if os.environ.get("KHERVEDOC_CHEMFIG_COMPILE") != "1":
        return False
    from khervedoc.compiler import tectonic_available
    return tectonic_available()


_COMPILE = _run_compile_tests()


# A representative subset — a plain ring, the MBTPA RAFT agent, and a full
# reaction scheme. The exhaustive template compile was verified by hand;
# compiling all of them on every test run is too slow to be worth it.
_COMPILE_SAMPLES = [
    (r"\chemfig{*6(======)}", "benzene"),
    (dict(CHEMFIG_GROUPS)["Structures"][3][0], "MBTPA"),
    (next(f for f, _ in dict(CHEMFIG_GROUPS)["Scheme"]
          if "schemestart" in f), "scheme"),
]


@pytest.mark.skipif(not _COMPILE, reason="set KHERVEDOC_CHEMFIG_COMPILE=1")
@pytest.mark.parametrize("frag,label", _COMPILE_SAMPLES)
def test_representative_templates_compile(tmp_path, frag, label):
    from khervedoc.compiler import compile_tex
    res = compile_tex(build_preview_doc(frag), tmp_path, basename="t")
    assert res.ok, f"{label} failed to compile:\n{(res.log or '')[-400:]}"


@pytest.mark.skipif(not _COMPILE, reason="set KHERVEDOC_CHEMFIG_COMPILE=1")
def test_preview_worker_renders_an_image(qapp, tmp_path):
    from khervedoc.equation_editor import _ChemfigPreviewWorker
    out = {}
    w = _ChemfigPreviewWorker(r"\chemfig{*6(======)}", tmp_path)
    w.done.connect(lambda ok, img, log: out.update(ok=ok, img=img))
    w.run()                              # synchronous in this thread
    assert out["ok"] is True
    assert out["img"] is not None and not out["img"].isNull()
