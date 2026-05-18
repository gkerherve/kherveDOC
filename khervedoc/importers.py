"""Import .tex and .docx files into the KherveTeX document model.

The .tex parser handles the common subset that the rest of KherveTeX also
emits (sections, lists, math, links, citations, cross-refs, figures, plus
the formatting marks). Anything it doesn't recognise is preserved as
RawLatex so the document round-trips without data loss.

The .docx importer uses python-docx and extracts embedded images into a
sibling folder so they end up as Figure nodes pointing to real files.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .model import (
    Abstract, Author, Citation, CrossRef, DEFAULT_PACKAGES, Document, DocMeta,
    Figure, Footnote, Frame, InlineRaw, Keywords, Link, List as ListNode,
    ListItem, MathBlock, MathInline, Paragraph, RawLatex, Section, Table,
    Text, Title,
)


# ============================================================
#                       .tex importer
# ============================================================

_SECTION_RE = re.compile(
    r"\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)"
    r"(\*?)\{([^}]*)\}")


_FRONTMATTER_BLOCK_RE = re.compile(
    r"\\begin\{frontmatter\}(.*?)\\end\{frontmatter\}", re.DOTALL)


def _strip_balanced_command(src: str, command: str) -> str:
    r"""Remove every occurrence of `\command[opt]{arg}` from `src`, handling
    balanced braces inside the argument so a nested macro doesn't terminate
    the match early."""
    pattern = re.compile(r"\\" + re.escape(command) + r"\b")
    out: list[str] = []
    pos = 0
    while True:
        m = pattern.search(src, pos)
        if not m:
            out.append(src[pos:])
            return "".join(out)
        out.append(src[pos:m.start()])
        p = m.end()
        # Skip optional brackets.
        while p < len(src) and src[p] == "[":
            depth = 1; j = p + 1
            while j < len(src) and depth > 0:
                if src[j] == "[": depth += 1
                elif src[j] == "]": depth -= 1
                j += 1
            p = j
        # Skip balanced { ... } argument if present.
        if p < len(src) and src[p] == "{":
            _, p = _consume_braced(src, p)
        pos = p


def _extract_preamble_extras(src: str) -> str:
    r"""Capture everything between \documentclass and \begin{document}
    that the model doesn't already represent.

    Removed (already modelled):
      - \documentclass[opts]{class}
      - \usepackage[opts]{name}
      - \title{...}, \author{...}, \journal{...}
      - line comments

    Kept (so they survive the round-trip and the PDF retains its
    styling): \lstset, \definecolor, \hypersetup, \newcommand,
    \renewcommand, \setlength, \theoremstyle, \newtheorem,
    \DeclareMathOperator, any other customisation the user wrote
    before \begin{document}.
    """
    doc_m = re.search(r"\\documentclass\b", src)
    body_m = re.search(r"\\begin\{document\}", src)
    if not doc_m or not body_m:
        return ""
    preamble = src[doc_m.start():body_m.start()]
    # Drop comments first so they don't interfere with the strip patterns.
    preamble = _strip_tex_comments(preamble)
    # Strip the patterns we already represent in the model.
    preamble = re.sub(
        r"\\documentclass(?:\[[^\]]*\])?\{[^}]+\}", "", preamble)
    preamble = re.sub(
        r"\\usepackage(?:\[[^\]]*\])?\{[^}]+\}", "", preamble)
    preamble = _strip_balanced_command(preamble, "title")
    preamble = _strip_balanced_command(preamble, "author")
    preamble = _strip_balanced_command(preamble, "journal")
    # Strip \Kstroke definitions — the serializer always emits its own.
    preamble = re.sub(
        r"\\(?:provide|renew|new)command\{?\\Kstroke\}?.*", "", preamble)
    # Collapse runs of blank lines.
    preamble = re.sub(r"\n\s*\n+", "\n", preamble)
    return preamble.strip()


def _extract_frontmatter_extras(src: str) -> str:
    r"""Return whatever lives inside \begin{frontmatter} that the model
    doesn't already represent (so it can be re-emitted verbatim for
    Elsevier-style document classes).

    Strips:
      - the body \title{...}                (model carries this)
      - \begin{abstract}...\end{abstract}   (Abstract blocks)
      - \begin{keyword}...\end{keyword}     (Keywords blocks)
    Keeps:
      - The full \author[opts]{...\corref{...}} expression
      - \ead, \cortext, \affiliation, \fntext, anything else
    """
    fm = _FRONTMATTER_BLOCK_RE.search(src)
    if not fm:
        return ""
    body = fm.group(1)
    body = _strip_balanced_command(body, "title")
    body = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}",
                  "", body, flags=re.DOTALL)
    body = re.sub(r"\\begin\{keyword(?:s)?\}.*?\\end\{keyword(?:s)?\}",
                  "", body, flags=re.DOTALL)
    # Collapse runs of blank lines that the strip leaves behind.
    body = re.sub(r"\n\s*\n+", "\n", body)
    return body.strip()


def _strip_tex_comments(src: str) -> str:
    """Drop LaTeX comments: `%` through end-of-line, except for `\\%`."""
    return re.sub(r"(?<!\\)%[^\n]*", "", src)


def _extract_braced(src: str, command: str) -> str | None:
    """Find `\\command[opts]?{...}` in src and return the balanced argument.

    Replaces the previous regex `\\\\title\\{([^}]*)\\}` which couldn't see
    past the first `}` and so truncated author lines containing nested
    macros (Elsevier's `\\author[ic]{Name\\corref{cor1}}` was a casualty).
    """
    pattern = re.compile(r"\\" + re.escape(command) + r"\b")
    m = pattern.search(src)
    if not m:
        return None
    pos = m.end()
    # Skip optional bracket arguments.
    while pos < len(src) and src[pos] == '[':
        depth = 1; j = pos + 1
        while j < len(src) and depth > 0:
            if src[j] == '[': depth += 1
            elif src[j] == ']': depth -= 1
            j += 1
        pos = j
    if pos >= len(src) or src[pos] != '{':
        return None
    content, _ = _consume_braced(src, pos)
    return content
_SECTION_LEVEL = {
    "chapter": 0,
    "section": 1, "subsection": 2, "subsubsection": 3,
    "paragraph": 4, "subparagraph": 5,
}

_TITLE_PREAMBLE_RE = re.compile(r"\\title\{([^}]*)\}")
_AUTHOR_PREAMBLE_RE = re.compile(r"\\author\{([^}]*)\}")
_DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}")
# Pulls the bracketed options out separately so we can read e.g.
# `twocolumn`, `10pt`, `a4paper` into the model — the bare _DOCCLASS_RE
# only captures the class name. Without this, every LaTeX-tab edit
# round-trips with column_count reset to 1 and body_font_pt reset to
# the DocMeta default, so the user's twocolumn / font choice vanishes.
_DOCCLASS_OPTS_RE = re.compile(r"\\documentclass\[([^\]]*)\]\{[^}]+\}")
_PACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}")
_GEOMETRY_RE = re.compile(r"\\usepackage\[([^\]]*)\]\{geometry\}")

_BODY_RE = re.compile(
    r"\\begin\{document\}(.*?)\\end\{document\}", re.DOTALL)

# Math environments we recognise as a single MathBlock. The names in the
# group are matched against the closing \end{...} via the backreference.
_MATH_ENVS = (
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "eqnarray", "eqnarray*",
    "displaymath", "split",
)
_MATH_ENV_RE = re.compile(
    r"\\begin\{(" + "|".join(re.escape(e) for e in _MATH_ENVS) + r")\}"
    r"(.*?)\\end\{\1\}", re.DOTALL)

# Matches the start of a top-level structure we care about, captured for
# routing. Order matters — math/figure/table envs first so they take
# precedence over generic environments.
_BLOCK_DISPATCH = [
    # Math envs win first.
    ("math_block_env",  _MATH_ENV_RE),
    ("math_block_dd",   re.compile(r"\$\$(.*?)\$\$", re.DOTALL)),
    ("math_block_bs",   re.compile(r"\\\[(.*?)\\\]", re.DOTALL)),
    # Lists
    ("itemize",         re.compile(r"\\begin\{itemize\}(.*?)\\end\{itemize\}", re.DOTALL)),
    ("enumerate",       re.compile(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", re.DOTALL)),
    # Floats and tables
    ("figure",          re.compile(r"\\begin\{figure\*?\}(?:\[[^\]]*\])?(.*?)\\end\{figure\*?\}", re.DOTALL)),
    ("table",           re.compile(r"\\begin\{table\*?\}(?:\[[^\]]*\])?(.*?)\\end\{table\*?\}", re.DOTALL)),
    ("standalone_tabular", re.compile(r"\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}", re.DOTALL)),
    # Verbatim-style code blocks: preserved as RawLatex so the source survives.
    ("verbatim",        re.compile(r"\\begin\{verbatim\}(.*?)\\end\{verbatim\}", re.DOTALL)),
    ("lstlisting",      re.compile(r"\\begin\{lstlisting\}(?:\[[^\]]*\])?(.*?)\\end\{lstlisting\}", re.DOTALL)),
    # Elsevier-style metadata blocks.
    ("abstract",        re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.DOTALL)),
    ("keyword",         re.compile(r"\\begin\{keyword(?:s)?\}(.*?)\\end\{keyword(?:s)?\}", re.DOTALL)),
    # Bibliography preserved verbatim so the references round-trip intact.
    ("bibliography",    re.compile(r"\\begin\{thebibliography\}\{[^}]*\}(.*?)\\end\{thebibliography\}", re.DOTALL)),
    # Alignment envs — emitted by our own serializer for left/center/right
    # paragraphs, so the round-trip path needs to recognise them or it
    # would wrap them in RawLatex via the unknown-env fallback.
    ("flushleft",       re.compile(r"\\begin\{flushleft\}(.*?)\\end\{flushleft\}", re.DOTALL)),
    ("flushright",      re.compile(r"\\begin\{flushright\}(.*?)\\end\{flushright\}", re.DOTALL)),
    ("center",          re.compile(r"\\begin\{center\}(.*?)\\end\{center\}", re.DOTALL)),
    # Beamer frames.
    ("frame",           re.compile(r"\\begin\{frame\}(?:\{([^}]*)\})?(.*?)\\end\{frame\}", re.DOTALL)),
    # Sections / titles.
    ("section",         _SECTION_RE),
    ("maketitle",       re.compile(r"\\maketitle\b")),
    # Last-resort: any other \begin{...}...\end{...} we don't understand
    # gets wrapped in a RawLatex block instead of leaking its body as
    # plain text. Must remain LAST so the specific handlers above win.
    # `@` is part of internal LaTeX names (e.g. \begin{@twocolumnfalse}
    # used by twocolumn[...] to hold a wide title). Accept it in the
    # env name so the round-trip preserves these blocks verbatim.
    ("unknown_env",     re.compile(r"\\begin\{([A-Za-z@]+\*?)\}(?:\[[^\]]*\])?(?:\{[^}]*\})?(.*?)\\end\{\1\}", re.DOTALL)),
]


def _unescape_text(s: str) -> str:
    """Reverse the serializer's escape_text on plain runs."""
    return (s
            .replace(r"\textbackslash{}", "\\")
            .replace(r"\textasciitilde{}", "~")
            .replace(r"\textasciicircum{}", "^")
            .replace(r"\{", "{").replace(r"\}", "}")
            .replace(r"\&", "&").replace(r"\%", "%")
            .replace(r"\$", "$").replace(r"\#", "#")
            .replace(r"\_", "_"))


def _parse_inlines(s: str) -> list:
    """Tokenise inline LaTeX into Text/MathInline/Link/Footnote/Citation/CrossRef.

    Walks the string left-to-right consuming one of: a recognised macro, an
    inline math span, or a plain text run up to the next macro or math span.
    """
    out: list = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "$":
            j = s.find("$", i + 1)
            if j < 0: j = n
            out.append(MathInline(latex=s[i + 1:j]))
            i = j + 1
            continue
        if ch == "\\":
            m = _match_macro(s, i)
            if m is not None:
                node, end = m
                # Mark macros that wrap multiple children flatten into a
                # list here. Extend the inline stream so the downstream
                # serializer never sees a list-as-inline-node.
                if isinstance(node, list):
                    out.extend(node)
                else:
                    out.append(node)
                i = end
                continue
        # Plain text run up to the next $ or recognised macro.
        nxt_math = s.find("$", i)
        nxt_bs = s.find("\\", i)
        candidates = [c for c in (nxt_math, nxt_bs) if c >= 0]
        end = min(candidates) if candidates else n
        if end == i:
            # Unrecognised macro — treat as a one-char advance to avoid loops.
            out.append(Text(text=_unescape_text(s[i:i + 1])))
            i += 1
        else:
            out.append(Text(text=_unescape_text(s[i:end])))
            i = end
    # Drop empty text fragments left over from unknown-macro consumption.
    out = [n for n in out if not (isinstance(n, Text) and n.text == "")]
    # Merge adjacent text runs with the same marks so a sequence like
    # `\texttt{extract\_all}` produces one `\texttt{extract\_all}` on
    # re-serialisation, not five back-to-back `\texttt{}` groups.
    merged: list = []
    for n in out:
        if (isinstance(n, Text) and merged and isinstance(merged[-1], Text)
                and sorted(merged[-1].marks) == sorted(n.marks)):
            merged[-1] = Text(text=merged[-1].text + n.text,
                              marks=list(n.marks))
        else:
            merged.append(n)
    return merged


# Macros that wrap a single brace argument and translate to a Text mark.
_MARK_MACROS = {
    "textbf": "bold", "textit": "italic", "emph": "italic",
    "underline": "underline", "texttt": "code", "textsc": "smallcaps",
    "textsubscript": "subscript", "textsuperscript": "superscript",
    "sout": "strikethrough",
}


_ESCAPED_SPECIAL = {"%", "&", "$", "#", "_", "{", "}"}


def _match_macro(s: str, i: int) -> tuple[object, int] | None:
    """Try to consume a recognised macro at position i. Returns (node, end)
    where end is the index past the macro, or None if not recognised."""
    # Escaped specials (\%, \&, \$, \#, \_, \{, \}) — emit as literal text.
    if i + 1 < len(s) and s[i + 1] in _ESCAPED_SPECIAL:
        return Text(text=s[i + 1]), i + 2
    m = re.match(r"\\([A-Za-z@]+)\*?", s[i:])
    if not m:
        return None
    name = m.group(1)
    after = i + m.end()
    # \\
    if name == "\\":
        return Text(text="\n"), after
    if name in _MARK_MACROS:
        arg, end = _consume_braced(s, after)
        if arg is None:
            return None
        children = _parse_inlines(arg)
        # Apply this mark on top of any Text children.
        mark = _MARK_MACROS[name]
        for c in children:
            if isinstance(c, Text):
                if mark not in c.marks:
                    c.marks.append(mark)
        return _flatten_single(children), end
    if name == "href":
        url, end = _consume_braced(s, after)
        if url is None: return None
        text, end2 = _consume_braced(s, end)
        if text is None: return None
        return Link(url=url, children=_parse_inlines(text)), end2
    if name == "footnote":
        arg, end = _consume_braced(s, after)
        if arg is None: return None
        return Footnote(children=_parse_inlines(arg)), end
    if name in ("cite", "citep", "citet"):
        arg, end = _consume_braced(s, after)
        if arg is None: return None
        return Citation(keys=[k.strip() for k in arg.split(",") if k.strip()],
                        style=name), end
    if name in ("ref", "eqref", "pageref"):
        arg, end = _consume_braced(s, after)
        if arg is None: return None
        return CrossRef(label=arg, kind=name), end
    if name == "label":
        # Strip — section/figure handlers attach labels themselves.
        _, end = _consume_braced(s, after)
        return Text(text=""), (end if end > after else after)
    if name == "url":
        arg, end = _consume_braced(s, after)
        if arg is None: return None
        return Link(url=arg, children=[Text(text=arg)]), end
    if name == "sep":
        # Elsevier keyword separator — render as a middle dot.
        return Text(text=" · "), after
    if name == "verb":
        # \verb<delim>...<delim> — inline verbatim, render as code mark.
        if after >= len(s): return None
        delim = s[after]
        close = s.find(delim, after + 1)
        if close < 0: return None
        return Text(text=s[after + 1:close], marks=["code"]), close + 1

    # Unknown command — consume the macro plus any [...] options and
    # {...} arguments so the outer loop makes progress, and preserve
    # the original source as an InlineRaw node. This is what keeps
    # user-defined commands like \Kstroke surviving a .tex import
    # instead of being silently dropped.
    pos = after
    while pos < len(s) and s[pos] == "[":
        depth = 1; j = pos + 1
        while j < len(s) and depth > 0:
            if s[j] == "[": depth += 1
            elif s[j] == "]": depth -= 1
            j += 1
        pos = j
    while pos < len(s) and s[pos] == "{":
        _, new_pos = _consume_braced(s, pos)
        if new_pos == pos:
            break  # unbalanced brace — stop to avoid infinite loop
        pos = new_pos
    return InlineRaw(latex=s[i:pos]), pos


def _consume_braced(s: str, i: int) -> tuple[str | None, int]:
    """Read a balanced {...} starting at s[i]. Returns (content, end_index)."""
    if i >= len(s) or s[i] != "{":
        return None, i
    depth = 0
    j = i
    while j < len(s):
        if s[j] == "{": depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return None, i


def _flatten_single(nodes: list):
    """Inline-macro helper: when a mark macro wraps a single child it's
    cleaner to surface that child directly rather than a one-element list.
    Returns a single node or, if there are multiple, a synthetic Text with
    the merged content kept as-is (the caller wraps it back into a list).

    For multi-child results we just return the first; the rest are added
    inline by the surrounding parser through the normal loop. Simplifies
    the common case where the macro contains a plain string.
    """
    if not nodes:
        return Text(text="")
    return nodes[0] if len(nodes) == 1 else nodes


_BRACKET_ARG_MACROS = ("twocolumn", "onecolumn")


def _scan_bracket_arg_macro(body: str, start: int) -> tuple[int, int] | None:
    r"""Find the next occurrence at or after `start` of any
    \twocolumn[...] / \onecolumn[...] (etc.) and return
    (match_start, match_end) covering both the macro and its
    bracketed body, with depth-tracked '[' / ']' balancing.

    These macros sit at block level and contain free-form LaTeX
    (\begin{@twocolumnfalse}\maketitle\tableofcontents...). Without
    treating the whole macro+arg as one opaque RawLatex block, the
    regex-based block parser dives into the bracket content and
    breaks the structure (\maketitle gets pulled out, the closing
    \end{@twocolumnfalse} ends up dangling, etc.)."""
    best: tuple[int, int] | None = None
    for name in _BRACKET_ARG_MACROS:
        pat = re.compile(r"\\" + re.escape(name) + r"(?![A-Za-z])\s*\[")
        m = pat.search(body, start)
        if not m:
            continue
        # Walk forward from the opening '[' to the matching ']'.
        j = m.end()  # one past the opening '['
        depth = 1
        n = len(body)
        while j < n and depth > 0:
            if body[j] == "[":
                depth += 1
            elif body[j] == "]":
                depth -= 1
            j += 1
        if depth != 0:
            # Unbalanced — bail out, don't pretend to consume.
            continue
        if best is None or m.start() < best[0]:
            best = (m.start(), j)
    return best


def _parse_blocks(body: str) -> list:
    """Walk the document body and produce a list of Block nodes."""
    blocks: list = []
    i = 0
    n = len(body)
    while i < n:
        # Find the earliest start of any recognised block.
        best_kind = None
        best_match = None
        best_start = n
        # Bracket-argument block-level macros (\twocolumn[...]) win
        # first so the dispatch regexes don't dive into their bodies.
        ba = _scan_bracket_arg_macro(body, i)
        if ba is not None and ba[0] < best_start:
            ba_start, ba_end = ba
            best_kind = "bracket_arg_macro"
            best_match = _StubMatch(ba_start, ba_end, body[ba_start:ba_end])
            best_start = ba_start
        for kind, regex in _BLOCK_DISPATCH:
            m = regex.search(body, i)
            if m and m.start() < best_start:
                best_kind = kind
                best_match = m
                best_start = m.start()
        # Anything before that is paragraph text.
        if best_start > i:
            chunk = body[i:best_start]
            for para in _split_paragraphs(chunk):
                children = _parse_inlines(para)
                if children:
                    blocks.append(Paragraph(children=children))
        if best_match is None:
            break
        node = _dispatch(best_kind, best_match)
        if isinstance(node, list):
            blocks.extend(node)
        elif node is not None:
            blocks.append(node)
        i = best_match.end()
    return blocks


def _split_paragraphs(chunk: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", chunk) if p.strip()]


class _StubMatch:
    """Minimal stand-in for re.Match so the manually-scanned bracket-arg
    macros can flow through the same dispatch pipeline as regex hits."""
    def __init__(self, start: int, end: int, text: str):
        self._start = start
        self._end = end
        self._text = text
    def start(self) -> int: return self._start
    def end(self) -> int: return self._end
    def group(self, n: int = 0) -> str:
        if n != 0:
            raise IndexError("_StubMatch only exposes group 0")
        return self._text


def _dispatch(kind: str, m) -> object:
    if kind == "bracket_arg_macro":
        # \twocolumn[ ... ]: preserved verbatim. The captured text
        # already includes the macro name and the balanced brackets.
        return RawLatex(text=m.group(0))
    if kind == "math_block_env":
        env_name = m.group(1)
        body = m.group(2).strip()
        # `align`, `gather`, `multline`, `eqnarray`, `split` etc. are still
        # legal LaTeX math; preserve them verbatim inside the MathBlock
        # so re-serialization keeps the same environment instead of
        # downgrading to a plain equation. Numbered status follows the *
        # convention.
        body_for_model = body
        if env_name not in ("equation", "equation*"):
            body_for_model = (f"\\begin{{{env_name}}}\n{body}"
                              f"\n\\end{{{env_name}}}")
        return MathBlock(latex=body_for_model,
                         numbered=not env_name.endswith("*"))
    if kind == "math_block_dd":
        return MathBlock(latex=m.group(1).strip(), numbered=False)
    if kind == "math_block_bs":
        return MathBlock(latex=m.group(1).strip(), numbered=False)
    if kind == "section":
        cmd = m.group(1); star = m.group(2); body = m.group(3)
        level = _SECTION_LEVEL.get(cmd, 1)
        return Section(level=level, numbered=(star == ""),
                       children=_parse_inlines(body))
    if kind == "itemize":
        return _parse_list(m.group(1), ordered=False)
    if kind == "enumerate":
        return _parse_list(m.group(1), ordered=True)
    if kind == "figure":
        return _parse_figure(m.group(1))
    if kind == "table":
        return _parse_table_env(m.group(1))
    if kind == "standalone_tabular":
        return _parse_tabular(m.group(1), m.group(2))
    if kind == "verbatim":
        return RawLatex(text=f"\\begin{{verbatim}}{m.group(1)}\\end{{verbatim}}")
    if kind == "lstlisting":
        # Preserve the full matched env (including any [caption=...]).
        return RawLatex(text=m.group(0))
    if kind == "abstract":
        # Split the abstract body into paragraphs (blank-line separated)
        # and emit one Abstract block per paragraph. Consecutive Abstract
        # blocks are merged back into a single env on re-serialisation.
        out: list = []
        for para in _split_paragraphs(m.group(1)):
            out.append(Abstract(children=_parse_inlines(para)))
        return out
    if kind == "keyword":
        # \sep separates terms in the source. Render them in the editor
        # as a single Keywords block whose children are the terms joined
        # by a visible ' · ' separator — the previous per-term layout
        # produced one italic paragraph per keyword, which the user
        # rightly disliked. The serializer splits on the same visible
        # separator to reconstruct the \sep-separated form.
        body = m.group(1)
        parts = [p.strip() for p in re.split(r"\\sep\b\s*", body) if p.strip()]
        if not parts:
            return []
        inlines: list = []
        for i, part in enumerate(parts):
            if i > 0:
                inlines.append(Text(text=" · "))
            inlines.extend(_parse_inlines(part))
        return [Keywords(children=inlines)]
    if kind == "bibliography":
        return RawLatex(text=m.group(0))
    if kind in ("flushleft", "flushright", "center"):
        # Treat the env body as paragraphs that all share the alignment
        # the env enforces. Parse the inside recursively in case it
        # contains lists, math, etc.
        align_name = {"flushleft": "left", "flushright": "right",
                      "center": "center"}[kind]
        sub_blocks = _parse_blocks(m.group(1))
        for sub in sub_blocks:
            if isinstance(sub, Paragraph):
                sub.alignment = align_name
        return sub_blocks
    if kind == "unknown_env":
        env_name = m.group(1)
        # Some envs are pure wrappers we want to strip entirely
        # (frontmatter brackets the real content).
        if env_name == "frontmatter":
            return _parse_blocks(m.group(2))
        return RawLatex(text=m.group(0))
    if kind == "frame":
        title = (m.group(1) or "").strip()
        body = (m.group(2) or "").strip()
        out: list = []
        if "\\titlepage" in body:
            out.append(Title(children=[Text(text=title)] if title else []))
        else:
            out.append(Frame(children=_parse_inlines(title) if title else []))
            out.extend(_parse_blocks(body))
        return out
    if kind == "maketitle":
        return None
    return None


def _parse_list(body: str, ordered: bool) -> ListNode:
    items: list[ListItem] = []
    raw_items = re.split(r"\\item\b", body)
    for it in raw_items[1:]:   # discard preamble before first \item
        text = it.strip()
        if text:
            items.append(ListItem(children=_parse_inlines(text)))
    return ListNode(ordered=ordered, items=items)


def _parse_figure(body: str) -> Figure:
    inc = re.search(r"\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}", body)
    # Caption may contain other macros; use the balanced consumer to grab
    # its full content even when it includes nested braces.
    cap_match = re.search(r"\\caption\{", body)
    caption = ""
    if cap_match:
        text, _ = _consume_braced(body, cap_match.end() - 1)
        caption = (text or "").strip()
    lab = re.search(r"\\label\{([^}]*)\}", body)
    width = "0.8\\textwidth"
    if inc and inc.group(1):
        wm = re.search(r"width\s*=\s*([^,\]]+)", inc.group(1))
        if wm: width = wm.group(1).strip()
    return Figure(
        path=inc.group(2) if inc else "",
        caption=caption,
        label=lab.group(1) if lab else None,
        width=width,
    )


def _parse_table_env(body: str) -> object:
    """Parse a \\begin{table}...\\end{table} float. If it wraps a tabular,
    return a Table; otherwise fall back to a RawLatex block so nothing
    is lost."""
    tab = re.search(r"\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}",
                    body, re.DOTALL)
    cap_match = re.search(r"\\caption\{", body)
    caption = ""
    if cap_match:
        text, _ = _consume_braced(body, cap_match.end() - 1)
        caption = (text or "").strip()
    lab = re.search(r"\\label\{([^}]*)\}", body)
    label = lab.group(1) if lab else None
    if not tab:
        return RawLatex(text=f"\\begin{{table}}{body}\\end{{table}}")
    table = _parse_tabular(tab.group(1), tab.group(2))
    table.caption = caption
    table.label = label
    return table


def _parse_tabular(align_spec: str, body: str) -> Table:
    """Turn a tabular body into a Table model node. Cells are stored as
    plain text strings (matching the model); embedded LaTeX inside a cell
    is preserved verbatim because the existing serializer escapes only
    plain-text cell content."""
    # Drop common line-rule commands so they don't survive into cell text.
    body = re.sub(r"\\hline\b", "", body)
    body = re.sub(r"\\toprule|\\midrule|\\bottomrule|\\cline\{[^}]*\}", "", body)
    # Strip extra LaTeX comments and whitespace.
    rows_raw = re.split(r"\\\\\s*", body)
    rows: list[list[str]] = []
    for raw in rows_raw:
        line = raw.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split("&")]
        rows.append(cells)
    alignment = "".join(c for c in align_spec if c in "lcr|p")
    # If alignment includes column-separator pipes we strip them; the
    # serializer doesn't model vertical rules yet.
    alignment = alignment.replace("|", "").replace("p", "l")
    return Table(rows=rows, alignment=alignment or "")


def import_tex(tex_source: str) -> Document:
    """Parse a LaTeX source string into a Document. Unknown commands and
    environments are preserved as RawLatex blocks so nothing is silently
    lost from the source."""
    # Strip line comments first — Elsevier templates use `%%` ruled
    # banners between sections, and without this every banner would
    # appear as a stray paragraph in the imported document.
    tex_source = _strip_tex_comments(tex_source)

    docclass_m = _DOCCLASS_RE.search(tex_source)
    # Use balanced-brace extraction for title/author so Elsevier-style
    # `\author[ic]{Name\corref{cor1}}` arguments aren't truncated at the
    # first inner `}`.
    title_text = _extract_braced(tex_source, "title")
    author_text = _extract_braced(tex_source, "author")
    geom_m = _GEOMETRY_RE.search(tex_source)
    packages = [p for p in _PACKAGE_RE.findall(tex_source)
                if p not in ("geometry", "setspace")]

    page_size = "A4"
    if geom_m:
        opts = geom_m.group(1).lower()
        if "letterpaper" in opts: page_size = "Letter"
        elif "legalpaper" in opts: page_size = "Legal"
        elif "a4paper" in opts:    page_size = "A4"

    # Strip nested macros from the author line — \corref{} etc. clutter
    # the visible author name. The cleaned author can still live in
    # meta.author; the full original is in the source if needed.
    if author_text:
        author_clean = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?",
                              "", author_text).strip()
    else:
        author_clean = ""
    doc_class = docclass_m.group(1) if docclass_m else "article"

    # Parse the \documentclass[...] options so we don't drop column
    # count / body font size on every LaTeX-tab edit. Without this,
    # editing the LaTeX view round-trips `[10pt,twocolumn]` into
    # `[12pt]{article}` because the model defaults take over.
    class_opts_m = _DOCCLASS_OPTS_RE.search(tex_source)
    doc_class_opts = [o.strip() for o in class_opts_m.group(1).split(",")] \
        if class_opts_m else []
    body_font_pt = 12
    for opt in doc_class_opts:
        if opt in ("10pt", "11pt", "12pt"):
            body_font_pt = int(opt[:-2])
            break
    column_count = 1
    if "twocolumn" in doc_class_opts:
        column_count = 2
    # `onecolumn` is the default; leave column_count at 1.

    # For Elsevier classes we keep \author[opts]{...\corref{...}},
    # \ead, \cortext, \affiliation etc. as raw LaTeX in frontmatter_extras
    # so the round-trip reproduces the journal's title-block layout
    # (author superscript, affiliation line, "Corresponding author"
    # footnote) instead of dropping these as unknown macros.
    if doc_class.lower().startswith("elsarticle"):
        frontmatter_extras = _extract_frontmatter_extras(tex_source)
    else:
        frontmatter_extras = ""
    # Preserve every other preamble customisation (\lstset for listings
    # styling, \definecolor, \hypersetup, custom \newcommand etc.) so
    # the PDF re-compiled from KherveTeX retains the framed line-numbered
    # syntax-coloured code blocks the user authored upstream.
    preamble_extras = _extract_preamble_extras(tex_source)
    meta = DocMeta(
        title=(title_text or "").strip(),
        author=author_clean,
        documentclass=doc_class,
        packages=packages or ["amsmath", "graphicx"],
        page_size=page_size,
        body_font_pt=body_font_pt,
        column_count=column_count,
        frontmatter_extras=frontmatter_extras,
        preamble_extras=preamble_extras,
    )

    body_m = _BODY_RE.search(tex_source)
    body = body_m.group(1) if body_m else tex_source

    children = _parse_blocks(body)

    # If the source had \title{...} but no Title block was reconstructed,
    # prepend one. Parse the title text as inlines so any nested macros
    # (\textbf, \emph, \texttt etc.) decode into proper marks instead of
    # surviving as literal LaTeX in the Text fragment.
    if title_text and not any(isinstance(b, Title) for b in children):
        title_inlines = _parse_inlines(title_text) or [Text(text=title_text)]
        # Title style is bold by definition — strip the bold mark from any
        # inline run so the next serialization round-trip doesn't double-
        # wrap with \textbf and leave literal characters behind.
        for c in title_inlines:
            if isinstance(c, Text) and "bold" in c.marks:
                c.marks = [m for m in c.marks if m != "bold"]
        children.insert(0, Title(children=title_inlines))
        meta.title = ""

    return Document(meta=meta, children=children)


# ============================================================
#                       .docx importer
# ============================================================

def docx_available() -> bool:
    try:
        import docx  # noqa: F401
        return True
    except Exception:
        return False


_DOCX_STYLE_TO_LEVEL = {
    "title": -1,
    "heading 1": 1, "heading 2": 2, "heading 3": 3,
    "heading 4": 4, "heading 5": 5, "heading 6": 5,
}


def import_docx(docx_path: Path, image_dir: Path) -> Document:
    """Import a .docx file. Embedded images are saved to image_dir and
    referenced from Figure blocks. image_dir is created if missing.

    Falls back to RawLatex for unsupported content (complex tables, shapes).
    """
    import docx as _docx
    image_dir.mkdir(parents=True, exist_ok=True)

    src = _docx.Document(str(docx_path))
    children: list = []
    title: str = ""
    author: str = src.core_properties.author or ""

    image_counter = 0
    # Use the docx package's part API to find image relationships.
    image_rels: dict[str, str] = {}
    for rel in src.part.rels.values():
        if "image" in rel.reltype:
            image_rels[rel.rId] = rel.target_ref

    for para in src.paragraphs:
        style_name = (para.style.name or "").lower().strip()
        text_runs = list(_runs_to_inlines(para))
        # Detect embedded images in this paragraph by inspecting the XML.
        para_images = _images_in_paragraph(para, src, image_dir, image_counter)
        image_counter += len(para_images)

        if para_images:
            for path in para_images:
                children.append(Figure(path=str(path).replace("\\", "/"),
                                       caption="", label=None))
            # If the paragraph only contained images and whitespace, skip
            # adding an empty text block beside them.
            if not any(isinstance(r, (Text,)) and r.text.strip() for r in text_runs):
                continue

        if style_name == "title":
            title = "".join(r.text for r in text_runs if isinstance(r, Text))
            children.append(Title(children=text_runs))
        elif style_name in _DOCX_STYLE_TO_LEVEL:
            lvl = _DOCX_STYLE_TO_LEVEL[style_name]
            if lvl >= 1:
                children.append(Section(level=lvl, children=text_runs))
            else:
                children.append(Title(children=text_runs))
        else:
            if text_runs:
                children.append(Paragraph(children=text_runs))

    meta = DocMeta(title=title, author=author)
    return Document(meta=meta, children=children)


def _runs_to_inlines(para) -> list:
    out: list = []
    for run in para.runs:
        text = run.text
        if not text:
            continue
        marks: list = []
        if run.bold: marks.append("bold")
        if run.italic: marks.append("italic")
        if run.underline: marks.append("underline")
        if getattr(run.font, "strike", False): marks.append("strikethrough")
        out.append(Text(text=text, marks=marks))
    return out


def _images_in_paragraph(para, src_doc, image_dir: Path, start_idx: int) -> list[Path]:
    """Save any inline images referenced from this paragraph into image_dir.
    Returns the list of saved file paths in document order."""
    paths: list[Path] = []
    # The python-docx public API doesn't expose images per-paragraph directly,
    # so we look at the underlying XML for "blip" elements referencing parts.
    from docx.oxml.ns import qn
    blips = para._element.findall(".//" + qn("a:blip"))
    for blip in blips:
        rid = blip.get(qn("r:embed"))
        if not rid:
            continue
        part = src_doc.part.related_parts.get(rid)
        if part is None:
            continue
        ext = Path(part.partname).suffix or ".png"
        out_path = image_dir / f"image_{start_idx + len(paths):03d}{ext}"
        out_path.write_bytes(part.blob)
        paths.append(out_path)
    return paths


# ============================================================
#                      .md (Markdown) importer
# ============================================================

_MD_YAML_FENCE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def _parse_md_yaml_header(text: str) -> tuple[dict, str]:
    """Extract a YAML front-matter block and return (metadata_dict, rest).
    Uses a minimal key: value parser — no PyYAML dependency needed."""
    m = _MD_YAML_FENCE.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip("'\"")
    return meta, text[m.end():]


_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?$", re.MULTILINE)
_MD_DISPLAY_MATH = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)
_MD_INLINE_MATH = re.compile(r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*")
_MD_BOLD_UNDER = re.compile(r"__(.+?)__")
_MD_ITALIC_STAR = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MD_ITALIC_UNDER = re.compile(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
_MD_CODE_SPAN = re.compile(r"`([^`]+)`")
_MD_CITE = re.compile(r"\[(@[\w:.-]+(?:;\s*@[\w:.-]+)*)\]")
_MD_CODE_FENCE = re.compile(
    r"^```(\w*)\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
_MD_BLOCKQUOTE = re.compile(r"^>\s?(.*)$", re.MULTILINE)


def _md_parse_inlines(text: str) -> list:
    """Convert Markdown inline markup to model Inline nodes."""
    parts: list = []
    pos = 0
    patterns = [
        ("display_math", _MD_DISPLAY_MATH),
        ("cite", _MD_CITE),
        ("inline_math", _MD_INLINE_MATH),
        ("image", _MD_IMAGE),
        ("link", _MD_LINK),
        ("code", _MD_CODE_SPAN),
        ("bold_s", _MD_BOLD_STAR),
        ("bold_u", _MD_BOLD_UNDER),
        ("italic_s", _MD_ITALIC_STAR),
        ("italic_u", _MD_ITALIC_UNDER),
    ]
    while pos < len(text):
        best_m = None
        best_kind = ""
        for kind, pat in patterns:
            m = pat.search(text, pos)
            if m and (best_m is None or m.start() < best_m.start()):
                best_m = m
                best_kind = kind
        if best_m is None:
            remainder = text[pos:]
            if remainder:
                parts.append(Text(text=remainder))
            break
        if best_m.start() > pos:
            parts.append(Text(text=text[pos:best_m.start()]))
        if best_kind == "display_math":
            parts.append(MathInline(latex=best_m.group(1).strip()))
        elif best_kind == "inline_math":
            parts.append(MathInline(latex=best_m.group(1).strip()))
        elif best_kind == "cite":
            keys = [k.strip().lstrip("@") for k in best_m.group(1).split(";")]
            parts.append(Citation(keys=keys))
        elif best_kind == "image":
            # Images become separate Figure blocks later; skip inline
            parts.append(Text(text=best_m.group(0)))
        elif best_kind == "link":
            link_text = best_m.group(1)
            link_url = best_m.group(2)
            parts.append(Link(url=link_url,
                              children=[Text(text=link_text)]))
        elif best_kind == "code":
            parts.append(Text(text=best_m.group(1), marks=["code"]))
        elif best_kind in ("bold_s", "bold_u"):
            parts.append(Text(text=best_m.group(1), marks=["bold"]))
        elif best_kind in ("italic_s", "italic_u"):
            parts.append(Text(text=best_m.group(1), marks=["italic"]))
        pos = best_m.end()
    return parts or [Text(text="")]


def import_md(md_source: str, image_dir: Path | None = None) -> Document:
    """Parse a Markdown string into a Document.

    Handles YAML front-matter (title, author, bibliography), ATX headings,
    display/inline math, fenced code blocks, images, links, bold, italic,
    inline code, citations (@key), ordered/unordered lists, and blockquotes.
    """
    yaml_meta, body = _parse_md_yaml_header(md_source)

    title = yaml_meta.get("title", "")
    author = yaml_meta.get("author", yaml_meta.get("authors", ""))
    bib = yaml_meta.get("bibliography", "")

    packages = list(DEFAULT_PACKAGES)
    if bib:
        packages = list(set(packages) | {"natbib"})
    preamble_lines: list[str] = []
    if bib:
        preamble_lines.append(
            f"\\bibliographystyle{{plainnat}}\n\\bibliography{{{bib.replace('.bib', '')}}}")

    children: list = []
    if title:
        children.append(Title(children=[Text(text=title)]))
    if author and isinstance(author, str):
        children.append(Author(children=[Text(text=author)]))

    has_code_blocks = False

    # Process body line by line, grouping into blocks.
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code block
        fence_m = re.match(r"^```(\w*)\s*$", line)
        if fence_m:
            code_lines = []
            i += 1
            while i < len(lines) and not re.match(r"^```\s*$", lines[i]):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            has_code_blocks = True
            lang = fence_m.group(1)
            code = "\n".join(code_lines)
            # Derive a caption from the preceding paragraph when it ends
            # with ":" — that's the typical Markdown pattern for introducing
            # a code example.  Otherwise fall back to the language name.
            caption = ""
            if children and isinstance(children[-1], Paragraph):
                prev_text = "".join(
                    n.text for n in children[-1].children
                    if isinstance(n, Text)).strip()
                if prev_text.endswith(":"):
                    caption = prev_text.rstrip(":").strip()
                    # Shorten to the last sentence/clause for cleaner captions
                    for sep in (". ", "; ", "— "):
                        if sep in caption:
                            caption = caption.rsplit(sep, 1)[-1].strip()
            if not caption:
                caption = lang.capitalize() if lang else "Code"
            # Escape special LaTeX chars inside the caption
            caption = caption.replace("_", "\\_")
            opts = [f"caption={{{caption}}}"]
            if lang:
                opts.append(f"language={lang}")
            children.append(RawLatex(
                text=f"\\begin{{lstlisting}}[{', '.join(opts)}]\n"
                     f"{code}\n\\end{{lstlisting}}"))
            continue

        # Display math ($$...$$ spanning lines)
        if line.strip().startswith("$$"):
            math_lines = [line.strip().removeprefix("$$")]
            i += 1
            while i < len(lines):
                if "$$" in lines[i]:
                    math_lines.append(
                        lines[i].strip().removesuffix("$$"))
                    i += 1
                    break
                math_lines.append(lines[i])
                i += 1
            latex = "\n".join(math_lines).strip()
            children.append(MathBlock(latex=latex))
            continue

        # ATX heading
        h_m = _MD_HEADING.match(line)
        if h_m:
            level = len(h_m.group(1))
            heading_text = h_m.group(2).strip()
            inlines = _md_parse_inlines(heading_text)
            children.append(Section(level=min(level, 5),
                                    children=inlines))
            i += 1
            continue

        # Image on its own line
        img_m = _MD_IMAGE.match(line.strip())
        if img_m:
            caption = img_m.group(1)
            img_path = img_m.group(2)
            children.append(Figure(path=img_path, caption=caption,
                                   label=None))
            i += 1
            continue

        # Unordered list
        if re.match(r"^[-*+]\s", line):
            items = []
            while i < len(lines) and re.match(r"^[-*+]\s", lines[i]):
                item_text = re.sub(r"^[-*+]\s+", "", lines[i])
                items.append(ListItem(
                    children=_md_parse_inlines(item_text)))
                i += 1
            children.append(ListNode(ordered=False, items=items))
            continue

        # Ordered list
        if re.match(r"^\d+\.\s", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i]):
                item_text = re.sub(r"^\d+\.\s+", "", lines[i])
                items.append(ListItem(
                    children=_md_parse_inlines(item_text)))
                i += 1
            children.append(ListNode(ordered=True, items=items))
            continue

        # Blockquote — collect consecutive > lines into an italic paragraph
        if line.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_lines.append(
                    re.sub(r"^>\s?", "", lines[i]))
                i += 1
            quote_text = " ".join(quote_lines)
            children.append(Paragraph(
                children=[Text(text=quote_text, marks=["italic"])]))
            continue

        # Blank line — skip
        if not line.strip():
            i += 1
            continue

        # Regular paragraph — collect lines until blank/heading/fence/list
        para_lines = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if (not nxt.strip() or _MD_HEADING.match(nxt)
                    or re.match(r"^```", nxt)
                    or re.match(r"^[-*+]\s", nxt)
                    or re.match(r"^\d+\.\s", nxt)
                    or nxt.startswith(">")
                    or nxt.strip().startswith("$$")):
                break
            para_lines.append(nxt)
            i += 1
        para_text = " ".join(para_lines)
        children.append(Paragraph(children=_md_parse_inlines(para_text)))

    if has_code_blocks:
        packages = list(set(packages) | {"listings", "xcolor"})
        preamble_lines.insert(0, (
            "\\definecolor{codegray}{rgb}{0.5,0.5,0.5}\n"
            "\\definecolor{codegreen}{rgb}{0,0.5,0}\n"
            "\\definecolor{codepurple}{rgb}{0.58,0,0.82}\n"
            "\\definecolor{backcolour}{rgb}{0.97,0.97,0.97}\n"
            "\\lstset{\n"
            "  backgroundcolor=\\color{backcolour},\n"
            "  commentstyle=\\color{codegreen},\n"
            "  keywordstyle=\\color{blue},\n"
            "  stringstyle=\\color{codepurple},\n"
            "  numberstyle=\\tiny\\color{codegray},\n"
            "  basicstyle=\\ttfamily\\small,\n"
            "  breaklines=true,\n"
            "  frame=single,\n"
            "  numbers=left,\n"
            "  numbersep=5pt,\n"
            "  tabsize=4,\n"
            "  captionpos=t,\n"
            "  showstringspaces=false,\n"
            "}"
        ))

    meta = DocMeta(
        title=title,
        author=author if isinstance(author, str) else "",
        documentclass="article",
        packages=packages,
        preamble_extras="\n".join(preamble_lines),
    )

    return Document(meta=meta, children=children)
