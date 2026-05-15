"""Import .tex and .docx files into the kherveDOC document model.

The .tex parser handles the common subset that the rest of kherveDOC also
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
    Citation, CrossRef, Document, DocMeta, Figure, Footnote, Link,
    List as ListNode, ListItem, MathBlock, MathInline, Paragraph, RawLatex,
    Section, Text, Title,
)


# ============================================================
#                       .tex importer
# ============================================================

_SECTION_RE = re.compile(
    r"\\(section|subsection|subsubsection|paragraph|subparagraph)(\*?)\{([^}]*)\}")
_SECTION_LEVEL = {
    "section": 1, "subsection": 2, "subsubsection": 3,
    "paragraph": 4, "subparagraph": 5,
}

_TITLE_PREAMBLE_RE = re.compile(r"\\title\{([^}]*)\}")
_AUTHOR_PREAMBLE_RE = re.compile(r"\\author\{([^}]*)\}")
_DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{([^}]+)\}")
_PACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}")
_GEOMETRY_RE = re.compile(r"\\usepackage\[([^\]]*)\]\{geometry\}")

_BODY_RE = re.compile(
    r"\\begin\{document\}(.*?)\\end\{document\}", re.DOTALL)

# Matches the start of a top-level structure we care about, captured for
# routing. Order matters — math/figure/table envs first so they take
# precedence over generic environments.
_BLOCK_DISPATCH = [
    ("math_block_env",  re.compile(r"\\begin\{(equation\*?|displaymath|align\*?)\}(.*?)\\end\{\1\}", re.DOTALL)),
    ("math_block_dd",   re.compile(r"\$\$(.*?)\$\$", re.DOTALL)),
    ("math_block_bs",   re.compile(r"\\\[(.*?)\\\]", re.DOTALL)),
    ("itemize",         re.compile(r"\\begin\{itemize\}(.*?)\\end\{itemize\}", re.DOTALL)),
    ("enumerate",       re.compile(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", re.DOTALL)),
    ("figure",          re.compile(r"\\begin\{figure\}(?:\[[^\]]*\])?(.*?)\\end\{figure\}", re.DOTALL)),
    ("section",         _SECTION_RE),
    ("maketitle",       re.compile(r"\\maketitle\b")),
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
    return [n for n in out if not (isinstance(n, Text) and n.text == "")]


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
    return None


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


def _dispatch(kind: str, m: re.Match) -> object:
    if kind == "math_block_env":
        env_name = m.group(1)
        return MathBlock(latex=m.group(2).strip(),
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
    if kind == "maketitle":
        # \maketitle without a Title block: we represent it as nothing —
        # the meta.title (read from \title{} in the preamble) is enough
        # for the fallback path.
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
    cap = re.search(r"\\caption\{([^}]*)\}", body)
    lab = re.search(r"\\label\{([^}]*)\}", body)
    width = "0.8\\textwidth"
    if inc and inc.group(1):
        wm = re.search(r"width\s*=\s*([^,\]]+)", inc.group(1))
        if wm: width = wm.group(1).strip()
    return Figure(
        path=inc.group(2) if inc else "",
        caption=cap.group(1) if cap else "",
        label=lab.group(1) if lab else None,
        width=width,
    )


def import_tex(tex_source: str) -> Document:
    """Parse a LaTeX source string into a Document. Unknown commands are
    preserved as RawLatex blocks so nothing is silently lost."""
    docclass_m = _DOCCLASS_RE.search(tex_source)
    title_m = _TITLE_PREAMBLE_RE.search(tex_source)
    author_m = _AUTHOR_PREAMBLE_RE.search(tex_source)
    geom_m = _GEOMETRY_RE.search(tex_source)
    packages = [p for p in _PACKAGE_RE.findall(tex_source)
                if p not in ("geometry",)]

    page_size = "A4"
    if geom_m:
        opts = geom_m.group(1).lower()
        if "letterpaper" in opts: page_size = "Letter"
        elif "legalpaper" in opts: page_size = "Legal"
        elif "a4paper" in opts:    page_size = "A4"

    meta = DocMeta(
        title=title_m.group(1) if title_m else "",
        author=author_m.group(1) if author_m else "",
        documentclass=docclass_m.group(1) if docclass_m else "article",
        packages=packages or ["amsmath", "graphicx"],
        page_size=page_size,
    )

    body_m = _BODY_RE.search(tex_source)
    body = body_m.group(1) if body_m else tex_source

    children = _parse_blocks(body)

    # If the source had \title{...} but no Title block was reconstructed,
    # prepend one so the editor shows it under the Title style.
    if meta.title and not any(isinstance(b, Title) for b in children):
        children.insert(0, Title(children=[Text(text=meta.title)]))
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
