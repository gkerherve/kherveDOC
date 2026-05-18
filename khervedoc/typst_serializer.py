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
        return f"${_latex_math_to_typst(node.latex)}$"
    if isinstance(node, Link):
        body = serialize_inlines(node.children)
        if body:
            return f"#link(\"{node.url}\")[{body}]"
        return f"#link(\"{node.url}\")"
    if isinstance(node, Footnote):
        return f"#footnote[{serialize_inlines(node.children)}]"
    if isinstance(node, Citation):
        # Typst @-citations require a loaded #bibliography(); render as
        # bracketed text so compilation never fails on a missing .bib.
        joined = ", ".join(node.keys)
        return f"\\[{joined}\\]"
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
        converted = _latex_math_to_typst(stripped)
        lab = _maybe_label(node.label)
        if node.numbered:
            return f"#math.equation(block: true, numbering: \"(1)\")[\n$ {converted} $\n]{lab}\n"
        return f"$ {converted} ${lab}\n"

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


# ---------------------------------------------------------------------------
# LaTeX → Typst math translation
# ---------------------------------------------------------------------------
# Covers common LaTeX math commands. Not exhaustive — exotic packages
# (e.g. tikz-cd, mhchem \ch{}) will pass through as-is and cause Typst
# errors, but the vast majority of everyday math renders correctly.

# Commands that take one braced argument: \cmd{arg} → cmd(arg)
_LATEX_ONE_ARG = {
    "frac": "frac",  "tfrac": "frac",  "dfrac": "frac",
    "sqrt": "sqrt",
    "mathbf": "bold", "boldsymbol": "bold", "bm": "bold",
    "mathrm": "upright", "textrm": "upright", "text": "upright",
    "mathit": "italic",
    "mathbb": "bb", "mathcal": "cal", "mathscr": "cal",
    "mathfrak": "frak",
    "hat": "hat", "widehat": "hat",
    "tilde": "tilde", "widetilde": "tilde",
    "bar": "overline", "overline": "overline",
    "underline": "underline",
    "dot": "dot", "ddot": "dot.double",
    "vec": "arrow",
    "acute": "acute", "grave": "grave",
    "breve": "breve", "check": "caron",
    "operatorname": "op",
    "cancel": "cancel",
}

# Commands whose argument is literal text, not math variables.
_LATEX_TEXT_CMDS = {"text", "textrm", "mathrm", "operatorname"}

# Commands that take two braced arguments: \cmd{a}{b} → cmd(a, b)
_LATEX_TWO_ARG = {
    "frac": "frac", "tfrac": "frac", "dfrac": "frac",
    "binom": "binom",
    "overset": "attach",
}

# Simple symbol replacements: \cmd → typst
_LATEX_SYMBOLS: dict[str, str] = {}
# Greek letters (lowercase)
for _g in ("alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta",
           "theta", "iota", "kappa", "lambda", "mu", "nu", "xi",
           "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi",
           "omega", "varepsilon", "vartheta", "varpi", "varrho",
           "varsigma", "varphi"):
    _LATEX_SYMBOLS[_g] = _g
# Greek letters (uppercase)
for _g in ("Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma",
           "Upsilon", "Phi", "Psi", "Omega"):
    _LATEX_SYMBOLS[_g] = _g
# Operators and relations
_LATEX_SYMBOLS.update({
    "cdot": "dot",  "cdots": "dots.h",  "ldots": "dots",
    "vdots": "dots.v",  "ddots": "dots.down",
    "times": "times",  "div": "div",
    "pm": "plus.minus",  "mp": "minus.plus",
    "neq": "eq.not",  "ne": "eq.not",
    "leq": "lt.eq",  "le": "lt.eq",
    "geq": "gt.eq",  "ge": "gt.eq",
    "ll": "lt.double",  "gg": "gt.double",
    "approx": "approx",  "sim": "tilde",
    "simeq": "tilde.eq",  "cong": "tilde.equiv",
    "equiv": "equiv",  "propto": "prop",
    "subset": "subset",  "supset": "supset",
    "subseteq": "subset.eq",  "supseteq": "supset.eq",
    "in": "in",  "notin": "in.not",  "ni": "in.rev",
    "cup": "union",  "cap": "sect",
    "setminus": "without",  "emptyset": "nothing",
    "forall": "forall",  "exists": "exists",
    "neg": "not",  "land": "and",  "lor": "or",
    "infty": "infinity",
    "partial": "diff",  "nabla": "nabla",
    "to": "arrow.r",  "rightarrow": "arrow.r",
    "leftarrow": "arrow.l",  "leftrightarrow": "arrow.l.r",
    "Rightarrow": "arrow.r.double",
    "Leftarrow": "arrow.l.double",
    "Leftrightarrow": "arrow.l.r.double",
    "mapsto": "arrow.r.bar",
    "iff": "arrow.l.r.double",
    "implies": "arrow.r.double",
    "sum": "sum",  "prod": "prod",
    "int": "integral",  "iint": "integral.double",
    "iiint": "integral.triple",  "oint": "integral.cont",
    "lim": "lim",  "limsup": "limsup",  "liminf": "liminf",
    "min": "min",  "max": "max",
    "sup": "sup",  "inf": "inf",
    "sin": "sin",  "cos": "cos",  "tan": "tan",
    "sec": "sec",  "csc": "csc",  "cot": "cot",
    "arcsin": "arcsin",  "arccos": "arccos",  "arctan": "arctan",
    "sinh": "sinh",  "cosh": "cosh",  "tanh": "tanh",
    "log": "log",  "ln": "ln",  "exp": "exp",
    "det": "det",  "dim": "dim",  "ker": "ker",
    "hom": "hom",  "deg": "deg",  "arg": "arg",
    "gcd": "gcd",
    "quad": "quad",  "qquad": "quad quad",
    ",": "thin",  ";": "med",  "!": "negthin",
    "hspace": "",  "vspace": "",
    "ast": "ast",  "star": "star",
    "dagger": "dagger",  "ddagger": "dagger.double",
    "ell": "ell",  "hbar": "planck.reduce",
    "Re": "Re",  "Im": "Im",
    "prime": "prime",
    "angle": "angle",
    "perp": "perp",  "parallel": "parallel",
    "circ": "compose",
    "otimes": "times.circle",  "oplus": "plus.circle",
    "top": "top",  "bot": "bot",
    "langle": "angle.l",  "rangle": "angle.r",
    "lceil": "ceil.l",  "rceil": "ceil.r",
    "lfloor": "floor.l",  "rfloor": "floor.r",
})

# \left and \right delimiter mapping
_DELIM_MAP = {
    "(": "(", ")": ")",
    "[": "[", "]": "]",
    "\\{": "{", "\\}": "}",
    "|": "|", "\\|": "||",
    ".": "",  # \left. or \right. = invisible delimiter
    "\\langle": "angle.l", "\\rangle": "angle.r",
    "\\lceil": "ceil.l", "\\rceil": "ceil.r",
    "\\lfloor": "floor.l", "\\rfloor": "floor.r",
}


def _eat_brace_arg(s: str, pos: int) -> tuple[str, int]:
    """Extract a braced argument starting at pos (which should be '{').
    Returns (content, new_pos_after_closing_brace)."""
    if pos >= len(s) or s[pos] != '{':
        return "", pos
    depth = 1
    start = pos + 1
    i = start
    while i < len(s) and depth > 0:
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
        i += 1
    return s[start:i - 1], i


def _latex_math_to_typst(latex: str) -> str:
    """Best-effort translation of LaTeX math markup to Typst math markup.

    Handles: Greek letters, \\frac, \\sqrt, \\mathbf and friends,
    \\left/\\right delimiters, \\\\, &, common symbols and operators.
    Unrecognised \\commands pass through (Typst will error on them but
    the user sees what needs manual fixing).
    """
    out: list[str] = []

    def _emit(s: str) -> None:
        """Append *s* to *out*, inserting a space when two letter-runs
        would merge into a multi-letter Typst identifier.  In LaTeX math
        each letter is a separate variable; Typst treats consecutive
        letters as one identifier (``SE`` → unknown variable)."""
        if s and out and s[0].isalpha() and out[-1][-1:].isalpha():
            out.append(" ")
        out.append(s)

    i = 0
    n = len(latex)
    while i < n:
        ch = latex[i]

        # Newline in align: \\ → \
        if ch == '\\' and i + 1 < n and latex[i + 1] == '\\':
            _emit(" \\")
            i += 2
            continue

        # Backslash command
        if ch == '\\':
            # Read the command name
            j = i + 1
            if j < n and not latex[j].isalpha():
                # Single-char commands: \, \; \! \{ \} \| etc.
                cmd_char = latex[j]
                if cmd_char in _LATEX_SYMBOLS:
                    _emit(_LATEX_SYMBOLS[cmd_char])
                elif cmd_char == '{':
                    _emit("{")
                elif cmd_char == '}':
                    _emit("}")
                elif cmd_char == '|':
                    _emit("||")
                elif cmd_char == ' ':
                    _emit(" ")
                else:
                    _emit(cmd_char)
                i = j + 1
                continue
            # Multi-char command
            while j < n and latex[j].isalpha():
                j += 1
            cmd = latex[i + 1:j]
            i = j

            # \left / \right — drop the command, keep the delimiter
            if cmd == "left" or cmd == "right":
                # Read the delimiter that follows
                if i < n:
                    if latex[i] == '\\':
                        # e.g. \left\{ or \left\langle
                        k = i + 1
                        while k < n and latex[k].isalpha():
                            k += 1
                        delim_key = latex[i:k]
                        if delim_key == '\\':
                            # \left\{ or \left\}
                            if k < n and latex[k] in '{}|':
                                delim_key = '\\' + latex[k]
                                k += 1
                        mapped = _DELIM_MAP.get(delim_key, delim_key.lstrip('\\'))
                        _emit(mapped)
                        i = k
                    else:
                        delim_key = latex[i]
                        mapped = _DELIM_MAP.get(delim_key, delim_key)
                        _emit(mapped)
                        i += 1
                continue

            # Two-argument commands (must check before one-arg)
            if cmd in _LATEX_TWO_ARG and i < n and latex[i] == '{':
                typst_fn = _LATEX_TWO_ARG[cmd]
                arg1, i = _eat_brace_arg(latex, i)
                arg2, i = _eat_brace_arg(latex, i)
                arg1 = _latex_math_to_typst(arg1)
                arg2 = _latex_math_to_typst(arg2)
                _emit(f"{typst_fn}({arg1}, {arg2})")
                continue

            # \sqrt[n]{x} → root(n, x)
            if cmd == "sqrt" and i < n and latex[i] == '[':
                end_bracket = latex.index(']', i)
                root_n = latex[i + 1:end_bracket]
                i = end_bracket + 1
                arg, i = _eat_brace_arg(latex, i)
                arg = _latex_math_to_typst(arg)
                root_n = _latex_math_to_typst(root_n)
                _emit(f"root({root_n}, {arg})")
                continue

            # One-argument commands
            if cmd in _LATEX_ONE_ARG and i < n and latex[i] == '{':
                typst_fn = _LATEX_ONE_ARG[cmd]
                arg, i = _eat_brace_arg(latex, i)
                # Text-like commands: quote the argument so Typst
                # renders it as literal text, not as math variables.
                if cmd in _LATEX_TEXT_CMDS:
                    _emit(f'{typst_fn}("{arg}")')
                else:
                    arg = _latex_math_to_typst(arg)
                    _emit(f"{typst_fn}({arg})")
                continue

            # Simple symbol replacement
            if cmd in _LATEX_SYMBOLS:
                repl = _LATEX_SYMBOLS[cmd]
                if repl:
                    _emit(repl)
                else:
                    pass  # drop empty replacements (\hspace etc.)
                continue

            # Unknown command — pass through without backslash
            # (many LaTeX command names happen to be valid Typst identifiers)
            _emit(cmd)
            continue

        # & alignment marker — Typst uses & too
        if ch == '&':
            _emit("&")
            i += 1
            continue

        # Everything else passes through
        _emit(ch)
        i += 1

    return "".join(out)


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
