"""Document model -> Typst source string.

Pure functions; one serializer per node type. No I/O.
"""
from __future__ import annotations

import re

from .model import (
    Abstract, Author, Block, Citation, Comment, CrossRef, Document, Figure,
    Footnote, Frame, Highlight, HIGHLIGHT_COLORS, Inline, InlineRaw, Keywords,
    Link, List as ListNode, ListItem, MathBlock, MathInline, Paragraph,
    RawLatex, Section, Table, Text, Title,
)


# Characters that have special meaning in Typst markup and need escaping.
_TYPST_SPECIAL = set("#*_`@$\\<>[]~")


def escape_text(s: str) -> str:
    """Escape Typst special characters by prefixing with backslash."""
    return "".join(f"\\{ch}" if ch in _TYPST_SPECIAL else ch for ch in s)


# Mark wrappers — use function-call form to avoid ambiguity when nested.
_MARK_WRAPPERS = {
    "bold":          ("#strong[", "]"),
    "italic":        ("#emph[", "]"),
    "underline":     ("#underline[", "]"),
    "code":          ("`", "`"),
    "smallcaps":     ("#smallcaps[", "]"),
    "subscript":     ("#sub[", "]"),
    "superscript":   ("#super[", "]"),
    "strikethrough": ("#strike[", "]"),
}

_MARK_ORDER = ["bold", "italic", "underline", "smallcaps",
               "subscript", "superscript", "strikethrough", "code"]


def serialize_inline(node: Inline) -> str:
    if isinstance(node, Text):
        s = escape_text(node.text)
        for mark in reversed(_MARK_ORDER):
            if mark in node.marks:
                open_, close = _MARK_WRAPPERS[mark]
                s = f"{open_}{s}{close}"
        return s
    if isinstance(node, MathInline):
        return f"${node.latex}$"
    if isinstance(node, Link):
        body = serialize_inlines(node.children)
        if body:
            return f"#link(\"{node.url}\")[{body}]"
        return f"#link(\"{node.url}\")"
    if isinstance(node, Footnote):
        return f"#footnote[{serialize_inlines(node.children)}]"
    if isinstance(node, Citation):
        return " ".join(f"@{k}" for k in node.keys)
    if isinstance(node, CrossRef):
        return f"@{node.label}"
    if isinstance(node, InlineRaw):
        return node.latex
    if isinstance(node, Highlight):
        body = serialize_inlines(node.children)
        hexval = HIGHLIGHT_COLORS.get(node.color, "#FFFF00")
        return f"#highlight(fill: rgb(\"{hexval}\"))[{body}]"
    if isinstance(node, Comment):
        body = serialize_inlines(node.children)
        note = node.note.replace("*/", "* /")
        return f"{body} /* {note} */"
    raise TypeError(f"Unknown inline node: {type(node).__name__}")


def serialize_inlines(nodes: list[Inline]) -> str:
    return "".join(serialize_inline(n) for n in nodes)


def _maybe_label(label: str | None) -> str:
    return f" <{label}>" if label else ""


def serialize_block(node: Block) -> str:
    if isinstance(node, Paragraph):
        body = serialize_inlines(node.children)
        if node.alignment in ("left", "center", "right"):
            return f"#align({node.alignment})[{body}]\n"
        return body + "\n"

    if isinstance(node, Section):
        marker = "=" * max(1, node.level)
        body = serialize_inlines(node.children)
        if not node.numbered:
            return (f"#heading(level: {node.level}, "
                    f"numbering: none)[{body}]{_maybe_label(node.label)}\n")
        return f"{marker} {body}{_maybe_label(node.label)}\n"

    if isinstance(node, MathBlock):
        latex = node.latex.strip()
        # Strip LaTeX environment wrappers — Typst uses bare $ ... $
        stripped = _strip_math_env(latex)
        lab = _maybe_label(node.label)
        if node.numbered:
            return f"#math.equation(block: true, numbering: \"(1)\")[\n$ {stripped} $\n]{lab}\n"
        return f"$ {stripped} ${lab}\n"

    if isinstance(node, ListNode):
        marker = "+" if node.ordered else "-"
        items = "".join(
            f"{marker} {serialize_inlines(it.children)}\n" for it in node.items
        )
        return items

    if isinstance(node, Figure):
        path = node.path.replace("\\", "/")
        width_pct = _latex_width_to_typst(node.width)
        cap = escape_text(node.caption)
        lab = _maybe_label(node.label)
        parts = [f"#figure(\n  image(\"{path}\", width: {width_pct})"]
        if cap:
            parts.append(f",\n  caption: [{cap}]")
        parts.append(f"\n){lab}\n")
        return "".join(parts)

    if isinstance(node, Table):
        if not node.rows:
            return ""
        cols = max(len(r) for r in node.rows)
        cells: list[str] = []
        for r in node.rows:
            padded = list(r) + [""] * (cols - len(r))
            for c in padded:
                cells.append(f"[{escape_text(c)}]")
        cells_str = ", ".join(cells)
        cap = escape_text(node.caption)
        lab = _maybe_label(node.label)
        inner = f"table(columns: {cols}, {cells_str})"
        if cap:
            return f"#figure(\n  {inner},\n  caption: [{cap}]\n){lab}\n"
        return f"#{inner}{lab}\n"

    if isinstance(node, RawLatex):
        text = node.text
        if not text.endswith("\n"):
            text += "\n"
        safe = text.replace("*/", "* /")
        return f"/* Raw LaTeX:\n{safe}*/\n"

    if isinstance(node, Title):
        return ""

    if isinstance(node, Author):
        return ""

    if isinstance(node, Abstract):
        body = serialize_inlines(node.children)
        return (f"#block(width: 100%, inset: (x: 2em))[\n"
                f"  #text(size: 0.9em)[#emph[Abstract.] {body}]\n]\n")

    if isinstance(node, Keywords):
        body = serialize_inlines(node.children)
        return f"#strong[Keywords:] {body}\n"

    if isinstance(node, Frame):
        body = serialize_inlines(node.children)
        return f"#pagebreak()\n= {body}\n"

    raise TypeError(f"Unknown block node: {type(node).__name__}")


def _strip_math_env(latex: str) -> str:
    r"""Strip LaTeX math environment wrappers (\begin{equation}...\end{...})
    and return the inner content for Typst's $ ... $ delimiters."""
    m = re.match(r"\\begin\{[^}]+\}(.*?)\\end\{[^}]+\}", latex, re.DOTALL)
    if m:
        return m.group(1).strip()
    return latex


def _latex_width_to_typst(width: str) -> str:
    r"""Convert LaTeX width spec (e.g. '0.8\textwidth') to Typst percentage."""
    m = re.match(r"([\d.]+)\\textwidth", width)
    if m:
        pct = float(m.group(1)) * 100
        if pct == int(pct):
            return f"{int(pct)}%"
        return f"{pct}%"
    return "80%"


_FONT_FAMILY_MAP = {
    "default":   "",
    "times":     "Times New Roman",
    "palatino":  "Palatino Linotype",
    "helvetica": "Helvetica",
    "courier":   "Courier New",
    "charter":   "Charter",
    "libertine": "Linux Libertine",
}

_PAGE_SIZE_MAP = {
    "A4":      "\"a4\"",
    "A5":      "\"a5\"",
    "Letter":  "\"us-letter\"",
    "Legal":   "\"us-legal\"",
    "B5":      "\"iso-b5\"",
}


def serialize_document(doc: Document) -> str:
    m = doc.meta
    lines: list[str] = []

    # Document metadata
    title_text = ""
    author_text = ""
    for block in doc.children:
        if isinstance(block, Title) and not title_text:
            title_text = serialize_inlines(block.children)
        elif isinstance(block, Author) and not author_text:
            author_text = serialize_inlines(block.children)
    if not title_text:
        title_text = escape_text((m.title or "").strip())
    if not author_text:
        author_text = escape_text((m.author or "").strip())

    meta_parts: list[str] = []
    if title_text:
        meta_parts.append(f"title: \"{title_text}\"")
    if author_text:
        meta_parts.append(f"author: \"{author_text}\"")
    if meta_parts:
        lines.append(f"#set document({', '.join(meta_parts)})")

    # Page setup
    paper = _PAGE_SIZE_MAP.get(m.page_size, "\"a4\"")
    margin = (f"(top: {m.margin_top_cm}cm, bottom: {m.margin_bottom_cm}cm, "
              f"left: {m.margin_left_cm}cm, right: {m.margin_right_cm}cm)")
    page_opts = [f"paper: {paper}", f"margin: {margin}"]
    if getattr(m, "column_count", 1) >= 2:
        page_opts.append(f"columns: {m.column_count}")
    lines.append(f"#set page({', '.join(page_opts)})")

    # Text setup
    text_opts = [f"size: {m.body_font_pt}pt"]
    font_name = _FONT_FAMILY_MAP.get(m.body_font_family, "")
    if font_name:
        text_opts.append(f"font: \"{font_name}\"")
    lines.append(f"#set text({', '.join(text_opts)})")

    # Paragraph setup
    par_opts: list[str] = ["justify: true"]
    if abs(m.line_spacing - 1.0) > 0.01:
        leading = 0.65 * m.line_spacing
        par_opts.append(f"leading: {leading:.2f}em")
    if m.paragraph_indent:
        par_opts.append("first-line-indent: 1em")
    lines.append(f"#set par({', '.join(par_opts)})")

    # Heading numbering
    lines.append("#set heading(numbering: \"1.1\")")

    lines.append("")  # blank line before body

    # Title block
    if title_text:
        lines.append(f"#align(center, text(size: 17pt, weight: \"bold\")[{title_text}])")
    if author_text:
        lines.append(f"#align(center, text(size: 12pt)[{author_text}])")
    if title_text or author_text:
        lines.append("")

    # Body
    children = doc.children
    n = len(children)
    i = 0
    while i < n:
        block = children[i]
        if isinstance(block, (Title, Author)):
            i += 1
            continue
        # Merge consecutive Abstract blocks
        if isinstance(block, Abstract):
            paras: list[str] = []
            while i < n and isinstance(children[i], Abstract):
                paras.append(serialize_inlines(children[i].children))
                i += 1
            joined = "\n\n".join(p for p in paras if p)
            lines.append(
                f"#block(width: 100%, inset: (x: 2em))[\n"
                f"  #text(size: 0.9em)[#emph[Abstract.] {joined}]\n]")
            lines.append("")
            continue
        # Merge consecutive Keywords blocks
        if isinstance(block, Keywords):
            parts: list[str] = []
            while i < n and isinstance(children[i], Keywords):
                parts.append(serialize_inlines(children[i].children))
                i += 1
            joined = " · ".join(p for p in parts if p)
            lines.append(f"#strong[Keywords:] {joined}")
            lines.append("")
            continue
        rendered = serialize_block(block)
        lines.append(rendered)
        i += 1

    return "\n".join(lines) + "\n"
