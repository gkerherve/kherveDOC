"""Document model -> LaTeX source string.

Pure functions; one serializer per node type. No I/O.
"""
from __future__ import annotations

import re

from .model import (
    Abstract, Author, Block, ChapterEntry, Citation, Comment, CrossRef,
    Document, Figure, Footnote, Frame, Highlight, HIGHLIGHT_COLORS, Inline,
    InlineRaw, Keywords, Link, List as ListNode, ListItem, MathBlock,
    MathInline, Paragraph, Project, RawLatex, Section, Table, Text, Title,
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
    "\u00a0": "~",
}


def escape_text(s: str) -> str:
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in s)


def escape_author(s: str) -> str:
    r"""Format the author metadata for ``\author{...}``.

    The author field accepts LaTeX: ``\thanks{...}`` footnotes, ``\small``
    affiliations, ``\texttt{...}`` and the like pass through untouched so a
    real title block can be built (and so an imported one round-trips). Both
    a literal newline and a typed ``\\`` become a real ``\\`` line break, so
    a name on one line and an affiliation on the next wrap in the PDF. Only
    bare ``& % # $`` — which a user is unlikely to mean as LaTeX and which
    otherwise abort the compile — are escaped, and never a copy already
    written as ``\&``."""
    parts = re.split(r"\s*\\\\\s*|\n", s.strip())
    lines = []
    for p in parts:
        p = p.strip()
        if p:
            lines.append(re.sub(r"(?<!\\)([&%#$])", r"\\\1", p))
    return " \\\\\n".join(lines)


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


def _auto_table_alignment(rows: list[list[str]], cols: int) -> str:
    """Pick column specs that fit on the page. Short tables get bare ``l``
    columns; wider ones get proportional ``p{...\\textwidth}`` columns so
    LaTeX can wrap long cell text instead of overflowing the margins."""
    # Measure the longest cell in each column.
    max_lens = [0] * cols
    for r in rows:
        for j in range(min(len(r), cols)):
            max_lens[j] = max(max_lens[j], len(r[j]))
    total = sum(max_lens) or 1
    # Heuristic: if the total character width is modest, plain l columns
    # will fit a standard page just fine (≈80 chars across).
    if total <= 80:
        return "l" * cols
    # Otherwise distribute \textwidth proportionally.
    usable = 0.95  # leave a small margin for \tabcolsep
    specs: list[str] = []
    for ml in max_lens:
        frac = round(usable * ml / total, 2)
        frac = max(frac, 0.06)  # minimum readable width
        specs.append(f"p{{{frac:.2f}\\textwidth}}")
    return "".join(specs)


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


from .model import class_supports_chapter as _class_supports_chapter


def serialize_block(node: Block, *, has_chapters: bool = False,
                    float_h: bool = True) -> str:
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
        # Caption is stored as raw LaTeX (may contain \textit, $...$,
        # etc.) — emit verbatim, do not re-escape.
        cap = node.caption
        lab = _maybe_label(node.label) if node.label else ""
        placement = "H" if float_h else "htbp"
        return (
            f"\\begin{{figure}}[{placement}]\n"
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
        align = node.alignment.strip()
        if not align:
            align = _auto_table_alignment(node.rows, cols)
        # Pad short rows with empty cells.
        body_rows: list[str] = []
        for i, r in enumerate(node.rows):
            # Table cells are stored as raw LaTeX — emit verbatim.
            cells = list(r) + [""] * (cols - len(r))
            row_str = " & ".join(cells) + r" \\"
            # Add \hline after the first row (header separator).
            if i == 0 and len(node.rows) > 1:
                row_str += " \\hline"
            body_rows.append(row_str)
        body = "\n    ".join(body_rows)
        cap = node.caption
        lab = _maybe_label(node.label) if node.label else ""
        placement = "H" if float_h else "htbp"
        return (
            f"\\begin{{table}}[{placement}]\n"
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
    """Emit the font size as-is — some classes accept non-standard sizes."""
    return f"{pt}pt"


_STANDARD_SERIALIZER_CLASSES = {
    "article", "report", "book", "letter", "memoir", "beamer",
    "scrartcl", "scrreprt", "scrbook",
    "elsarticle",
}


def _class_options(m) -> str:
    """Comma-joined documentclass options: font size, twocolumn, etc.

    For non-standard classes without explicit options, return empty
    string — custom classes set their own layout internally.
    For standard classes, reconstruct from model fields and append
    any extra preserved options (a4paper, draft, etc.).
    """
    raw = getattr(m, "class_options", "")
    if (m.documentclass or "").lower() not in _STANDARD_SERIALIZER_CLASSES:
        return raw
    opts = [_body_font_pt_class_option(m.body_font_pt)]
    if getattr(m, "column_count", 1) == 2:
        opts.append("twocolumn")
    # Append preserved extras (a4paper, draft, landscape, etc.)
    if raw:
        extras = [o.strip() for o in raw.split(",") if o.strip()]
        opts.extend(extras)
    return ",".join(opts)


def _documentclass_line(m) -> str:
    opts = _class_options(m)
    if opts:
        return f"\\documentclass[{opts}]{{{m.documentclass}}}"
    return f"\\documentclass{{{m.documentclass}}}"


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
    has_chapters = _class_supports_chapter(m.documentclass or "")
    # Non-standard classes carry their own layout — don't inject geometry,
    # setspace, or font packages that may conflict.
    is_journal = (m.documentclass or "").lower() not in _STANDARD_SERIALIZER_CLASSES

    # Margins flow into geometry per-side so users can pick asymmetric layouts.
    # Journal classes (non-standard) often define their own layout that
    # conflicts with geometry — skip it for those.
    if is_journal:
        geometry = ""
    else:
        geometry = (
            f"\\usepackage[{page.geometry_option},"
            f"top={m.margin_top_cm}cm,bottom={m.margin_bottom_cm}cm,"
            f"left={m.margin_left_cm}cm,right={m.margin_right_cm}cm]{{geometry}}"
        )
    font_pkg = "" if is_journal else _FONT_FAMILY_PACKAGES.get(m.body_font_family, "")
    if is_journal:
        spacing_pkg = ""
        spacing_cmd = ""
    else:
        spacing_pkg = "\\usepackage{setspace}"
        spacing_cmd = ""
        if abs(m.line_spacing - 1.0) > 0.01:
            if abs(m.line_spacing - 1.5) < 0.01:
                spacing_cmd = "\\onehalfspacing"
            elif abs(m.line_spacing - 2.0) < 0.01:
                spacing_cmd = "\\doublespacing"
            else:
                spacing_cmd = f"\\setstretch{{{m.line_spacing}}}"
    parindent = "" if (m.paragraph_indent or is_journal) else "\\setlength{\\parindent}{0pt}\n\\setlength{\\parskip}{0.8em}"

    preamble_extras = "\n".join(p for p in (font_pkg, spacing_pkg, spacing_cmd, parindent) if p)
    pkg_list = list(m.packages)
    if "float" not in pkg_list and not is_journal:
        pkg_list.append("float")
    pkg_lines = "\n".join(f"\\usepackage{{{p}}}" for p in pkg_list)
    packages = (geometry + "\n" + pkg_lines).strip() if geometry else pkg_lines
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
    author_parts: list[str] = []
    for block in doc.children:
        if isinstance(block, Title) and inline_title is None:
            inline_title = serialize_inlines(block.children)
            has_title_block = True
        elif isinstance(block, Author):
            part = serialize_inlines(block.children)
            if part:
                author_parts.append(part)
    title_text = inline_title if inline_title is not None else (
        escape_text((doc.meta.title or "").strip()))
    # Join multiple Author blocks with \\ so they wrap in the PDF.
    inline_author = " \\\\\n".join(author_parts) if author_parts else None
    author_text = inline_author if inline_author is not None else (
        escape_author(doc.meta.author or ""))
    # LaTeX's \maketitle puts \@author inside a non-wrapping tabular{c}.
    # A single long author line overflows the margins, so wrap it in a
    # \parbox to reflow. But when the author already sets its own line
    # breaks (name \\ affiliation), \maketitle centres each line for us —
    # wrapping then would swallow the \thanks{} footnote, so leave it be.
    if author_text and "\\\\" not in author_text and len(author_text) > 80:
        author_text = (
            f"\\parbox{{\\textwidth}}{{\\centering {author_text}}}"
        )

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
            body_parts.append(serialize_block(b, has_chapters=has_chapters,
                                               float_h=not is_journal))
            if i < len(body_blocks) - 1:
                body_parts.append("\n")
        body = "".join(body_parts)
        if getattr(m, "column_count", 1) >= 3:
            body = _wrap_multicols(body, m.column_count)

        return (
            f"{_documentclass_line(m)}\n"
            f"{packages}\n"
            f"\\begin{{document}}\n"
            f"{frontmatter}"
            f"{body}"
            f"\\end{{document}}\n"
        )

    # Standard article / report / book / etc. — title and author go in
    # the preamble, abstract / keywords flow inline in the body.
    # For journal classes preamble_extras already carries the full
    # \title{} / \author[]{} blocks — don't emit duplicates.
    # Also check frontmatter_extras which holds body-level author
    # commands extracted from Wiley-style templates.
    extras_src = (m.preamble_extras or "")
    fm_extras = (m.frontmatter_extras or "").strip()
    all_extras = extras_src + "\n" + fm_extras
    preamble_meta = ""
    if has_metadata:
        if not re.search(r"\\title\b", all_extras):
            preamble_meta += f"\\title{{{title_text or '~'}}}\n"
        if author_text and not re.search(r"\\author\b", all_extras):
            preamble_meta += f"\\author{{{author_text}}}\n"

    parts: list[str] = []
    emitted_maketitle = False
    # Wiley-style journal classes: emit body-level frontmatter commands
    # (multi-author, addresses, etc.) at the top of the body, followed
    # by \maketitle.
    if fm_extras and not is_elsarticle:
        parts.append(fm_extras + "\n")
        # Emit abstract/keywords (now model nodes) back before \maketitle.
        for blk in doc.children:
            if isinstance(blk, Abstract):
                parts.append(f"\\abstract{{{serialize_inlines(blk.children)}}}\n")
            elif isinstance(blk, Keywords):
                kw_group = [blk]
                kw_terms = _split_keyword_inlines(kw_group)
                parts.append(f"\\keywords{{{', '.join(kw_terms)}}}\n")
        parts.append("\\maketitle\n")
        emitted_maketitle = True
    children = doc.children
    n = len(children)
    i = 0
    # If a RawLatex block already contains \maketitle (e.g. inside a
    # \twocolumn[...\maketitle...] wrapper), don't emit a separate one.
    raw_has_maketitle = any(
        isinstance(b, RawLatex) and "\\maketitle" in b.text
        for b in children)

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
            # Skip Title/Author/Abstract/Keywords blocks when body
            # frontmatter already carries the full metadata + \maketitle.
            if fm_extras and isinstance(block, (Title, Author, Abstract, Keywords)):
                i += 1
                continue
            # Skip the Title block's \maketitle if a RawLatex block
            # already contains one (e.g. \twocolumn[...\maketitle...]).
            if raw_has_maketitle and isinstance(block, Title):
                emitted_maketitle = True
                i += 1
                continue
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
            rendered = serialize_block(block, has_chapters=has_chapters,
                                       float_h=not is_journal)
            if isinstance(block, Title):
                emitted_maketitle = True
            elif isinstance(block, RawLatex) and "\\maketitle" in block.text:
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
        f"{_documentclass_line(m)}\n"
        f"{packages}\n"
        f"{preamble_meta}"
        f"\\begin{{document}}\n"
        f"{body}"
        f"\\end{{document}}\n"
    )


# ==================== Multi-chapter project ====================


def serialize_chapter_body(doc: Document) -> str:
    """Serialize a chapter document as body-only LaTeX (no preamble, no
    \\begin{document}).  Used for \\include'd chapter files."""
    m = doc.meta
    has_chapters = _class_supports_chapter(m.documentclass or "")
    is_journal = (m.documentclass or "").lower() not in _STANDARD_SERIALIZER_CLASSES
    parts: list[str] = []
    children = doc.children
    n = len(children)
    i = 0
    while i < n:
        block = children[i]
        if isinstance(block, (Title, Author)):
            i += 1
            continue
        if isinstance(block, Abstract):
            paras: list[str] = []
            while i < n and isinstance(children[i], Abstract):
                paras.append(serialize_inlines(children[i].children))
                i += 1
            joined = "\n\n".join(p for p in paras if p)
            parts.append(f"\\begin{{abstract}}\n{joined}\n\\end{{abstract}}\n")
            if i < n:
                parts.append("\n")
            continue
        if isinstance(block, Keywords):
            group: list = []
            while i < n and isinstance(children[i], Keywords):
                group.append(children[i])
                i += 1
            terms = _split_keyword_inlines(group)
            joined = " \\sep ".join(terms)
            parts.append(f"\\begin{{keyword}}\n{joined}\n\\end{{keyword}}\n")
            if i < n:
                parts.append("\n")
            continue
        rendered = serialize_block(block, has_chapters=has_chapters,
                                   float_h=not is_journal)
        parts.append(rendered)
        i += 1
        if i < n:
            parts.append("\n")
    return "".join(parts)


def _chapter_stem(ch: ChapterEntry) -> str:
    """Return the file stem used in \\include{stem} for a chapter."""
    from pathlib import PurePosixPath
    p = ch.path.replace("\\", "/")
    name = PurePosixPath(p).stem
    for ext in (".kdoc", ".ktex"):
        if name.endswith(ext):
            name = name[:-len(ext)]
    return name


def serialize_project_master(proj: Project) -> str:
    """Generate the master .tex for a multi-chapter project.

    All chapters appear in \\include{} calls (so LaTeX keeps numbering
    consistent), but only enabled chapters are listed in \\includeonly{}
    so disabled ones compile as no-ops.
    """
    from . import page_sizes
    m = proj.meta
    page = page_sizes.by_code(m.page_size)
    is_journal = (m.documentclass or "").lower() not in _STANDARD_SERIALIZER_CLASSES

    if is_journal:
        geometry = ""
    else:
        geometry = (
            f"\\usepackage[{page.geometry_option},"
            f"top={m.margin_top_cm}cm,bottom={m.margin_bottom_cm}cm,"
            f"left={m.margin_left_cm}cm,right={m.margin_right_cm}cm]{{geometry}}"
        )
    font_pkg = "" if is_journal else _FONT_FAMILY_PACKAGES.get(m.body_font_family, "")
    if is_journal:
        spacing_pkg = ""
        spacing_cmd = ""
    else:
        spacing_pkg = "\\usepackage{setspace}"
        spacing_cmd = ""
        if abs(m.line_spacing - 1.0) > 0.01:
            if abs(m.line_spacing - 1.5) < 0.01:
                spacing_cmd = "\\onehalfspacing"
            elif abs(m.line_spacing - 2.0) < 0.01:
                spacing_cmd = "\\doublespacing"
            else:
                spacing_cmd = f"\\setstretch{{{m.line_spacing}}}"
    parindent = "" if (m.paragraph_indent or is_journal) else (
        "\\setlength{\\parindent}{0pt}\n\\setlength{\\parskip}{0.8em}")

    preamble_extras = "\n".join(p for p in (font_pkg, spacing_pkg, spacing_cmd, parindent) if p)
    pkg_list = list(m.packages)
    if "float" not in pkg_list and not is_journal:
        pkg_list.append("float")
    pkg_lines = "\n".join(f"\\usepackage{{{p}}}" for p in pkg_list)
    packages = (geometry + "\n" + pkg_lines).strip() if geometry else pkg_lines
    if preamble_extras:
        packages += "\n" + preamble_extras
    if m.preamble_extras and m.preamble_extras.strip():
        packages += "\n" + m.preamble_extras.strip()
    packages += "\n" + _KSTROKE_PROVIDE

    # Title / author in the preamble
    preamble_meta = ""
    if m.title and m.title != "Untitled":
        preamble_meta += f"\\title{{{escape_text(m.title)}}}\n"
    if m.author:
        preamble_meta += f"\\author{{{escape_author(m.author)}}}\n"

    # Bibliography
    bib_lines = ""
    if proj.bibliography:
        bib_path = proj.bibliography.replace("\\", "/")
        if bib_path.endswith(".bib"):
            bib_path = bib_path[:-4]
        style = proj.bib_style or "plain"
        bib_lines = (
            f"\n\\bibliographystyle{{{style}}}\n"
            f"\\bibliography{{{bib_path}}}\n"
        )

    # Disabled chapters are omitted from the body entirely (no \include
    # line), with \setcounter used to keep numbering consistent. This is
    # simpler and more reliable than \includeonly, which still requires
    # every \include to be present and leaves .aux files from prior runs.

    # Body: section-type switches, page-numbering commands, \include per chapter.
    # \frontmatter / \mainmatter / \appendix / \backmatter are standard
    # book-class commands that control chapter numbering and page style.
    #
    # Disabled chapters are excluded via \includeonly, but we still need
    # to keep counters consistent: each disabled chapter advances the
    # chapter counter (and page counter by its last-known page count) so
    # the next enabled chapter prints the right numbers.
    body_parts: list[str] = []
    if preamble_meta:
        body_parts.append("\\maketitle\n")
    prev_numbering = None
    prev_type = None
    running_chapter = 0       # tracks the chapter counter across all entries
    running_page_offset = 0   # pages consumed by preceding disabled chapters
    for ch in proj.chapters:
        cmds: list[str] = []
        ctype = getattr(ch, "chapter_type", "chapter")
        if ctype != prev_type:
            if ctype == "frontmatter":
                cmds.append("\\frontmatter")
            elif ctype == "chapter" and prev_type in ("frontmatter", None):
                cmds.append("\\mainmatter")
                running_chapter = 0
            elif ctype == "appendix":
                cmds.append("\\appendix")
                running_chapter = 0
            elif ctype == "backmatter":
                cmds.append("\\backmatter")
            prev_type = ctype

        # Determine what chapter number this entry occupies.
        ch_num = getattr(ch, "chapter_number", None)
        if ctype == "chapter":
            if ch_num is not None:
                running_chapter = ch_num
            else:
                running_chapter += 1

        if ch.numbering != prev_numbering:
            cmds.append(f"\\pagenumbering{{{ch.numbering}}}")
            prev_numbering = ch.numbering

        if not ch.enabled:
            # Skip the \include but account for the pages and chapter
            # number this entry would have consumed.
            running_page_offset += ch.last_known_pages or 0
            continue

        # Enabled chapter: set counters to compensate for any skipped
        # chapters that came before.
        if ch.start_page is not None:
            cmds.append(f"\\setcounter{{page}}{{{ch.start_page}}}")
        elif running_page_offset > 0:
            cmds.append(f"\\addtocounter{{page}}{{{running_page_offset}}}")
            running_page_offset = 0

        if ctype == "chapter":
            cmds.append(f"\\setcounter{{chapter}}{{{running_chapter - 1}}}")

        if cmds:
            body_parts.append("\n".join(cmds) + "\n")
        stem = _chapter_stem(ch)
        body_parts.append(f"\\include{{{stem}}}\n")

    body = "\n".join(body_parts)

    return (
        f"{_documentclass_line(m)}\n"
        f"{packages}\n"
        f"{preamble_meta}"
        f"\\begin{{document}}\n"
        f"{body}"
        f"{bib_lines}"
        f"\\end{{document}}\n"
    )
