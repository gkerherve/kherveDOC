"""Document model — the single source of truth.

JSON-serialisable, no Qt or LaTeX dependencies. Editor and serializer both
read and write this tree.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Literal, Union


Mark = Literal["bold", "italic", "underline", "code", "smallcaps",
               "subscript", "superscript", "strikethrough"]


# ---------------- Inline nodes ----------------

@dataclass
class Text:
    text: str
    marks: list[Mark] = field(default_factory=list)
    type: str = "Text"


@dataclass
class MathInline:
    latex: str
    type: str = "MathInline"


@dataclass
class Link:
    url: str
    children: list["Inline"] = field(default_factory=list)
    type: str = "Link"


@dataclass
class Footnote:
    children: list["Inline"] = field(default_factory=list)
    type: str = "Footnote"


@dataclass
class Citation:
    keys: list[str] = field(default_factory=list)
    style: Literal["cite", "citep", "citet"] = "cite"
    type: str = "Citation"


@dataclass
class CrossRef:
    label: str = ""
    kind: Literal["ref", "eqref", "pageref"] = "ref"
    type: str = "CrossRef"


@dataclass
class InlineRaw:
    """Verbatim LaTeX inline. The importer emits these for unknown macros
    (\\Kstroke, \\textcolor{...}{...}, custom \\newcommand-defined names,
    etc.) so they survive a round-trip instead of being silently dropped.
    The Symbol palette also inserts text-mode macros this way."""
    latex: str = ""
    type: str = "InlineRaw"


Inline = Union[Text, MathInline, Link, Footnote, Citation, CrossRef, InlineRaw]


# ---------------- Block nodes ----------------

Alignment = Literal["left", "center", "right", "justify"]


@dataclass
class Paragraph:
    children: list[Inline] = field(default_factory=list)
    alignment: Alignment = "left"
    type: str = "Paragraph"


@dataclass
class Section:
    level: int = 1
    children: list[Inline] = field(default_factory=list)
    numbered: bool = True
    label: str | None = None
    type: str = "Section"


@dataclass
class MathBlock:
    latex: str
    numbered: bool = False
    label: str | None = None
    type: str = "MathBlock"


@dataclass
class ListItem:
    children: list[Inline] = field(default_factory=list)
    type: str = "ListItem"


@dataclass
class List:
    ordered: bool = False
    items: list[ListItem] = field(default_factory=list)
    type: str = "List"


@dataclass
class Figure:
    path: str = ""
    caption: str = ""
    label: str | None = None
    width: str = "0.8\\textwidth"
    type: str = "Figure"


@dataclass
class Table:
    rows: list[list[str]] = field(default_factory=list)   # each cell = plain text
    caption: str = ""
    label: str | None = None
    alignment: str = ""           # e.g. "lcr"; empty = auto (all left)
    type: str = "Table"


@dataclass
class RawLatex:
    text: str
    type: str = "RawLatex"


@dataclass
class Title:
    """Document title paragraph — like Word's "Title" style. Becomes
    \\title{...}\\maketitle in the LaTeX output (only the first one wins;
    subsequent Title blocks are still rendered, last definition takes)."""
    children: list[Inline] = field(default_factory=list)
    type: str = "Title"


@dataclass
class Author:
    """Document author paragraph — like Word's "Author" / "Subtitle" style.
    First Author block's content drives \\author{...} in the preamble; the
    same \\maketitle that the Title block already emits will use it."""
    children: list[Inline] = field(default_factory=list)
    type: str = "Author"


@dataclass
class Abstract:
    """One paragraph of the document's Abstract. Consecutive Abstract
    blocks are merged into a single \\begin{abstract}...\\end{abstract}
    environment on serialization, so multi-paragraph abstracts work
    without each paragraph getting its own env."""
    children: list[Inline] = field(default_factory=list)
    type: str = "Abstract"


@dataclass
class Keywords:
    """One keyword line. Consecutive Keywords blocks are merged into a
    single \\begin{keyword}...\\end{keyword} env. Inside that env the
    serialiser uses \\sep between keyword groups so Elsevier-style
    journals format correctly."""
    children: list[Inline] = field(default_factory=list)
    type: str = "Keywords"


Block = Union[Paragraph, Section, MathBlock, List, Figure, Table, RawLatex,
              Title, Author, Abstract, Keywords]


# ---------------- Metadata + document ----------------

# amssymb provides \square (and other math symbols) — required because the
# equation-builder palette uses \square as the placeholder slot for users
# to fill in. Without it, every freshly-inserted template raises an
# "Undefined control sequence \square" error from tectonic.
DEFAULT_PACKAGES = ["amsmath", "amssymb", "graphicx", "multicol"]


@dataclass
class DocMeta:
    title: str = "Untitled"
    author: str = ""
    documentclass: str = "article"
    packages: list[str] = field(default_factory=lambda: list(DEFAULT_PACKAGES))
    page_size: str = "A4"        # short code from khervedoc.page_sizes
    # Page margins in centimetres, fed straight into the geometry package.
    margin_top_cm: float = 2.5
    margin_bottom_cm: float = 2.5
    margin_left_cm: float = 2.5
    margin_right_cm: float = 2.5
    # Body type size — the LaTeX article class only accepts 10 / 11 / 12 pt
    # as a class option; anything else is rounded to the nearest of those.
    body_font_pt: int = 12
    # Font family. "default" leaves Computer Modern in place. Other values
    # map to the loaded packages — see serializer._FONT_FAMILY_PACKAGES.
    body_font_family: str = "default"
    # Line spacing multiplier — 1.0 single, 1.15 / 1.5 / 2.0 typical.
    line_spacing: float = 1.0
    # Indent the first line of each paragraph? Most modern docs prefer no
    # indent with extra paragraph spacing; LaTeX's default is the opposite.
    paragraph_indent: bool = True
    # When true, pass `twocolumn` to \documentclass so the whole document
    # flows in two columns. Independent from in-flow \begin{multicols}{2}
    # regions, which the user inserts via Insert > Multi-column region.
    two_column: bool = False
    # Verbatim LaTeX to drop inside \begin{frontmatter} (Elsevier classes)
    # alongside the model-driven title / author / abstract / keyword envs.
    # Captures \author[opts]{... \corref{...}}, \ead, \cortext, \affiliation
    # and similar commands the model doesn't natively represent.
    frontmatter_extras: str = ""
    # Verbatim LaTeX to drop after \usepackage{...} and before
    # \begin{document}. Captures preamble customisation we don't model,
    # most importantly \lstset{...} (listings styling — frame, line
    # numbers, syntax-colour keywordstyle/commentstyle/stringstyle),
    # \definecolor, \hypersetup, \newcommand, \theoremstyle, etc.
    preamble_extras: str = ""


@dataclass
class Document:
    children: list[Block] = field(default_factory=list)
    meta: DocMeta = field(default_factory=DocMeta)
    type: str = "Document"


# ---------------- JSON serialisation ----------------

def to_json(doc: Document) -> str:
    return json.dumps(asdict(doc), indent=2, ensure_ascii=False)


def from_json(s: str) -> Document:
    return _build_document(json.loads(s))


def _build_inline(d: dict) -> Inline:
    t = d["type"]
    if t == "Text":
        return Text(text=d["text"], marks=list(d.get("marks", [])))
    if t == "MathInline":
        return MathInline(latex=d["latex"])
    if t == "Link":
        return Link(url=d.get("url", ""), children=_build_inlines(d.get("children", [])))
    if t == "Footnote":
        return Footnote(children=_build_inlines(d.get("children", [])))
    if t == "Citation":
        return Citation(keys=list(d.get("keys", [])), style=d.get("style", "cite"))
    if t == "CrossRef":
        return CrossRef(label=d.get("label", ""), kind=d.get("kind", "ref"))
    if t == "InlineRaw":
        return InlineRaw(latex=d.get("latex", ""))
    raise ValueError(f"Unknown inline node type: {t!r}")


def _build_inlines(items: list[dict]) -> list[Inline]:
    return [_build_inline(i) for i in items]


def _build_block(d: dict) -> Block:
    t = d["type"]
    if t == "Paragraph":
        return Paragraph(
            children=_build_inlines(d.get("children", [])),
            alignment=d.get("alignment", "left"),
        )
    if t == "Section":
        return Section(
            level=d.get("level", 1),
            children=_build_inlines(d.get("children", [])),
            numbered=d.get("numbered", True),
            label=d.get("label"),
        )
    if t == "MathBlock":
        return MathBlock(
            latex=d["latex"],
            numbered=d.get("numbered", False),
            label=d.get("label"),
        )
    if t == "List":
        return List(
            ordered=d.get("ordered", False),
            items=[ListItem(children=_build_inlines(it.get("children", [])))
                   for it in d.get("items", [])],
        )
    if t == "Figure":
        return Figure(
            path=d.get("path", ""),
            caption=d.get("caption", ""),
            label=d.get("label"),
            width=d.get("width", "0.8\\textwidth"),
        )
    if t == "Table":
        return Table(
            rows=[[str(c) for c in row] for row in d.get("rows", [])],
            caption=d.get("caption", ""),
            label=d.get("label"),
            alignment=d.get("alignment", ""),
        )
    if t == "RawLatex":
        return RawLatex(text=d["text"])
    if t == "Title":
        return Title(children=_build_inlines(d.get("children", [])))
    if t == "Author":
        return Author(children=_build_inlines(d.get("children", [])))
    if t == "Abstract":
        return Abstract(children=_build_inlines(d.get("children", [])))
    if t == "Keywords":
        return Keywords(children=_build_inlines(d.get("children", [])))
    raise ValueError(f"Unknown block node type: {t!r}")


def _build_document(d: dict) -> Document:
    meta_d = d.get("meta", {})
    meta = DocMeta(
        title=meta_d.get("title", "Untitled"),
        author=meta_d.get("author", ""),
        documentclass=meta_d.get("documentclass", "article"),
        packages=list(meta_d.get("packages", list(DEFAULT_PACKAGES))),
        page_size=meta_d.get("page_size", "A4"),
        margin_top_cm=float(meta_d.get("margin_top_cm", 2.5)),
        margin_bottom_cm=float(meta_d.get("margin_bottom_cm", 2.5)),
        margin_left_cm=float(meta_d.get("margin_left_cm", 2.5)),
        margin_right_cm=float(meta_d.get("margin_right_cm", 2.5)),
        body_font_pt=int(meta_d.get("body_font_pt", 12)),
        body_font_family=str(meta_d.get("body_font_family", "default")),
        line_spacing=float(meta_d.get("line_spacing", 1.0)),
        paragraph_indent=bool(meta_d.get("paragraph_indent", True)),
        two_column=bool(meta_d.get("two_column", False)),
        frontmatter_extras=str(meta_d.get("frontmatter_extras", "")),
        preamble_extras=str(meta_d.get("preamble_extras", "")),
    )
    return Document(
        children=[_build_block(b) for b in d.get("children", [])],
        meta=meta,
    )
