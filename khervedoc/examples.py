"""Example documents shown under the Examples menu and used as the
starting document when kherveDOC opens for the first time.

Each factory returns a fully-formed Document so the editor can hand it
straight to set_document(). Keeping the examples here (rather than as
.kdocz files shipped on disk) means they always match the current
model schema — no risk of an example loading with a missing field
after a model bump.
"""
from __future__ import annotations

from .model import (
    Abstract, Author, Citation, CrossRef, DEFAULT_PACKAGES, Document, DocMeta,
    Figure, Footnote, Keywords, Link, List as ListNode, ListItem, MathBlock,
    MathInline, Paragraph, RawLatex, Section, Table, Text, Title,
)


# ---------------------------------------------------------------- helpers

def _meta(**overrides) -> DocMeta:
    """Build a DocMeta with the kherveDOC defaults and let callers tweak
    a few fields. Avoids each example repeating the same boilerplate."""
    base = DocMeta(
        title="", author="",
        body_font_pt=11,
        line_spacing=1.15,
        paragraph_indent=False,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _p(*runs) -> Paragraph:
    """Compact constructor: _p('hello ', ('world', ['bold']), '.')"""
    children: list = []
    for r in runs:
        if isinstance(r, str):
            children.append(Text(text=r))
        elif isinstance(r, tuple) and len(r) == 2 and isinstance(r[0], str):
            children.append(Text(text=r[0], marks=list(r[1])))
        else:
            children.append(r)
    return Paragraph(children=children)


# ---------------------------------------------------------------- welcome

def welcome() -> Document:
    """Multi-page tour of kherveDOC's main features — what new users see
    when they open the app. Long enough to span a few PDF pages so the
    page-flipping preview is obvious from the first impression."""
    return Document(
        meta=_meta(title="Welcome to kherveDOC", author="The kherveDOC team"),
        children=[
            Title(children=[Text(text="Welcome to kherveDOC")]),
            Author(children=[Text(text="A quick tour of the editor")]),

            Section(level=1, children=[Text(text="What this is")]),
            _p(
                "kherveDOC is a WYSIWYG editor that produces real LaTeX. "
                "Type here like you would in Word; the preview on the right "
                "compiles to PDF every time you stop typing. Underneath, "
                "your document is stored as a structured model — section "
                "headings, paragraphs, math, tables — and the serializer "
                "turns that into clean .tex you can hand to a journal.",
            ),
            _p(
                "Every save also commits to a local Git repository, so you "
                "can browse the full history of a document under the ",
                ("History", ["bold"]), " menu and roll back to any earlier "
                "version. If the folder has a remote, kherveDOC pushes too.",
            ),

            Section(level=1, children=[Text(text="Formatting basics")]),
            _p(
                "Use the toolbar or the ", ("Format", ["bold"]), " menu to "
                "make text ", ("bold", ["bold"]), ", ",
                ("italic", ["italic"]), ", ",
                ("underlined", ["underline"]), ", or ",
                ("monospaced", ["code"]), ". Subscripts (H",
                ("2", ["subscript"]), "O) and superscripts (E = mc",
                ("2", ["superscript"]), ") work the same way.",
            ),
            _p(
                "Choose a paragraph style from the dropdown next to the "
                "font size. ", ("Title", ["bold"]), ", ",
                ("Author", ["bold"]), ", ", ("Abstract", ["bold"]), " and ",
                ("Keywords", ["bold"]), " are first-class paragraph types "
                "that survive a round-trip to LaTeX and back.",
            ),

            Section(level=2, children=[Text(text="Lists")]),
            ListNode(ordered=False, items=[
                ListItem(children=[Text(text="Bullet lists from the toolbar")]),
                ListItem(children=[Text(text="Or numbered lists, which renumber automatically")]),
                ListItem(children=[Text(text="Nested items use Tab / Shift+Tab")]),
            ]),
            ListNode(ordered=True, items=[
                ListItem(children=[Text(text="Pick the data")]),
                ListItem(children=[Text(text="Fit the model")]),
                ListItem(children=[Text(text="Plot, write, commit")]),
            ]),

            Section(level=1, children=[Text(text="Math")]),
            _p(
                "Inline math like ",
                MathInline(latex=r"E = mc^2"),
                " is one keystroke away (Ctrl+M). For displayed equations, "
                "press Ctrl+Shift+M or use the equation builder palette:",
            ),
            MathBlock(
                latex=r"\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}",
                numbered=True, label="eq:gauss",
            ),
            _p(
                "Aligned multi-line equations work too — the importer "
                "recognises ", ("align", ["code"]), ", ",
                ("split", ["code"]), ", ", ("gather", ["code"]),
                " and friends, and the serializer round-trips them "
                "without re-wrapping in equation*:",
            ),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  f(x) &= a x^2 + b x + c \\\\\n"
                    "  f'(x) &= 2 a x + b \\\\\n"
                    "  f''(x) &= 2 a\n"
                    "\\end{align}"
                ),
                numbered=True,
            ),
            _p(
                "Refer back to a numbered equation with a cross-reference: "
                "see ", CrossRef(label="eq:gauss", kind="eqref"), ".",
            ),

            Section(level=1, children=[Text(text="Figures and tables")]),
            _p(
                "Insert > Figure prompts for a path; the image is included "
                "via ", ("\\includegraphics", ["code"]), " and the preview "
                "renders it inline. Missing images don't break the build — "
                "they show up as a labelled placeholder so you can see "
                "exactly which figure path needs fixing.",
            ),
            Table(
                rows=[
                    ["Feature", "Shortcut", "Where"],
                    ["Bold", "Ctrl+B", "Format menu"],
                    ["Inline math", "Ctrl+M", "Insert menu"],
                    ["Math block", "Ctrl+Shift+M", "Insert menu"],
                    ["Symbol palette", "Ctrl+Shift+S", "Insert menu"],
                    ["Open in new window", "Ctrl+Shift+O", "File menu"],
                ],
                caption="A handful of useful shortcuts.",
                label="tab:shortcuts",
                alignment="lll",
            ),

            Section(level=1, children=[Text(text="Citations and links")]),
            _p(
                "Drop a citation with Insert > Citation — keys go in the "
                "usual ", ("\\cite{...}", ["code"]), " form: ",
                Citation(keys=["knuth1984"], style="cite"),
                ". External links use Insert > Hyperlink (Ctrl+K), for "
                "example ",
                Link(url="https://tectonic-typesetting.github.io/",
                     children=[Text(text="the tectonic project")]),
                ". Footnotes",
                Footnote(children=[Text(text="like this one")]),
                " sit beside the text and render at the bottom of the page.",
            ),

            Section(level=1, children=[Text(text="Columns")]),
            _p(
                "The three buttons next to the alignment group on the "
                "toolbar flip the whole document between 1, 2 and 3 "
                "columns. For a multi-column region inside an otherwise "
                "single-column document, use Insert > Multi-column region.",
            ),

            Section(level=1, children=[Text(text="Where to go next")]),
            _p(
                "Open the ", ("Examples", ["bold"]), " menu for a few "
                "starting templates (math-heavy paper, two-column article, "
                "letter, etc.). Use ", ("File > Open in new window", ["bold"]),
                " to keep two documents side by side, or ",
                ("Import > .tex", ["bold"]),
                " to bring an existing LaTeX source into the editor.",
            ),
            _p(
                "Have fun. ",
                ("Press Ctrl+N for a blank document any time.", ["italic"]),
            ),
        ],
    )


# ---------------------------------------------------------------- examples

def blank() -> Document:
    """A bare-bones single-paragraph document — what File > New also opens."""
    return Document(
        meta=_meta(),
        children=[
            Title(children=[Text(text="Untitled")]),
            Author(children=[Text(text="")]),
            Paragraph(children=[Text(text="Start writing here.")]),
        ],
    )


def article() -> Document:
    """Single-column journal article skeleton: title, author, abstract,
    keywords, intro / methods / results / conclusion sections."""
    return Document(
        meta=_meta(title="An example article", author="A. Author"),
        children=[
            Title(children=[Text(text="An example article")]),
            Author(children=[Text(text="A. Author, B. Coauthor")]),
            Abstract(children=[
                Text(text="This is the abstract. Write 150-250 words "
                          "summarising the contribution, the method, the "
                          "result, and why the reader should care.")]),
            Keywords(children=[Text(text="example · template · article")]),
            Section(level=1, children=[Text(text="Introduction")]),
            _p("Set up the problem and the prior work."),
            Section(level=1, children=[Text(text="Methods")]),
            _p("Describe what you did, in enough detail to reproduce."),
            Section(level=1, children=[Text(text="Results")]),
            _p("Show the numbers / figures / tables that the method produced."),
            Section(level=1, children=[Text(text="Discussion")]),
            _p("Interpret. Compare with prior work. Acknowledge limitations."),
            Section(level=1, children=[Text(text="Conclusion")]),
            _p("Short take-home, plus what comes next."),
        ],
    )


def two_column_article() -> Document:
    """Two-column article — the layout most physics / chemistry journals
    want for the camera-ready version."""
    doc = article()
    doc.meta.title = "A two-column article"
    doc.meta.column_count = 2
    doc.children[0] = Title(children=[Text(text="A two-column article")])
    return doc


def three_column_document() -> Document:
    """Three-column document — wraps the body in multicols{3}."""
    doc = article()
    doc.meta.title = "A three-column document"
    doc.meta.column_count = 3
    doc.children[0] = Title(children=[Text(text="A three-column document")])
    return doc


def math_heavy() -> Document:
    """Example with several display equations and an aligned derivation —
    useful for sanity-checking the math round-trip."""
    return Document(
        meta=_meta(title="Quadratic forms"),
        children=[
            Title(children=[Text(text="Quadratic forms — a worked example")]),
            Section(level=1, children=[Text(text="Definition")]),
            _p(
                "A quadratic function ",
                MathInline(latex="f"),
                " is a polynomial of degree at most two:",
            ),
            MathBlock(latex="f(x) = a x^2 + b x + c, \\qquad a \\neq 0.",
                      numbered=True, label="eq:quad"),
            Section(level=1, children=[Text(text="Completing the square")]),
            _p("From ", CrossRef(label="eq:quad", kind="eqref"),
               " we have:"),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  f(x) &= a\\left(x^2 + \\tfrac{b}{a} x\\right) + c \\\\\n"
                    "       &= a\\left(x + \\tfrac{b}{2a}\\right)^2 "
                    "+ c - \\tfrac{b^2}{4a}.\n"
                    "\\end{align}"
                ),
                numbered=True,
            ),
            Section(level=1, children=[Text(text="Discriminant")]),
            _p("The number of real roots is determined by the discriminant ",
               MathInline(latex="\\Delta = b^2 - 4ac"), ":"),
            ListNode(ordered=False, items=[
                ListItem(children=[Text(text="Δ > 0: two distinct real roots")]),
                ListItem(children=[Text(text="Δ = 0: one repeated real root")]),
                ListItem(children=[Text(text="Δ < 0: two complex conjugate roots")]),
            ]),
        ],
    )


def letter() -> Document:
    """Short letter — useful when you just need a one-page formal note.
    Uses the article class with adjusted margins; the LaTeX `letter`
    class itself is supported via Document settings if needed."""
    return Document(
        meta=_meta(
            title="", author="",
            margin_left_cm=3.0, margin_right_cm=3.0,
            margin_top_cm=3.0, margin_bottom_cm=3.0,
            paragraph_indent=False,
        ),
        children=[
            Paragraph(children=[Text(text="Your name")], alignment="right"),
            Paragraph(children=[Text(text="Street address")], alignment="right"),
            Paragraph(children=[Text(text="City, postcode")], alignment="right"),
            Paragraph(children=[Text(text="")]),
            Paragraph(children=[Text(text="Recipient")]),
            Paragraph(children=[Text(text="Their address")]),
            Paragraph(children=[Text(text="")]),
            Paragraph(children=[Text(text="2026-05-17", marks=["italic"])],
                      alignment="right"),
            Paragraph(children=[Text(text="")]),
            _p(("Dear …,", ["bold"])),
            _p(
                "Body of the letter goes here. Keep it short, get to the "
                "point in the first paragraph, and use one paragraph per "
                "idea.",
            ),
            _p("Yours sincerely,"),
            Paragraph(children=[Text(text="")]),
            _p("Your name"),
        ],
    )


# Order = display order in the Examples menu. The labels here are what
# the user sees; the factories above produce the actual documents.
EXAMPLES: list[tuple[str, callable]] = [
    ("&Welcome tour",         welcome),
    ("&Blank document",       blank),
    ("Single-column &article", article),
    ("&Two-column article",   two_column_article),
    ("Three-&column document", three_column_document),
    ("&Math-heavy document",  math_heavy),
    ("&Letter",               letter),
]
