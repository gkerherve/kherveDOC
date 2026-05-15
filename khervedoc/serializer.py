"""Document model -> LaTeX source string.

Pure functions; one serializer per node type. No I/O.
"""
from __future__ import annotations

from .model import (
    Block, Citation, CrossRef, Document, Figure, Footnote, Inline, Link,
    List as ListNode, ListItem, MathBlock, MathInline, Paragraph, RawLatex,
    Section, Table, Text,
)


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
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in s)


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

# Outermost-first; iteration reverses so first mark in this list wraps last.
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
        body = serialize_inlines(node.children) or escape_text(node.url)
        return f"\\href{{{node.url}}}{{{body}}}"
    if isinstance(node, Footnote):
        return f"\\footnote{{{serialize_inlines(node.children)}}}"
    if isinstance(node, Citation):
        keys = ",".join(node.keys)
        return f"\\{node.style}{{{keys}}}"
    if isinstance(node, CrossRef):
        return f"\\{node.kind}{{{node.label}}}"
    raise TypeError(f"Unknown inline node: {type(node).__name__}")


def serialize_inlines(nodes: list[Inline]) -> str:
    return "".join(serialize_inline(n) for n in nodes)


_SECTION_COMMANDS = {
    1: "section", 2: "subsection", 3: "subsubsection",
    4: "paragraph", 5: "subparagraph",
}


def _maybe_label(label: str | None) -> str:
    return f"\\label{{{label}}}\n" if label else ""


def serialize_block(node: Block) -> str:
    if isinstance(node, Paragraph):
        return serialize_inlines(node.children) + "\n"

    if isinstance(node, Section):
        cmd = _SECTION_COMMANDS.get(max(1, min(5, node.level)), "section")
        star = "" if node.numbered else "*"
        body = serialize_inlines(node.children)
        return f"\\{cmd}{star}{{{body}}}\n{_maybe_label(node.label)}"

    if isinstance(node, MathBlock):
        env = "equation" if node.numbered else "equation*"
        lab = _maybe_label(node.label) if node.numbered else ""
        return f"\\begin{{{env}}}\n{lab}{node.latex}\n\\end{{{env}}}\n"

    if isinstance(node, ListNode):
        env = "enumerate" if node.ordered else "itemize"
        items = "".join(
            f"  \\item {serialize_inlines(it.children)}\n" for it in node.items
        )
        return f"\\begin{{{env}}}\n{items}\\end{{{env}}}\n"

    if isinstance(node, Figure):
        # Use forward slashes in the path — LaTeX dislikes backslashes.
        path = node.path.replace("\\", "/")
        cap = escape_text(node.caption)
        lab = _maybe_label(node.label) if node.label else ""
        return (
            "\\begin{figure}[h]\n"
            "  \\centering\n"
            f"  \\includegraphics[width={node.width}]{{{path}}}\n"
            f"  \\caption{{{cap}}}\n"
            f"  {lab}"
            "\\end{figure}\n"
        )

    if isinstance(node, Table):
        if not node.rows:
            return ""
        cols = max(len(r) for r in node.rows)
        align = node.alignment.strip() or ("l" * cols)
        # Pad short rows with empty cells.
        body_rows: list[str] = []
        for r in node.rows:
            cells = [escape_text(c) for c in r] + [""] * (cols - len(r))
            body_rows.append(" & ".join(cells) + r" \\")
        body = "\n    ".join(body_rows)
        cap = escape_text(node.caption)
        lab = _maybe_label(node.label) if node.label else ""
        return (
            "\\begin{table}[h]\n"
            "  \\centering\n"
            f"  \\begin{{tabular}}{{{align}}}\n"
            f"    \\hline\n"
            f"    {body}\n"
            f"    \\hline\n"
            "  \\end{tabular}\n"
            f"  \\caption{{{cap}}}\n"
            f"  {lab}"
            "\\end{table}\n"
        )

    if isinstance(node, RawLatex):
        return node.text + ("\n" if not node.text.endswith("\n") else "")

    raise TypeError(f"Unknown block node: {type(node).__name__}")


def serialize_document(doc: Document) -> str:
    packages = "\n".join(f"\\usepackage{{{p}}}" for p in doc.meta.packages)
    title = (doc.meta.title or "").strip()
    author = (doc.meta.author or "").strip()

    # Skip \title/\author entirely if both are empty — some packages break on
    # "\maketitle" with empty metadata.
    title_block = ""
    if title or author:
        title_block += f"\\title{{{escape_text(title) or '~'}}}\n"
        title_block += f"\\author{{{escape_text(author) or '~'}}}\n"
    maketitle = "\\maketitle\n" if (title or author) else ""

    parts: list[str] = []
    for i, block in enumerate(doc.children):
        parts.append(serialize_block(block))
        if i < len(doc.children) - 1:
            parts.append("\n")
    body = "".join(parts)

    return (
        f"\\documentclass{{{doc.meta.documentclass}}}\n"
        f"{packages}\n"
        f"{title_block}"
        f"\\begin{{document}}\n"
        f"{maketitle}"
        f"{body}"
        f"\\end{{document}}\n"
    )
