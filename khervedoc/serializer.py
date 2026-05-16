"""Document model -> LaTeX source string.

Pure functions; one serializer per node type. No I/O.
"""
from __future__ import annotations

from .model import (
    Author, Block, Citation, CrossRef, Document, Figure, Footnote, Inline,
    Link, List as ListNode, ListItem, MathBlock, MathInline, Paragraph,
    RawLatex, Section, Table, Text, Title,
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


_ALIGN_ENVS = {"left": "flushleft", "center": "center", "right": "flushright"}


def serialize_block(node: Block) -> str:
    if isinstance(node, Paragraph):
        body = serialize_inlines(node.children)
        # LaTeX defaults to fully-justified text. If the editor shows the
        # paragraph as left/center/right-aligned we need to wrap it so the
        # PDF looks the same — otherwise "left" in the editor would render
        # as justified (with both edges flush) in the PDF.
        if node.alignment in _ALIGN_ENVS:
            env = _ALIGN_ENVS[node.alignment]
            return f"\\begin{{{env}}}\n{body}\n\\end{{{env}}}\n"
        # "justify" is LaTeX's natural default — no wrapper needed.
        return body + "\n"

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

    if isinstance(node, Title):
        # Title blocks emit \maketitle here; the actual \title{...} is set in
        # the preamble by serialize_document.
        return "\\maketitle\n"

    if isinstance(node, Author):
        # Author blocks are pulled into the preamble; they don't render in
        # the body. \maketitle (emitted by the Title block) will print them.
        return ""

    raise TypeError(f"Unknown block node: {type(node).__name__}")


_FONT_FAMILY_PACKAGES = {
    "default":  "",                  # Computer Modern, LaTeX default
    "times":    "\\usepackage{times}",
    "palatino": "\\usepackage{palatino}",
    "helvetica":"\\usepackage{helvet}\n\\renewcommand{\\familydefault}{\\sfdefault}",
    "courier":  "\\usepackage{courier}\n\\renewcommand{\\familydefault}{\\ttdefault}",
    "charter":  "\\usepackage[bitstream-charter]{mathdesign}",
    "libertine":"\\usepackage{libertine}",
}


def _body_font_pt_class_option(pt: int) -> str:
    """LaTeX article supports 10/11/12pt. Snap to the closest."""
    return f"{min((10, 11, 12), key=lambda v: abs(v - pt))}pt"


def serialize_document(doc: Document) -> str:
    from . import page_sizes
    page = page_sizes.by_code(doc.meta.page_size)
    m = doc.meta
    # Margins flow into geometry per-side so users can pick asymmetric layouts.
    geometry = (
        f"\\usepackage[{page.geometry_option},"
        f"top={m.margin_top_cm}cm,bottom={m.margin_bottom_cm}cm,"
        f"left={m.margin_left_cm}cm,right={m.margin_right_cm}cm]{{geometry}}"
    )
    font_pkg = _FONT_FAMILY_PACKAGES.get(m.body_font_family, "")
    spacing_pkg = "\\usepackage{setspace}"
    spacing_cmd = ""
    if abs(m.line_spacing - 1.0) > 0.01:
        if abs(m.line_spacing - 1.5) < 0.01:
            spacing_cmd = "\\onehalfspacing"
        elif abs(m.line_spacing - 2.0) < 0.01:
            spacing_cmd = "\\doublespacing"
        else:
            spacing_cmd = f"\\setstretch{{{m.line_spacing}}}"
    parindent = "" if m.paragraph_indent else "\\setlength{\\parindent}{0pt}\n\\setlength{\\parskip}{0.8em}"

    preamble_extras = "\n".join(p for p in (font_pkg, spacing_pkg, spacing_cmd, parindent) if p)
    packages = geometry + "\n" + "\n".join(
        f"\\usepackage{{{p}}}" for p in m.packages)
    if preamble_extras:
        packages += "\n" + preamble_extras

    # A Title block in the document body takes precedence over meta.title —
    # this lets the user pick the "Title" style inside the editor and have
    # the document title flow naturally into the LaTeX output.
    inline_title: str | None = None
    has_title_block = False
    inline_author: str | None = None
    for block in doc.children:
        if isinstance(block, Title) and inline_title is None:
            inline_title = serialize_inlines(block.children)
            has_title_block = True
        elif isinstance(block, Author) and inline_author is None:
            inline_author = serialize_inlines(block.children)
    title_text = inline_title if inline_title is not None else (
        escape_text((doc.meta.title or "").strip()))
    author_text = inline_author if inline_author is not None else (
        escape_text((doc.meta.author or "").strip()))

    has_metadata = bool(title_text or author_text)
    preamble_meta = ""
    if has_metadata:
        preamble_meta += f"\\title{{{title_text or '~'}}}\n"
        preamble_meta += f"\\author{{{author_text or '~'}}}\n"

    parts: list[str] = []
    emitted_maketitle = False
    for i, block in enumerate(doc.children):
        rendered = serialize_block(block)
        if isinstance(block, Title):
            emitted_maketitle = True
        parts.append(rendered)
        if i < len(doc.children) - 1:
            parts.append("\n")

    # If meta.title is set but no Title block exists in the body, fall back
    # to emitting \maketitle once at the top — preserves the previous
    # behaviour for documents created via the properties dialog.
    if has_metadata and not has_title_block and not emitted_maketitle:
        parts.insert(0, "\\maketitle\n")
    body = "".join(parts)

    return (
        f"\\documentclass[{_body_font_pt_class_option(m.body_font_pt)}]"
        f"{{{m.documentclass}}}\n"
        f"{packages}\n"
        f"{preamble_meta}"
        f"\\begin{{document}}\n"
        f"{body}"
        f"\\end{{document}}\n"
    )
