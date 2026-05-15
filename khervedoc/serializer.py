"""Serializes a Document model to a LaTeX source string.

Pure functions, no I/O. One serializer per node type.
"""
from __future__ import annotations

from .model import (
    Document, Section, Paragraph, MathBlock, RawLatex,
    Text, MathInline, Block, Inline,
)


# Characters that have special meaning in LaTeX and must be escaped in text runs.
# Backslash and braces are handled separately because their replacements contain
# backslashes themselves and would otherwise be double-escaped.
_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_text(s: str) -> str:
    # Process backslash first to avoid re-escaping the backslashes we introduce.
    out = []
    for ch in s:
        out.append(_LATEX_ESCAPES.get(ch, ch))
    return "".join(out)


_MARK_WRAPPERS = {
    "bold": (r"\textbf{", "}"),
    "italic": (r"\textit{", "}"),
    "underline": (r"\underline{", "}"),
    "code": (r"\texttt{", "}"),
    "smallcaps": (r"\textsc{", "}"),
    "subscript": (r"\textsubscript{", "}"),
    "superscript": (r"\textsuperscript{", "}"),
    "strikethrough": (r"\sout{", "}"),
}

# Mark application order — outermost first. Nesting order is stable so output is
# deterministic regardless of the order marks appear in the model.
_MARK_ORDER = ["bold", "italic", "underline", "smallcaps",
               "subscript", "superscript", "strikethrough", "code"]


def serialize_inline(node: Inline) -> str:
    if isinstance(node, Text):
        s = escape_text(node.text)
        # Apply in reverse priority so the first mark in _MARK_ORDER ends up
        # as the outermost wrapper (deterministic, regardless of input order).
        for mark in reversed(_MARK_ORDER):
            if mark in node.marks:
                open_, close = _MARK_WRAPPERS[mark]
                s = f"{open_}{s}{close}"
        return s
    if isinstance(node, MathInline):
        # The math body is raw LaTeX by design — do not escape.
        return f"${node.latex}$"
    raise TypeError(f"Unknown inline node: {type(node).__name__}")


def serialize_inlines(nodes: list[Inline]) -> str:
    return "".join(serialize_inline(n) for n in nodes)


_SECTION_COMMANDS = {
    1: "section",
    2: "subsection",
    3: "subsubsection",
    4: "paragraph",
    5: "subparagraph",
}


def serialize_block(node: Block) -> str:
    if isinstance(node, Paragraph):
        return serialize_inlines(node.children) + "\n"
    if isinstance(node, Section):
        cmd = _SECTION_COMMANDS.get(max(1, min(5, node.level)), "section")
        star = "" if node.numbered else "*"
        body = serialize_inlines(node.children)
        label = f"\\label{{{node.label}}}\n" if node.label else ""
        return f"\\{cmd}{star}{{{body}}}\n{label}"
    if isinstance(node, MathBlock):
        env = "equation" if node.numbered else "equation*"
        label = f"\\label{{{node.label}}}\n" if (node.numbered and node.label) else ""
        return f"\\begin{{{env}}}\n{label}{node.latex}\n\\end{{{env}}}\n"
    if isinstance(node, RawLatex):
        return node.text + ("\n" if not node.text.endswith("\n") else "")
    raise TypeError(f"Unknown block node: {type(node).__name__}")


def serialize_document(doc: Document) -> str:
    packages = "\n".join(f"\\usepackage{{{p}}}" for p in doc.meta.packages)
    title = (doc.meta.title or "").strip()
    author = (doc.meta.author or "").strip()

    # Only emit \title / \author / \maketitle when there is real content.
    # Empty values plus hyperref can fail with "Missing $ inserted" because
    # some packages try to typeset the empty metadata as math.
    title_block = ""
    if title or author:
        title_block += f"\\title{{{escape_text(title) or '~'}}}\n"
        title_block += f"\\author{{{escape_text(author) or '~'}}}\n"

    body_parts: list[str] = []
    for i, block in enumerate(doc.children):
        body_parts.append(serialize_block(block))
        if i < len(doc.children) - 1:
            body_parts.append("\n")
    body = "".join(body_parts)

    maketitle = "\\maketitle\n" if (title or author) else ""

    return (
        f"\\documentclass{{{doc.meta.documentclass}}}\n"
        f"{packages}\n"
        f"{title_block}"
        f"\\begin{{document}}\n"
        f"{maketitle}"
        f"{body}"
        f"\\end{{document}}\n"
    )
