"""Document model — the single source of truth.

Everything (editor, serializer, git layer) reads and writes this tree.
JSON-serializable. No Qt or LaTeX knowledge here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Literal, Union


Mark = Literal["bold", "italic", "underline", "code", "smallcaps",
               "subscript", "superscript", "strikethrough"]


@dataclass
class Text:
    text: str
    marks: list[Mark] = field(default_factory=list)
    type: str = "Text"


@dataclass
class MathInline:
    latex: str
    type: str = "MathInline"


Inline = Union[Text, MathInline]


@dataclass
class Paragraph:
    children: list[Inline] = field(default_factory=list)
    type: str = "Paragraph"


@dataclass
class Section:
    level: int = 1                     # 1..5  (\section, \subsection, ...)
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
class RawLatex:
    text: str
    type: str = "RawLatex"


Block = Union[Paragraph, Section, MathBlock, RawLatex]


@dataclass
class DocMeta:
    title: str = "Untitled"
    author: str = ""
    documentclass: str = "article"
    packages: list[str] = field(default_factory=lambda: ["amsmath", "graphicx"])


@dataclass
class Document:
    children: list[Block] = field(default_factory=list)
    meta: DocMeta = field(default_factory=DocMeta)
    type: str = "Document"


# ---------- JSON serialization ----------

def to_json(doc: Document) -> str:
    return json.dumps(asdict(doc), indent=2, ensure_ascii=False)


def from_json(s: str) -> Document:
    raw = json.loads(s)
    return _build_document(raw)


_INLINE_BUILDERS = {
    "Text": lambda d: Text(text=d["text"], marks=list(d.get("marks", []))),
    "MathInline": lambda d: MathInline(latex=d["latex"]),
}


def _build_inlines(items: list[dict]) -> list[Inline]:
    out: list[Inline] = []
    for item in items:
        builder = _INLINE_BUILDERS.get(item["type"])
        if builder is None:
            raise ValueError(f"Unknown inline node type: {item['type']!r}")
        out.append(builder(item))
    return out


def _build_block(d: dict) -> Block:
    t = d["type"]
    if t == "Paragraph":
        return Paragraph(children=_build_inlines(d.get("children", [])))
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
    if t == "RawLatex":
        return RawLatex(text=d["text"])
    raise ValueError(f"Unknown block node type: {t!r}")


def _build_document(d: dict) -> Document:
    meta_d = d.get("meta", {})
    meta = DocMeta(
        title=meta_d.get("title", "Untitled"),
        author=meta_d.get("author", ""),
        documentclass=meta_d.get("documentclass", "article"),
        packages=list(meta_d.get("packages", ["amsmath", "graphicx"])),
    )
    return Document(
        children=[_build_block(b) for b in d.get("children", [])],
        meta=meta,
    )
