import re

import pytest

from khervedoc import chemistry
from khervedoc.chemistry import (
    CHEM_GROUPS, all_templates, ce_to_mathtext, wrap_ce,
)
from khervedoc.model import Document, DocMeta, MathBlock, MathInline, Paragraph
from khervedoc.serializer import serialize_document


# ---------------------------------------------------------------- transpiler

@pytest.mark.parametrize("body,expected", [
    ("H2O", r"\mathrm{H}_{2}\mathrm{O}"),
    ("2H2", r"2\mathrm{H}_{2}"),
    ("SO4^2-", r"\mathrm{SO}_{4}^{2-}"),
    ("Na^+", r"\mathrm{Na}^{+}"),
    ("OH-", r"\mathrm{OH}^{-}"),
    ("e-", r"\mathrm{e}^{-}"),
    ("H2O(l)", r"\mathrm{H}_{2}\mathrm{O}(\mathrm{l})"),
])
def test_species(body, expected):
    assert ce_to_mathtext(body) == expected


@pytest.mark.parametrize("body,arrow", [
    ("A -> B", r"\rightarrow"),
    ("A <- B", r"\leftarrow"),
    ("A <=> B", r"\rightleftharpoons"),
    ("A <-> B", r"\leftrightarrow"),
])
def test_arrows(body, arrow):
    assert arrow in ce_to_mathtext(body)


def test_full_reaction():
    assert ce_to_mathtext("2H2 + O2 -> 2H2O") == (
        r"2\mathrm{H}_{2}\;+\;\mathrm{O}_{2}\;\rightarrow"
        r"\;2\mathrm{H}_{2}\mathrm{O}"
    )


def test_arrow_annotation_is_dropped():
    """mathtext has no \\xrightarrow, so ->[cat] previews as a plain arrow."""
    out = ce_to_mathtext(r"CaCO3 ->[\Delta] CaO + CO2")
    assert r"\rightarrow" in out
    assert "Delta" not in out


def test_trailing_plus_is_a_charge_not_an_operator():
    """`Th+` is a cation; the + operator always has whitespace around it."""
    assert ce_to_mathtext("^{227}_{90}Th+") == r"^{227}_{90}\mathrm{Th}^{+}"


def test_hydrate_dot_digits_are_a_coefficient():
    assert ce_to_mathtext("CuSO4.5H2O") == (
        r"\mathrm{CuSO}_{4}\cdot 5\mathrm{H}_{2}\mathrm{O}")


def test_bonds():
    assert ce_to_mathtext("C#N") == r"\mathrm{C}\equiv \mathrm{N}"


def test_precipitate_and_gas():
    assert ce_to_mathtext("BaSO4 v").endswith(r"\downarrow")
    assert ce_to_mathtext("CO2 ^").endswith(r"\uparrow")


def test_empty():
    assert ce_to_mathtext("") == ""
    assert ce_to_mathtext("   ") == ""


# ---------------------------------------------------------------- wrap_ce

def test_wrap_ce():
    assert wrap_ce("H2O") == r"\ce{H2O}"
    assert wrap_ce("  H2O  ") == r"\ce{H2O}"
    assert wrap_ce("") == ""


def test_wrap_ce_is_idempotent():
    assert wrap_ce(r"\ce{H2O}") == r"\ce{H2O}"


# ---------------------------------------------------------------- templates

def test_placeholder_is_math_islanded():
    """Regression: mhchem parses the \\ce{} body itself and aborts with
    "Unexpected input character" on a bare \\square, so every unfilled slot
    must be wrapped in $...$ or freshly-inserted templates won't compile."""
    assert chemistry.PLACEHOLDER == r"$\square$"


def test_no_template_contains_a_bare_square():
    bare = re.compile(r"(?<!\$)\\square(?!\$)")
    for body, _label in all_templates():
        assert not bare.search(body), f"bare \\square in {body!r}"


def test_every_template_previews():
    """A template that can't be transpiled would show "Cannot render" the
    moment its category is opened."""
    for body, _label in all_templates():
        assert ce_to_mathtext(body).strip(), f"empty preview for {body!r}"


def test_groups_are_wellformed():
    assert len(CHEM_GROUPS) == 6
    for name, items in CHEM_GROUPS:
        assert name and items
        for body, label in items:
            assert isinstance(body, str) and isinstance(label, str)


# ---------------------------------------------------------------- serializer

def test_inline_chemistry_serializes_as_math():
    """\\ce{} needs no model node of its own — it rides inside MathInline."""
    doc = Document(
        meta=DocMeta(title="T", packages=["amsmath", "mhchem"]),
        children=[Paragraph(children=[MathInline(latex=r"\ce{H2O}")])],
    )
    tex = serialize_document(doc)
    assert r"$\ce{H2O}$" in tex
    assert r"\usepackage{mhchem}" in tex


def test_block_chemistry_serializes_as_equation():
    doc = Document(
        meta=DocMeta(title="T", packages=["amsmath", "mhchem"]),
        children=[MathBlock(latex=r"\ce{2H2 + O2 -> 2H2O}")],
    )
    tex = serialize_document(doc)
    assert r"\ce{2H2 + O2 -> 2H2O}" in tex
    assert r"\begin{equation*}" in tex


def test_numbered_block_chemistry_serializes_as_numbered_equation():
    doc = Document(
        meta=DocMeta(title="T", packages=["amsmath", "mhchem"]),
        children=[MathBlock(latex=r"\ce{H2O}", numbered=True)],
    )
    tex = serialize_document(doc)
    assert r"\begin{equation}" in tex
