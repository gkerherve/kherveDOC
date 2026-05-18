"""Document model -> LaTeX source string.

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
    if isinstance(node, InlineRaw):
        return node.latex
    if isinstance(node, Highlight):
        body = serialize_inlines(node.children)
        color_name = f"hl{node.color.capitalize()}"
        return f"\\colorbox{{{color_name}}}{{{body}}}"
    if isinstance(node, Comment):
        body = serialize_inlines(node.children)
        escaped_note = node.note.replace("{", "\\{").replace("}", "\\}")
        author_opt = f", author={{{node.author}}}" if node.author else ""
        return f"{body}\\todo[color=blue!20{author_opt}]{{{escaped_note}}}"
    raise TypeError(f"Unknown inline node: {type(node).__name__}")


def serialize_inlines(nodes: list[Inline]) -> str:
    return "".join(serialize_inline(n) for n in nodes)


_SECTION_COMMANDS = {
    0: "chapter",  # only valid in report / book / memoir classes
    1: "section", 2: "subsection", 3: "subsubsection",
    4: "paragraph", 5: "subparagraph",
}


def _maybe_label(label: str | None) -> str:
    return f"\\label{{{label}}}\n" if label else ""


_ALIGN_ENVS = {"left": "flushleft", "center": "center", "right": "flushright"}


_CHAPTER_CLASSES = {"report", "book", "memoir"}


def serialize_block(node: Block, *, has_chapters: bool = False) -> str:
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
        # For report/book/memoir classes, level 1 in the model becomes
        # \chapter (level 0 in _SECTION_COMMANDS) so that the editor's
        # "Heading 1" maps to the document class's top-level division.
        effective = node.level - 1 if has_chapters else node.level
        cmd = _SECTION_COMMANDS.get(max(0, min(5, effective)), "section")
        star = "" if node.numbered else "*"
        body = serialize_inlines(node.children)
        return f"\\{cmd}{star}{{{body}}}\n{_maybe_label(node.label)}"

    if isinstance(node, MathBlock):
        # The importer stores non-equation envs (align*, gather, split, ...)
        # as a complete \begin{env}...\end{env} string inside node.latex,
        # so re-wrapping in equation/equation* would produce illegal
        # \begin{equation*}\begin{align*}...\end{align*}\end{equation*}
        # nesting and break compilation. Detect a pre-wrapped body and
        # emit it verbatim instead.
        stripped = node.latex.lstrip()
        if stripped.startswith("\\begin{"):
            return f"{node.latex}\n"
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

    if isinstance(node, Abstract):
        # Defensive single-block path. serialize_document collects
        # consecutive Abstract blocks before reaching here, so this only
        # fires if a caller invokes serialize_block on a lone Abstract.
        return (f"\\begin{{abstract}}\n"
                f"{serialize_inlines(node.children)}\n"
                f"\\end{{abstract}}\n")

    if isinstance(node, Keywords):
        return (f"\\begin{{keyword}}\n"
                f"{serialize_inlines(node.children)}\n"
                f"\\end{{keyword}}\n")

    if isinstance(node, Frame):
        return serialize_inlines(node.children)

    raise TypeError(f"Unknown block node: {type(node).__name__}")


# --- Review-feature helpers (highlight / comment package injection) ---

def _collect_review_usage(doc: Document) -> tuple[set[str], bool]:
    """Walk the document tree and return (highlight_colors_used, has_comments)."""
    colors: set[str] = set()
    has_comments = False

    def _walk_inlines(nodes: list[Inline]) -> None:
        nonlocal has_comments
        for node in nodes:
            if isinstance(node, Highlight):
                colors.add(node.color)
                _walk_inlines(node.children)
            elif isinstance(node, Comment):
                has_comments = True
                _walk_inlines(node.children)
            elif isinstance(node, (Link, Footnote)):
                _walk_inlines(node.children)

    from .model import (List as ListModel, ListItem as LI,
                        Paragraph as P, Section as S, Title as T,
                        Author as Au, Abstract as Ab, Keywords as Kw)
    for block in doc.children:
        if hasattr(block, "children") and not isinstance(block, (Figure, Table)):
            if isinstance(block, ListModel):
                for item in block.items:
                    _walk_inlines(item.children)
            else:
                _walk_inlines(block.children)
    return colors, has_comments


def _review_preamble(colors_used: set[str], has_comments: bool) -> str:
    """Return extra preamble lines for review features (definecolor, packages)."""
    lines: list[str] = []
    if colors_used:
        lines.append("\\usepackage{xcolor}")
        for name, hexval in HIGHLIGHT_COLORS.items():
            if name in colors_used:
                clean = hexval.lstrip("#")
                lines.append(f"\\definecolor{{hl{name.capitalize()}}}{{HTML}}{{{clean}}}")
    if has_comments:
        lines.append("\\usepackage[colorinlistoftodos]{todonotes}")
    return "\n".join(lines)


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


def _class_options(m) -> str:
    """Comma-joined documentclass options: font size, twocolumn, etc."""
    opts = [_body_font_pt_class_option(m.body_font_pt)]
    if getattr(m, "column_count", 1) == 2:
        opts.append("twocolumn")
    return ",".join(opts)


def _wrap_multicols(body: str, n: int) -> str:
    """Wrap the body in \\begin{multicols}{n}...\\end{multicols}. Used
    for column counts that the documentclass can't express natively
    (i.e. 3+, since LaTeX's `twocolumn` only does 2)."""
    return f"\\begin{{multicols}}{{{n}}}\n{body}\\end{{multicols}}\n"


# KherveTeX-provided macros. \providecommand (not \newcommand) so that
# imported documents which already define \Kstroke in their preamble
# survive the round-trip without a "command already defined" error.
# \rotatebox needs graphicx, which is in DEFAULT_PACKAGES.
_KSTROKE_PROVIDE = (
    r"\providecommand{\Kstroke}"
    r"{K\hspace{-0.55em}\raisebox{-0.5ex}{\rotatebox{40}{--}}\hspace{-0.1em}}"
)


def _split_keyword_inlines(blocks: list) -> list[str]:
    r"""Given one or more consecutive Keywords blocks, flatten their
    inlines and split into individual keyword terms.

    The importer combines all of an env's keywords into one Keywords
    block separated by Text(" · ") fragments so the editor can show
    them on a single line. To re-emit the elsarticle-friendly
    `kw \sep kw \sep kw` form, we serialize the inlines and split on
    the visible bullet separator. Multiple input blocks (the legacy
    one-per-term form) are accepted too.
    """
    out: list[str] = []
    for block in blocks:
        line = serialize_inlines(block.children).strip()
        if not line: continue
        for term in line.split(" · "):
            term = term.strip(" \t\n")
            if term:
                out.append(term)
    return out


def serialize_document(doc: Document) -> str:
    from . import page_sizes
    page = page_sizes.by_code(doc.meta.page_size)
    m = doc.meta
    is_elsarticle = (m.documentclass or "").lower().startswith("elsarticle")
    is_beamer = (m.documentclass or "").lower() == "beamer"
    has_chapters = (m.documentclass or "").lower() in _CHAPTER_CLASSES

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
    # User-supplied preamble customisation (\lstset for listings styling,
    # \definecolor, \hypersetup, \newcommand etc.) — preserved verbatim
    # from the imported .tex so the PDF keeps its framed line-numbered
    # syntax-coloured code blocks and any other custom rendering.
    if m.preamble_extras and m.preamble_extras.strip():
        packages += "\n" + m.preamble_extras.strip()
    # \Kstroke is provided AFTER preamble_extras so that documents
    # importing their own \newcommand{\Kstroke}{...} keep theirs and
    # ours becomes a no-op. The reverse order produced a "command
    # already defined" error because \newcommand (unlike
    # \providecommand) refuses to redefine an existing macro.
    packages += "\n" + _KSTROKE_PROVIDE

    # Review features: highlight colours + todonotes
    hl_colors, has_comments = _collect_review_usage(doc)
    review_preamble = _review_preamble(hl_colors, has_comments)
    if review_preamble:
        packages += "\n" + review_preamble

    # Pull title / author content out of the body (or fall back to meta).
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

    # elsarticle and the other Elsevier classes require title / author /
    # abstract / keywords all to live inside \begin{frontmatter} ...
    # \end{frontmatter}. Anything outside that block is silently dropped
    # by the class — which was why the user's abstract didn't reach the
    # PDF. For these classes we collect the front matter explicitly and
    # emit the rest of the document as body.
    if is_elsarticle:
        abstract_blocks: list = []
        keywords_blocks: list = []
        body_blocks: list = []
        for block in doc.children:
            if isinstance(block, (Title, Author)):
                continue   # handled via title_text / author_text
            if isinstance(block, Abstract):
                abstract_blocks.append(block); continue
            if isinstance(block, Keywords):
                keywords_blocks.append(block); continue
            body_blocks.append(block)

        front_parts: list[str] = []
        if title_text:
            front_parts.append(f"\\title{{{title_text}}}")
        # If the imported source had its own \author[opts]{...\corref{...}},
        # that lives verbatim in meta.frontmatter_extras and we mustn't emit
        # a second plain \author{...} alongside it.
        extras = (m.frontmatter_extras or "").strip()
        extras_has_author = bool(re.search(r"\\author\b", extras))
        if author_text and not extras_has_author:
            front_parts.append(f"\\author{{{author_text}}}")
        if extras:
            front_parts.append(extras)
        if abstract_blocks:
            paras = [serialize_inlines(b.children) for b in abstract_blocks]
            joined = "\n\n".join(p for p in paras if p)
            front_parts.append(f"\\begin{{abstract}}\n{joined}\n\\end{{abstract}}")
        if keywords_blocks:
            terms = _split_keyword_inlines(keywords_blocks)
            if terms:
                joined = " \\sep ".join(terms)
                front_parts.append(f"\\begin{{keyword}}\n{joined}\n\\end{{keyword}}")
        frontmatter = (
            "\\begin{frontmatter}\n" + "\n\n".join(front_parts) +
            "\n\\end{frontmatter}\n") if front_parts else ""

        body_parts: list[str] = []
        for i, b in enumerate(body_blocks):
            body_parts.append(serialize_block(b, has_chapters=has_chapters))
            if i < len(body_blocks) - 1:
                body_parts.append("\n")
        body = "".join(body_parts)
        if getattr(m, "column_count", 1) >= 3:
            body = _wrap_multicols(body, m.column_count)

        return (
            f"\\documentclass[{_class_options(m)}]"
            f"{{{m.documentclass}}}\n"
            f"{packages}\n"
            f"\\begin{{document}}\n"
            f"{frontmatter}"
            f"{body}"
            f"\\end{{document}}\n"
        )

    # Standard article / report / book / etc. — title and author go in
    # the preamble, abstract / keywords flow inline in the body.
    preamble_meta = ""
    if has_metadata:
        preamble_meta += f"\\title{{{title_text or '~'}}}\n"
        preamble_meta += f"\\author{{{author_text or '~'}}}\n"

    parts: list[str] = []
    emitted_maketitle = False
    children = doc.children
    n = len(children)
    i = 0

    if is_beamer:
        while i < n:
            block = children[i]
            if isinstance(block, Title):
                parts.append("\\begin{frame}\n\\titlepage\n\\end{frame}\n")
                emitted_maketitle = True
                i += 1
                if i < n: parts.append("\n")
                continue
            if isinstance(block, (Author, Abstract, Keywords)):
                i += 1
                continue
            if isinstance(block, Frame):
                frame_title = serialize_inlines(block.children)
                i += 1
                content_parts: list[str] = []
                while i < n and not isinstance(children[i], (Frame, Section, Title)):
                    content_parts.append(serialize_block(children[i]))
                    i += 1
                content = "\n".join(p for p in content_parts if p)
                if frame_title:
                    parts.append(f"\\begin{{frame}}{{{frame_title}}}\n{content}\n\\end{{frame}}\n")
                else:
                    parts.append(f"\\begin{{frame}}\n\\titlepage\n\\end{{frame}}\n")
                if i < n: parts.append("\n")
                continue
            rendered = serialize_block(block, has_chapters=has_chapters)
            parts.append(rendered)
            i += 1
            if i < n: parts.append("\n")
    else:
        while i < n:
            block = children[i]
            if isinstance(block, Abstract):
                paras: list[str] = []
                while i < n and isinstance(children[i], Abstract):
                    paras.append(serialize_inlines(children[i].children))
                    i += 1
                joined = "\n\n".join(p for p in paras if p)
                parts.append(f"\\begin{{abstract}}\n{joined}\n\\end{{abstract}}\n")
                if i < n: parts.append("\n")
                continue
            if isinstance(block, Keywords):
                group: list = []
                while i < n and isinstance(children[i], Keywords):
                    group.append(children[i])
                    i += 1
                terms = _split_keyword_inlines(group)
                joined = " \\sep ".join(terms)
                parts.append(f"\\begin{{keyword}}\n{joined}\n\\end{{keyword}}\n")
                if i < n: parts.append("\n")
                continue

            rendered = serialize_block(block, has_chapters=has_chapters)
            if isinstance(block, Title):
                emitted_maketitle = True
            parts.append(rendered)
            i += 1
            if i < n:
                parts.append("\n")

    if has_metadata and not has_title_block and not emitted_maketitle:
        parts.insert(0, "\\maketitle\n")
    body = "".join(parts)
    if getattr(m, "column_count", 1) >= 3:
        body = _wrap_multicols(body, m.column_count)

    return (
        f"\\documentclass[{_class_options(m)}]"
        f"{{{m.documentclass}}}\n"
        f"{packages}\n"
        f"{preamble_meta}"
        f"\\begin{{document}}\n"
        f"{body}"
        f"\\end{{document}}\n"
    )
