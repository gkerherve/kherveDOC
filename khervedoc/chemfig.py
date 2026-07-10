"""Palette templates and preview plumbing for the chemfig structure editor.

Unlike the equation and chemistry editors — whose previews are matplotlib
mathtext — chemfig is TikZ and *cannot* be rendered by mathtext at all. The
live preview therefore compiles a real ``standalone`` document with tectonic
and rasterises the PDF (see ``build_preview_doc`` and the ChemfigEditorDialog
worker). The source the user builds is inserted verbatim as a RawLatex block,
so the compiled document draws native, vector chemfig.

``\\square`` doubles as the tab-navigable placeholder, exactly as in the
equation editor — it compiles fine inside ``\\chemfig{}`` (it renders as an
empty box until filled), so a half-built structure still previews.
"""
from __future__ import annotations

# Tab-navigable empty slot. Reused from the equation editor: it compiles
# inside \chemfig{} (as an empty box) so a partial structure still renders.
PLACEHOLDER = r"\square"
_S = PLACEHOLDER


# Each entry is `(latex_fragment, label)`. The fragment is inserted at the
# cursor in the source field; the label names the palette button. Some groups
# hold whole constructs (\chemfig{...}, \schemestart...\schemestop); others
# hold fragments meant to drop inside an existing \chemfig{}.
CHEMFIG_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Structures", [
        (r"\chemfig{" + _S + "}", "chemfig{}"),
        (r"\chemfig{*6(======)}", "benzene"),
        (r"\chemfig{CH_3-CH_2-OH}", "ethanol"),
        (r"\chemfig{[:30]CH_3O-C(=[:120]O)-CH(-[:-90]CH_3)-S-C(=[:120]S)-S-[4]CH_2CH_2CH_2CH_3}",
         "MBTPA"),
        (r"\chemfig{CH_2=CH-C(=[:120]O)-O-CH_2CH_2-R}", "acrylate"),
        (r"\chemfig{[6]-(-[2])(-[6])-[@{op}]CH_2-CH(-[6]C(=[:-120]O)-O-R)-[@{cl}]}",
         "repeat unit"),
    ]),
    ("Rings", [
        (r"*6(======)", "benzene"),
        (r"*6(------)", "cyclohexane"),
        (r"*5(-----)", "cyclopentane"),
        (r"*4(----)", "cyclobutane"),
        (r"*3(---)", "cyclopropane"),
        (r"**6(------)", "aromatic"),
    ]),
    ("Bonds", [
        (r"-", "single"),
        (r"=", "double"),
        (r"~", "triple"),
        (r"-[:30]", "angle"),
        (r">", "wedge up"),
        (r"<", "wedge down"),
        (r">:", "hash up"),
        (r"<:", "hash down"),
    ]),
    ("Groups", [
        (r"-OH", "hydroxyl"),
        (r"(=[:120]O)", "carbonyl"),
        (r"-C(=[:120]O)-OH", "carboxyl"),
        (r"-C(=[:120]O)-O-", "ester"),
        (r"-O-", "ether"),
        (r"-NH_2", "amine"),
        (r"-CH_3", "methyl"),
        (r"-C~N", "nitrile"),
    ]),
    ("Scheme", [
        (f"\\schemestart\n\\chemfig{{{_S}}}\n\\arrow\n\\chemfig{{{_S}}}\n\\schemestop",
         "A -> B"),
        (r"\arrow{->[\text{" + _S + "}]}", "arrow +label"),
        (r"\arrow{->[\text{" + _S + r"}][\text{" + _S + "}]}", "label +/-"),
        (r"\arrow{<=>}", "reversible"),
        (r"\+", "plus"),
        (f"\\schemestart\n\\chemfig{{{_S}}} \\+ \\chemfig{{{_S}}}\n"
         f"\\arrow{{->[\\text{{{_S}}}]}}\n\\chemfig{{{_S}}}\n\\schemestop",
         "A + B -> C"),
    ]),
    ("Polymer", [
        (r"-[@{op}]CH_2-CH(-[6]R)-[@{cl}]", "backbone"),
        (r"\polymerdelim[height=6pt,depth=6pt]{op}{cl}", "brackets"),
        (r"\polymerdelim[height=6pt,depth=6pt,indice=$n$]{op}{cl}", "bracket_n"),
        (r"\polymerdelim[height=6pt,depth=6pt,indice=$x$]{op}{cl}", "bracket_x"),
    ]),
]


def all_templates() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for _, items in CHEMFIG_GROUPS:
        out.extend(items)
    return out


# The extra packages a chemfig preview / document needs beyond chemfig itself.
# amssymb supplies \square (the placeholder); the polymer templates use it too.
_PREVIEW_PACKAGES = ("chemfig", "amssymb")


def build_preview_doc(body: str) -> str:
    """A minimal ``standalone`` document that draws *body* cropped to its
    bounding box, for the live-preview compile."""
    lines = [r"\documentclass[border=4pt]{standalone}"]
    lines += [f"\\usepackage{{{p}}}" for p in _PREVIEW_PACKAGES]
    lines += [r"\begin{document}", body.strip(), r"\end{document}", ""]
    return "\n".join(lines)
