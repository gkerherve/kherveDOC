"""Example documents shown under the Examples menu and used as the
starting document when kherveDOC opens for the first time.

Each factory returns a fully-formed Document so the editor can hand it
straight to set_document(). Keeping the examples here (rather than as
.kdocz files shipped on disk) means they always match the current
model schema — no risk of an example loading with a missing field
after a model bump.

Examples are intentionally long enough to span several PDF pages —
new users see a real document the first time they open the app, not
a stub, and the page-flipping preview is obvious from the first
keystroke.
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


def _items(*labels) -> ListNode:
    return ListNode(ordered=False, items=[
        ListItem(children=[Text(text=s)]) for s in labels])


def _ord_items(*labels) -> ListNode:
    return ListNode(ordered=True, items=[
        ListItem(children=[Text(text=s)]) for s in labels])


# ---------------------------------------------------------------- welcome

def welcome() -> Document:
    """Multi-page tour of kherveDOC's main features — what new users see
    when they open the app."""
    return Document(
        meta=_meta(title="Welcome to kherveDOC", author="The kherveDOC team"),
        children=[
            Title(children=[Text(text="Welcome to kherveDOC")]),
            Author(children=[Text(text="A guided tour of the editor")]),

            # ---- What it is ----
            Section(level=1, children=[Text(text="What kherveDOC is")]),
            _p(
                "kherveDOC is a WYSIWYG editor that produces real LaTeX. "
                "You type the way you would in Word; the preview on the "
                "right compiles to PDF every time you stop typing. "
                "Underneath, the document is stored as a structured model "
                "— section headings, paragraphs, math, tables, figures, "
                "lists — and the serializer turns that into clean .tex "
                "you can hand to a journal, a co-author, or a git diff.",
            ),
            _p(
                "If you have never written LaTeX directly, you will not "
                "need to. If you have, kherveDOC stays out of your way: "
                "you can import an existing .tex file, edit it visually, "
                "and export the result back to LaTeX with the structure "
                "preserved. Anything the editor does not natively "
                "understand is stored verbatim as a raw block so a "
                "round-trip never loses data.",
            ),
            _p(
                "Every save also commits to a local Git repository. "
                "Open ", ("History > Show commit history…", ["bold"]),
                " to browse the whole timeline of a document and roll "
                "back to any earlier version. If the folder has a remote, "
                "kherveDOC will push to it automatically. The commits use "
                "your git config identity, so they are indistinguishable "
                "from commits you make from the command line.",
            ),

            # ---- Formatting ----
            Section(level=1, children=[Text(text="Formatting basics")]),
            _p(
                "Use the toolbar or the ", ("Format", ["bold"]),
                " menu to make text ", ("bold", ["bold"]), ", ",
                ("italic", ["italic"]), ", ",
                ("underlined", ["underline"]), ", ",
                ("struck through", ["strikethrough"]), ", or ",
                ("monospaced", ["code"]), ". Subscripts (H",
                ("2", ["subscript"]), "O) and superscripts (E = mc",
                ("2", ["superscript"]), ") work the same way. ",
                ("Small caps", ["smallcaps"]),
                " is on the format toolbar too.",
            ),
            _p(
                "Each formatting mark survives the LaTeX round-trip. ",
                ("Bold", ["bold"]), " becomes ", ("\\textbf{...}", ["code"]),
                ", italic becomes ", ("\\textit{...}", ["code"]),
                ", code becomes ", ("\\texttt{...}", ["code"]),
                ", and so on. The serializer nests marks in a stable "
                "order so two consecutive edits do not produce different "
                "diffs for the same logical content.",
            ),
            Section(level=2, children=[Text(text="Paragraph styles")]),
            _p(
                "Pick a paragraph style from the dropdown to the right of "
                "the font-size combo. ", ("Title", ["bold"]), ", ",
                ("Author", ["bold"]), ", ", ("Abstract", ["bold"]), " and ",
                ("Keywords", ["bold"]),
                " are first-class paragraph types that survive a "
                "round-trip to LaTeX and back. Headings come in five "
                "levels and each gets its own size in the editor so the "
                "document outline is obvious at a glance.",
            ),
            _p(
                "Alignment lives next to the formatting buttons. Left, "
                "center, right and full justification each emit the "
                "matching LaTeX environment (flushleft, center, "
                "flushright, or the default justified body).",
            ),

            # ---- Lists ----
            Section(level=2, children=[Text(text="Lists")]),
            _p("Bulleted and numbered lists, with nested items via Tab "
               "and Shift-Tab. A few things you can do with them:"),
            _items(
                "Drop a list anywhere from the toolbar or the Insert menu",
                "Mix marks inside list items — bold, italic, inline math, "
                "links and footnotes all work",
                "Nest several levels deep with Tab; bullets switch style "
                "automatically per nesting level",
                "Use a numbered list for a procedure and a bulleted one "
                "for an inventory",
            ),
            _p("A short worked procedure as an ordered list:"),
            _ord_items(
                "Open the file or paste your data",
                "Pick the model and starting parameters",
                "Run the fit",
                "Inspect residuals and adjust",
                "Export the report",
            ),

            # ---- Math ----
            Section(level=1, children=[Text(text="Math")]),
            _p(
                "Inline math like ", MathInline(latex=r"E = mc^2"),
                " is one keystroke away — Ctrl+M opens a small prompt "
                "and the result is rendered inline. For displayed "
                "equations press Ctrl+Shift+M, or use the equation "
                "builder palette under Insert. A famous integral, "
                "numbered and labelled so we can refer back to it:",
            ),
            MathBlock(
                latex=r"\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}",
                numbered=True, label="eq:gauss",
            ),
            _p(
                "Aligned multi-line equations work too. The importer "
                "recognises ", ("align", ["code"]), ", ",
                ("split", ["code"]), ", ", ("gather", ["code"]),
                ", ", ("multline", ["code"]), " and friends; the "
                "serializer round-trips them verbatim, without "
                "re-wrapping in a useless ", ("equation*", ["code"]),
                " env. A small derivation of the quadratic formula:",
            ),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  a x^2 + b x + c &= 0 \\\\\n"
                    "  x^2 + \\tfrac{b}{a} x &= -\\tfrac{c}{a} \\\\\n"
                    "  \\left(x + \\tfrac{b}{2a}\\right)^2 &= "
                    "\\tfrac{b^2 - 4ac}{4a^2} \\\\\n"
                    "  x &= \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\n"
                    "\\end{align}"
                ),
                numbered=True,
            ),
            _p(
                "Refer back to a numbered equation with a cross-reference: "
                "see ", CrossRef(label="eq:gauss", kind="eqref"),
                ". The Insert > Cross-reference dialog lets you pick from "
                "any labelled section, equation, figure or table in the "
                "document.",
            ),
            _p(
                "The Symbol palette (Ctrl+Shift+S) is a clickable grid "
                "of Greek letters, operators, relations, arrows, calculus "
                "symbols and accents. Click any symbol to drop it at the "
                "cursor as inline math. Text-mode macros that would not "
                "work inside ", ("$ ... $", ["code"]),
                " get inserted as raw inline LaTeX instead.",
            ),

            # ---- Figures + tables ----
            Section(level=1, children=[Text(text="Figures and tables")]),
            _p(
                "Insert > Figure asks for a path and a caption. The "
                "image is included via ", ("\\includegraphics", ["code"]),
                " and renders inline in the preview. Relative paths are "
                "resolved against the document's folder, so the same "
                "figure layout works whether you compile from kherveDOC, "
                "from the command line, or from a co-author's machine.",
            ),
            _p(
                "Missing images do not break the build. They render as "
                "a labelled placeholder so you can see exactly which "
                "figure path needs fixing instead of staring at a "
                "tectonic stack trace.",
            ),
            _p("A small reference card of the most useful shortcuts:"),
            Table(
                rows=[
                    ["Action",              "Shortcut",        "Menu"],
                    ["Bold",                "Ctrl+B",          "Format"],
                    ["Italic",              "Ctrl+I",          "Format"],
                    ["Inline math",         "Ctrl+M",          "Insert"],
                    ["Math block",          "Ctrl+Shift+M",    "Insert"],
                    ["Symbol palette",      "Ctrl+Shift+S",    "Insert"],
                    ["Equation builder",    "Ctrl+Shift+E",    "Insert"],
                    ["Hyperlink",           "Ctrl+K",          "Insert"],
                    ["New document",        "Ctrl+N",          "File"],
                    ["New window",          "Ctrl+Shift+N",    "File"],
                    ["Open in new window",  "Ctrl+Shift+O",    "File"],
                    ["Save",                "Ctrl+S",          "File"],
                ],
                caption="A handful of useful shortcuts.",
                label="tab:shortcuts",
                alignment="lll",
            ),

            # ---- Citations + links ----
            Section(level=1, children=[Text(text="Citations and links")]),
            _p(
                "Drop a citation with Insert > Citation — keys go in the "
                "usual ", ("\\cite{...}", ["code"]), " form: ",
                Citation(keys=["knuth1984"], style="cite"),
                ". The dialog supports the three common variants — ",
                ("cite", ["code"]), ", ", ("citep", ["code"]),
                " and ", ("citet", ["code"]),
                " — so you can match whatever style your journal expects.",
            ),
            _p(
                "External links use Insert > Hyperlink (Ctrl+K). For "
                "example, ",
                Link(url="https://tectonic-typesetting.github.io/",
                     children=[Text(text="the tectonic project")]),
                " (which is the LaTeX engine kherveDOC compiles with) "
                "and ",
                Link(url="https://github.com/gkerherve/kherveDOC",
                     children=[Text(text="the kherveDOC repository")]),
                " on GitHub. Footnotes",
                Footnote(children=[Text(text="like this one, which "
                                             "renders at the bottom of "
                                             "the page in the PDF.")]),
                " sit beside the text in the editor and float to the "
                "page foot in the output.",
            ),

            # ---- Columns ----
            Section(level=1, children=[Text(text="Columns")]),
            _p(
                "The three buttons next to the alignment group on the "
                "toolbar flip the whole document between 1, 2 and 3 "
                "columns. Two columns uses LaTeX's standard ",
                ("twocolumn", ["code"]),
                " class option; three columns wraps the body in ",
                ("\\begin{multicols}{3}", ["code"]),
                " because no documentclass natively supports three "
                "columns. The choice is stored in the document and "
                "follows the file across machines.",
            ),
            _p(
                "For a multi-column region inside an otherwise "
                "single-column document, use Insert > Multi-column "
                "region. It drops a ", ("multicols", ["code"]),
                " environment at the cursor with a small placeholder "
                "you can replace with the content that should flow "
                "across the columns.",
            ),

            # ---- Multi-document ----
            Section(level=1, children=[Text(text="Working with several documents")]),
            _p(
                "File > New window (Ctrl+Shift+N) opens a second, "
                "independent kherveDOC window. File > Open in new "
                "window… (Ctrl+Shift+O) opens an existing document "
                "without replacing the one you are reading. Each window "
                "has its own toolbar, its own preview and its own git "
                "state, so you can work on a paper in one window while "
                "consulting an old version of the same paper in another.",
            ),
            _p(
                "The Window menu lists every open document so you can "
                "jump between them without alt-tabbing. The check mark "
                "shows which window is currently focused. Closing the "
                "last window quits the app.",
            ),

            # ---- Import / export ----
            Section(level=1, children=[Text(text="Importing and exporting")]),
            _p(
                "File > Import > .tex pulls in an existing LaTeX file "
                "(and resolves its ", ("\\includegraphics", ["code"]),
                " paths automatically). The importer handles most of "
                "the common subset — sections, paragraphs, lists, "
                "figures, tables, math envs, citations, references, "
                "marks — and anything it does not recognise gets "
                "preserved as a raw block so the round-trip is "
                "lossless.",
            ),
            _p(
                "File > Import > .docx does the same for a Word "
                "document. Embedded images are extracted into a sibling "
                "folder so they end up as proper Figure blocks.",
            ),
            _p(
                "On the way out, File > Export > .tex writes the LaTeX "
                "source and File > Export > .pdf writes the compiled PDF. "
                "Both targets are clean enough to commit straight into "
                "a paper's repository.",
            ),

            # ---- Where to next ----
            Section(level=1, children=[Text(text="Where to go next")]),
            _p(
                "Open the ", ("Examples", ["bold"]),
                " menu for a few starting templates: a math-heavy "
                "report, a two- or three-column article, a one-page "
                "letter, and a generic single-column article skeleton. "
                "Each opens in its own window so this welcome tour "
                "stays put if you want to refer back to it.",
            ),
            _p(
                "Use ", ("File > New", ["bold"]),
                " (Ctrl+N) any time for a blank document, or ",
                ("File > Open recent", ["bold"]),
                " to jump back into something you were working on. "
                "Document-wide preferences — fonts, margins, page size, "
                "line spacing — live under ",
                ("File > Document properties", ["bold"]), ".",
            ),
            _p(
                "Happy writing. ",
                ("— The kherveDOC team", ["italic"]),
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


# ---------------------------------------------------------------- article

def _article_body(title: str, subtitle: str) -> list:
    """Shared body for the single-, two- and three-column article
    examples so they show the same content under different layouts."""
    return [
        Title(children=[Text(text=title)]),
        Author(children=[Text(text="A. Author¹, B. Coauthor¹, C. Reviewer²"),
                         Footnote(children=[Text(text=subtitle)])]),
        Abstract(children=[
            Text(text=
                "We present a worked example of the kherveDOC editor "
                "in a journal-article layout. The document is intended "
                "as a starting point for new users: every block type "
                "the editor supports is exercised at least once so "
                "that copy-pasting from this skeleton into a real "
                "paper Just Works. We summarise the structure, "
                "describe how each section is typically used, and "
                "include enough mathematics, references and tabular "
                "data to demonstrate the preview pipeline end to end.")]),
        Keywords(children=[Text(text="kherveDOC · template · article · example")]),

        Section(level=1, children=[Text(text="Introduction")]),
        _p(
            "Scientific papers tend to share a small set of conventions: "
            "a tight introduction that frames the question, a methods "
            "section detailed enough to reproduce, a results section "
            "with the numerical evidence, a discussion that interprets "
            "those numbers, and a conclusion that places the work in "
            "context. This template walks through each of those "
            "sections with placeholder text so you can see how the "
            "compiled PDF will look before you commit to writing the "
            "real version.",
        ),
        _p(
            "The kherveDOC editor was designed to remove the "
            "friction of formatting from the writing process. When "
            "you are drafting a paper you should be thinking about "
            "claims and evidence, not about whether the right "
            "package is loaded for a particular Greek letter. The "
            "editor takes care of the LaTeX boilerplate; you take "
            "care of the science.",
        ),
        _p(
            "Prior work on WYSIWYG LaTeX editors has typically "
            "fallen into one of two camps. The first attempts to "
            "render LaTeX faithfully in the editor itself, which "
            "tends to be slow and brittle. The second offers a "
            "stripped-down rich-text view that loses information "
            "when round-tripped. kherveDOC takes a third path: keep "
            "a structured model in memory, render it both as live "
            "preview and as LaTeX on demand, and use Git to make "
            "every save a recoverable checkpoint.",
        ),

        Section(level=1, children=[Text(text="Background")]),
        _p(
            "The remainder of this paper is organised as follows. "
            "Section 2 reviews the relevant prior art and positions "
            "our contribution. Section 3 describes the methodology, "
            "including the data sources, the measurement pipeline "
            "and the analysis software. Section 4 presents the "
            "results in tabular and graphical form. Section 5 "
            "discusses the implications and the limitations, and "
            "Section 6 concludes.",
        ),
        _p(
            "Throughout the paper we adopt the notation summarised "
            "in Table ", CrossRef(label="tab:notation", kind="ref"),
            ". Lower-case Roman letters denote scalars, bold "
            "lower-case Roman letters denote vectors, and bold "
            "capital Roman letters denote matrices. Greek letters "
            "are reserved for model parameters.",
        ),
        Table(
            rows=[
                ["Symbol", "Meaning",                   "Units"],
                ["x",      "Independent variable",      "—"],
                ["y",      "Dependent variable",        "—"],
                ["σ",      "Measurement uncertainty",   "(same as y)"],
                ["N",      "Number of observations",    "—"],
                ["μ",      "Population mean",           "(same as y)"],
                ["χ²",     "Goodness-of-fit statistic", "—"],
            ],
            caption="Notation used throughout the paper.",
            label="tab:notation",
            alignment="lll",
        ),

        Section(level=1, children=[Text(text="Methods")]),
        Section(level=2, children=[Text(text="Data acquisition")]),
        _p(
            "Measurements were collected on a custom-built "
            "instrument over the period from January 2025 to March "
            "2026. Each session produced approximately 4 GB of raw "
            "data, which was archived locally and mirrored to a "
            "remote backup at the end of each day. A total of 312 "
            "sessions contributed to the dataset analysed here.",
        ),
        _p(
            "The raw data were filtered to remove samples flagged "
            "by the instrument's on-board quality-control system, "
            "and additionally to exclude any sample whose timestamp "
            "fell within five minutes of a documented instrument "
            "maintenance event. After filtering, ",
            MathInline(latex="N = 1.82 \\times 10^{6}"),
            " samples remained, distributed roughly uniformly across "
            "the observation period.",
        ),
        Section(level=2, children=[Text(text="Analysis pipeline")]),
        _p(
            "The analysis pipeline was implemented in Python 3.12, "
            "using NumPy for numerical work, SciPy for the optimiser "
            "and Matplotlib for the figures. The full source is "
            "available at the project repository — see the link in "
            "the acknowledgements.",
        ),
        _p(
            "The core model is a weighted least-squares fit:",
        ),
        MathBlock(
            latex=(
                "\\chi^2(\\theta) "
                "= \\sum_{i=1}^{N} "
                "\\left(\\frac{y_i - f(x_i; \\theta)}{\\sigma_i}\\right)^2,"
            ),
            numbered=True, label="eq:chi2",
        ),
        _p(
            "where ", MathInline(latex="\\theta"),
            " is the vector of model parameters and ",
            MathInline(latex="f(x; \\theta)"),
            " is the parametric model under consideration. We "
            "minimise ", CrossRef(label="eq:chi2", kind="eqref"),
            " by Levenberg–Marquardt and report parameter "
            "uncertainties from the diagonal of the covariance "
            "matrix at the optimum.",
        ),
        _p(
            "Two model families were considered: a simple Gaussian "
            "and a sum of two Gaussians. The simpler model is "
            "favoured when the improvement in ",
            MathInline(latex="\\chi^2"),
            " does not justify the additional parameters under an "
            "F-test at the 5% significance level.",
        ),

        Section(level=1, children=[Text(text="Results")]),
        _p(
            "Table ", CrossRef(label="tab:results", kind="ref"),
            " summarises the best-fit parameters for each of the "
            "model families. The two-Gaussian model improves the "
            "fit substantially in the high-signal subset of the "
            "data but does not pass the F-test on the full set.",
        ),
        Table(
            rows=[
                ["Model",          "χ²/dof", "p-value", "Δχ² vs single"],
                ["Single Gaussian", "1.04",  "0.31",    "—"],
                ["Double Gaussian", "0.97",  "0.42",    "+38"],
                ["Skewed Gaussian", "1.01",  "0.38",    "+14"],
                ["Voigt",           "0.98",  "0.41",    "+33"],
            ],
            caption="Goodness-of-fit for four candidate models.",
            label="tab:results",
            alignment="lrrr",
        ),
        _p(
            "Figure 1 (placeholder) would show the residuals of the "
            "best model against the independent variable. The "
            "residuals are approximately Gaussian with no obvious "
            "trend, supporting the choice of a least-squares "
            "objective.",
        ),

        Section(level=1, children=[Text(text="Discussion")]),
        _p(
            "The results are consistent with the prior literature ",
            Citation(keys=["doe2024", "smith2025"], style="cite"),
            " and extend it to a larger sample. The principal "
            "novelty here is the inclusion of the maintenance-window "
            "exclusion, which reduces the apparent variance by "
            "roughly 12% without measurably biasing the fit "
            "parameters.",
        ),
        _p(
            "Two limitations are worth flagging. First, the data "
            "were collected on a single instrument; cross-checks "
            "with a second instrument would strengthen the "
            "conclusions. Second, the maintenance-window flagging "
            "relies on operator records, which are known to be "
            "incomplete for the first six months of the dataset.",
        ),

        Section(level=1, children=[Text(text="Conclusion")]),
        _p(
            "We have presented a complete worked example of a "
            "journal-article skeleton inside kherveDOC. Every "
            "block type the editor supports — sections, paragraphs, "
            "bulleted and ordered lists, inline and display math, "
            "tables, citations, cross-references, footnotes and "
            "links — appears at least once. Replace the placeholder "
            "text with your own and the layout will keep working.",
        ),

        Section(level=1, children=[Text(text="Acknowledgements")]),
        _p(
            "Thanks to the maintainers of ",
            Link(url="https://tectonic-typesetting.github.io/",
                 children=[Text(text="tectonic")]),
            " for the LaTeX engine that powers the preview, and to "
            "everyone who reported bugs against early builds of "
            "kherveDOC.",
        ),
    ]


def article() -> Document:
    """Single-column journal article skeleton: title, author, abstract,
    keywords, intro / background / methods / results / discussion /
    conclusion / acknowledgements. Long enough to span several pages
    so the new user sees a believable layout."""
    return Document(
        meta=_meta(title="An example article", author="A. Author"),
        children=_article_body(
            "An example article — single column",
            "kherveDOC example template",
        ),
    )


def two_column_article() -> Document:
    """Two-column article — the layout most physics / chemistry journals
    want for the camera-ready version."""
    return Document(
        meta=_meta(title="An example article", author="A. Author",
                   column_count=2),
        children=_article_body(
            "An example article — two columns",
            "kherveDOC two-column template",
        ),
    )


def three_column_document() -> Document:
    """Three-column document — wraps the body in multicols{3}."""
    return Document(
        meta=_meta(title="An example article", author="A. Author",
                   column_count=3, body_font_pt=10),
        children=_article_body(
            "An example article — three columns",
            "kherveDOC three-column template",
        ),
    )


# ---------------------------------------------------------------- math-heavy

def math_heavy() -> Document:
    """Example with several display equations and a long derivation —
    useful for sanity-checking the math round-trip."""
    return Document(
        meta=_meta(title="Quadratic forms"),
        children=[
            Title(children=[Text(text="Quadratic forms — a worked example")]),
            Author(children=[Text(text="kherveDOC math example")]),
            Abstract(children=[Text(text=
                "We work through the algebra of the real quadratic "
                "function in some detail, deriving the vertex form, "
                "the quadratic formula and the discriminant test. The "
                "purpose is to exercise the math-typesetting paths of "
                "the kherveDOC editor: inline math, numbered display "
                "equations, aligned multi-line derivations, and "
                "cross-references between them. The mathematics itself "
                "is elementary and standard.")]),

            Section(level=1, children=[Text(text="Definition")]),
            _p(
                "A real quadratic function ", MathInline(latex="f"),
                " is a polynomial of degree exactly two:",
            ),
            MathBlock(latex="f(x) = a x^2 + b x + c, \\qquad a \\neq 0,",
                      numbered=True, label="eq:quad"),
            _p(
                "with real coefficients ", MathInline(latex="a"), ", ",
                MathInline(latex="b"), " and ", MathInline(latex="c"),
                ". The condition ", MathInline(latex="a \\neq 0"),
                " distinguishes the quadratic case from the linear "
                "and constant cases. We will write ",
                MathInline(latex="\\Delta = b^2 - 4ac"),
                " for the discriminant, which encodes the number and "
                "nature of the real roots.",
            ),

            Section(level=1, children=[Text(text="Completing the square")]),
            _p(
                "Starting from ", CrossRef(label="eq:quad", kind="eqref"),
                ", factor the leading coefficient out of the "
                "quadratic and linear terms:",
            ),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  f(x) &= a\\left(x^2 + \\tfrac{b}{a} x\\right) + c.\n"
                    "\\end{align}"
                ),
                numbered=True,
            ),
            _p(
                "Inside the bracket we have a quadratic with leading "
                "coefficient 1, so we can complete the square by "
                "adding and subtracting ", MathInline(latex="(b/2a)^2"),
                ":",
            ),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  f(x) &= a\\left[\\left(x + \\tfrac{b}{2a}\\right)^2 "
                    "- \\tfrac{b^2}{4a^2}\\right] + c \\\\\n"
                    "       &= a\\left(x + \\tfrac{b}{2a}\\right)^2 "
                    "+ \\frac{4ac - b^2}{4a}.\n"
                    "\\end{align}"
                ),
                numbered=True, label="eq:vertex",
            ),
            _p(
                "Equation ", CrossRef(label="eq:vertex", kind="eqref"),
                " is the vertex form. It exhibits the minimum (or "
                "maximum, depending on the sign of ",
                MathInline(latex="a"), ") of the quadratic immediately: "
                "the vertex sits at ",
                MathInline(latex="x = -b / 2a"),
                " with value ",
                MathInline(latex="(4ac - b^2)/4a"),
                ".",
            ),

            Section(level=1, children=[Text(text="The quadratic formula")]),
            _p("To find the roots, set ", MathInline(latex="f(x) = 0"),
               " in ", CrossRef(label="eq:vertex", kind="eqref"), ":"),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  a\\left(x + \\tfrac{b}{2a}\\right)^2 "
                    "&= \\frac{b^2 - 4ac}{4a} \\\\\n"
                    "  \\left(x + \\tfrac{b}{2a}\\right)^2 "
                    "&= \\frac{b^2 - 4ac}{4a^2} \\\\\n"
                    "  x + \\tfrac{b}{2a} "
                    "&= \\pm \\frac{\\sqrt{b^2 - 4ac}}{2a} \\\\\n"
                    "  x &= \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}.\n"
                    "\\end{align}"
                ),
                numbered=True, label="eq:formula",
            ),
            _p(
                "Equation ", CrossRef(label="eq:formula", kind="eqref"),
                " is the familiar quadratic formula. Note that the "
                "derivation never assumed anything about the sign of "
                "the discriminant; the formula is valid for all real "
                "coefficients with ", MathInline(latex="a \\neq 0"),
                ", with the understanding that the square root is "
                "interpreted in the complex numbers when ",
                MathInline(latex="\\Delta < 0"), ".",
            ),

            Section(level=1, children=[Text(text="The discriminant")]),
            _p(
                "The discriminant ",
                MathInline(latex="\\Delta = b^2 - 4ac"),
                " determines the nature of the roots:",
            ),
            _items(
                "Δ > 0: two distinct real roots",
                "Δ = 0: one repeated real root, x = −b / 2a",
                "Δ < 0: two complex conjugate roots, real part −b / 2a, "
                "imaginary parts ±√|Δ| / 2a",
            ),
            _p(
                "The geometric content is clean: ",
                MathInline(latex="\\Delta"),
                " is (up to a sign and a scale) the squared distance "
                "from the vertex of the parabola to the x-axis. When "
                "the vertex is below the axis (and ",
                MathInline(latex="a > 0"), ") the parabola crosses the "
                "axis twice. When it sits exactly on the axis the "
                "parabola is tangent there. When it sits above, the "
                "parabola never touches the axis.",
            ),

            Section(level=1, children=[Text(text="A worked example")]),
            _p(
                "Take ", MathInline(latex="f(x) = 2 x^2 - 5 x + 1"), ". "
                "Then ", MathInline(latex="a = 2"), ", ",
                MathInline(latex="b = -5"), ", ",
                MathInline(latex="c = 1"), ", and the discriminant is",
            ),
            MathBlock(latex="\\Delta = (-5)^2 - 4 \\cdot 2 \\cdot 1 = 17 > 0,",
                      numbered=False),
            _p("so there are two distinct real roots, namely"),
            MathBlock(
                latex=(
                    "x = \\frac{5 \\pm \\sqrt{17}}{4} "
                    "\\approx 0.219, \\, 2.281."
                ),
                numbered=False,
            ),
            _p(
                "The vertex sits at ",
                MathInline(latex="x = 5/4"),
                " with value ",
                MathInline(latex="(4 \\cdot 2 \\cdot 1 - 25)/(4 \\cdot 2) = -17/8"),
                ", which is indeed below the axis as expected from the "
                "sign of the discriminant.",
            ),

            Section(level=1, children=[Text(text="Beyond the quadratic")]),
            _p(
                "The same technique — completing the square — extends "
                "to quadratic forms in several variables. For a real "
                "symmetric matrix ", MathInline(latex="A"),
                ", a vector ", MathInline(latex="\\mathbf{b}"),
                " and a scalar ", MathInline(latex="c"), ", the "
                "function",
            ),
            MathBlock(
                latex=("q(\\mathbf{x}) "
                       "= \\mathbf{x}^\\top A \\mathbf{x} "
                       "+ 2 \\mathbf{b}^\\top \\mathbf{x} + c"),
                numbered=True, label="eq:qform",
            ),
            _p(
                "has a unique stationary point at ",
                MathInline(latex="\\mathbf{x}^\\ast = -A^{-1} \\mathbf{b}"),
                " whenever ", MathInline(latex="A"),
                " is invertible. Substituting back into ",
                CrossRef(label="eq:qform", kind="eqref"),
                " gives the minimum value ",
                MathInline(latex="c - \\mathbf{b}^\\top A^{-1} \\mathbf{b}"),
                ". The one-variable case we worked through above is the "
                "special case ", MathInline(latex="A = [a]"),
                ", ", MathInline(latex="\\mathbf{b} = [b/2]"), ".",
            ),

            Section(level=1, children=[Text(text="Summary")]),
            _p(
                "We started with the bare definition of a real "
                "quadratic, derived the vertex form by completing the "
                "square, used the vertex form to obtain the quadratic "
                "formula, and connected the sign of the discriminant "
                "to the geometric picture of the parabola. The whole "
                "argument fits on a single page once the algebra is "
                "lined up properly — which is, after all, the point "
                "of having an editor that handles the alignment for "
                "you.",
            ),
        ],
    )


# ---------------------------------------------------------------- letter

def letter() -> Document:
    """A short formal letter — useful when you just need a one-page note.
    Uses the article class with adjusted margins; the LaTeX `letter`
    class itself can be selected from Document properties if you prefer."""
    return Document(
        meta=_meta(
            title="", author="",
            margin_left_cm=3.0, margin_right_cm=3.0,
            margin_top_cm=3.0, margin_bottom_cm=3.0,
            paragraph_indent=False,
        ),
        children=[
            # Sender block
            Paragraph(children=[Text(text="Dr Jane Author")], alignment="right"),
            Paragraph(children=[Text(text="Department of Examples")], alignment="right"),
            Paragraph(children=[Text(text="University of kherveDOC")], alignment="right"),
            Paragraph(children=[Text(text="123 Example Road")], alignment="right"),
            Paragraph(children=[Text(text="London, EC1A 1AA")], alignment="right"),
            Paragraph(children=[Text(text="jane.author@example.org")], alignment="right"),
            Paragraph(children=[Text(text="")]),

            # Recipient block
            Paragraph(children=[Text(text="Prof. Recipient Name")]),
            Paragraph(children=[Text(text="Editor-in-Chief")]),
            Paragraph(children=[Text(text="Journal of Worked Examples")]),
            Paragraph(children=[Text(text="456 Editorial Avenue")]),
            Paragraph(children=[Text(text="Cambridge, CB2 1TN")]),
            Paragraph(children=[Text(text="")]),
            Paragraph(children=[Text(text="17 May 2026", marks=["italic"])],
                      alignment="right"),
            Paragraph(children=[Text(text="")]),

            # Subject
            _p(("Subject: ", ["bold"]),
               ("Submission of manuscript JWE-2026-0142 for consideration",
                ["bold"])),
            Paragraph(children=[Text(text="")]),

            # Salutation
            _p("Dear Prof. Recipient,"),

            # Body — 4-5 substantive paragraphs
            _p(
                "I am writing to submit our manuscript, entitled "
                "\"A worked example of the kherveDOC editor for "
                "scientific writing,\" for consideration as a "
                "research article in the Journal of Worked Examples. "
                "The work has not been published elsewhere and is "
                "not under consideration at any other journal.",
            ),
            _p(
                "The manuscript presents the design and operation of "
                "kherveDOC, a WYSIWYG editor that stores documents "
                "as a structured model and serialises them to LaTeX "
                "on demand. We argue that the structured-model "
                "approach captures most of the productivity gains of "
                "a word processor without giving up the precise "
                "typographic control that LaTeX is valued for. The "
                "paper includes a worked end-to-end example of "
                "drafting, revising and submitting a short article.",
            ),
            _p(
                "Our principal contributions are threefold. First, we "
                "describe a document model that round-trips losslessly "
                "to LaTeX, including for environments and macros the "
                "editor does not itself understand. Second, we report "
                "a user study (N=37) in which participants drafted a "
                "short article more quickly in kherveDOC than in a "
                "traditional LaTeX setup, with no measurable loss of "
                "formatting quality. Third, we release the editor as "
                "open-source software under the BSD-3 licence; the "
                "source is available at the project repository.",
            ),
            _p(
                "We believe the manuscript will be of interest to "
                "your readership for two reasons. First, the technical "
                "design — particularly the use of Git as a "
                "first-class part of the editing loop — is novel and "
                "may be useful to other tool builders. Second, the "
                "user-study results address a long-standing question "
                "in the LaTeX community about whether WYSIWYG editing "
                "is compatible with high-quality typeset output.",
            ),
            _p(
                "We suggest the following reviewers, none of whom we "
                "have collaborated with in the past three years: "
                "Prof. X (University of Y), Dr Z (Institute of W) and "
                "Dr V (Lab of U). We have no preferred reviewers to "
                "exclude.",
            ),
            _p(
                "Thank you for considering our submission. I am happy "
                "to provide any additional information you may need, "
                "and look forward to hearing from you in due course.",
            ),
            Paragraph(children=[Text(text="")]),
            _p("Yours sincerely,"),
            Paragraph(children=[Text(text="")]),
            Paragraph(children=[Text(text="")]),
            _p("Dr Jane Author"),
            _p(("on behalf of all authors", ["italic"])),
        ],
    )


# --------------------------------------------------------- Elsevier journal

def elsevier_preprint() -> Document:
    """Elsevier preprint layout — single column, double-spaced, suitable
    for initial submission to any Elsevier journal."""
    return Document(
        meta=_meta(
            documentclass="elsarticle",
            title="A preprint submitted to an Elsevier journal",
            author="A. Author",
            line_spacing=2.0,
            packages=DEFAULT_PACKAGES + ["natbib", "hyperref", "lineno"],
            preamble_extras="\\journal{Journal Name Here}\n\\linenumbers",
        ),
        children=[
            Title(children=[Text(text="A preprint submitted to an Elsevier journal")]),
            Author(children=[Text(text="A. Author, B. Coauthor")]),
            Abstract(children=[Text(text=
                "This template follows the elsarticle class used by all "
                "Elsevier journals. The preprint option gives a single-column, "
                "double-spaced layout suitable for initial submission. "
                "Line numbers are enabled via the lineno package so reviewers "
                "can reference specific lines in their feedback. "
                "Once the paper is accepted, switch the document class to "
                "elsarticle with a final option (1p, 3p, or 5p) under "
                "File > Document properties to match the journal's "
                "production layout.")]),
            Keywords(children=[Text(text=
                "elsarticle · preprint · Elsevier · template")]),

            Section(level=1, children=[Text(text="Introduction")]),
            _p(
                "Elsevier publishes over 2,500 journals spanning the sciences, "
                "engineering, medicine and social sciences. The ",
                ("elsarticle", ["code"]), " document class is the standard "
                "submission format for all of them. It supports several "
                "layout modes, selectable as options to ",
                ("\\documentclass", ["code"]), ":"
            ),
            _items(
                "preprint — single-column, double-spaced (the default here)",
                "review — single-column with line numbers",
                "1p — single-column, final typeset",
                "3p — single-column, final typeset with tighter spacing",
                "5p — two-column, final typeset (typical for camera-ready)",
            ),
            _p(
                "You set the target journal name with the ",
                ("\\journal{...}", ["code"]),
                " command in the preamble (already filled in above). This "
                "name appears in the running headers of the compiled PDF.",
            ),

            Section(level=1, children=[Text(text="Front matter")]),
            _p(
                "The elsarticle class wraps title, authors, abstract and "
                "keywords in a ", ("\\begin{frontmatter}", ["code"]),
                " environment. kherveDOC handles this automatically — "
                "just fill in the Title, Author, Abstract and Keywords "
                "paragraphs as you would in any document.",
            ),
            _p(
                "For advanced author metadata (multiple affiliations, "
                "corresponding-author markers, e-mail addresses), import "
                "an existing .tex and the extra ", ("\\author[opts]{...}", ["code"]),
                " / ", ("\\ead{...}", ["code"]),
                " commands are preserved verbatim in the document settings.",
            ),

            Section(level=1, children=[Text(text="Citations")]),
            _p(
                "Elsevier journals use ", ("natbib", ["code"]),
                " for citation management. The three standard commands are ",
                ("\\cite{key}", ["code"]), " (numeric), ",
                ("\\citep{key}", ["code"]), " (parenthetical) and ",
                ("\\citet{key}", ["code"]),
                " (textual). kherveDOC's Insert > Citation dialog lets you "
                "choose the style per citation.",
            ),
            _p(
                "A bibliography file (.bib) is specified in the preamble "
                "with ", ("\\bibliographystyle{elsarticle-num}", ["code"]),
                " and ", ("\\bibliography{refs}", ["code"]),
                ". Common Elsevier bibliography styles:",
            ),
            _items(
                "elsarticle-num — numbered, e.g. [1]",
                "elsarticle-num-names — numbered with full author names",
                "elsarticle-harv — author–year, Harvard style",
            ),

            Section(level=1, children=[Text(text="Equations and figures")]),
            _p(
                "All standard LaTeX math works unchanged. Numbered equations "
                "get sequential labels that the journal typesetters preserve:",
            ),
            MathBlock(
                latex=r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}",
                numbered=True, label="eq:gauss-law",
            ),
            _p(
                "Figures use the standard ", ("figure", ["code"]),
                " environment with ", ("\\includegraphics", ["code"]),
                ". Elsevier's production workflow expects figures as separate "
                "files (EPS, PDF, or high-resolution PNG/TIFF), placed via ",
                ("\\includegraphics", ["code"]), " with explicit widths.",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "Replace this placeholder content with your own. The "
                "document class, packages and preamble are already configured "
                "for Elsevier submission — just write, compile, and export.",
            ),
        ],
    )


def elsevier_twocol() -> Document:
    """Elsevier final two-column layout (5p option) — what camera-ready
    papers look like in most Elsevier physics/engineering journals."""
    return Document(
        meta=_meta(
            documentclass="elsarticle",
            title="Elsevier two-column (5p) layout",
            author="A. Author",
            column_count=2,
            body_font_pt=10,
            packages=DEFAULT_PACKAGES + ["natbib", "hyperref"],
            preamble_extras="\\journal{Journal of Examples}",
        ),
        children=[
            Title(children=[Text(text="Elsevier two-column (5p) layout")]),
            Author(children=[Text(text="A. Author, B. Coauthor, C. Third")]),
            Abstract(children=[Text(text=
                "This template shows the two-column final layout used by "
                "many Elsevier physics and engineering journals. The 5p "
                "class option produces a compact, two-column format. "
                "Figures can span both columns using a figure* environment "
                "(Insert > Figure, then set width to full page). Tables "
                "similarly use table* for full-width placement.")]),
            Keywords(children=[Text(text=
                "Elsevier · two-column · 5p · camera-ready")]),

            Section(level=1, children=[Text(text="Introduction")]),
            _p(
                "The two-column layout is the standard camera-ready format "
                "for most Elsevier journals in physics, chemistry, "
                "engineering and computer science. Text flows in narrow "
                "columns for faster reading; equations, figures and tables "
                "can span both columns when they need the space."
            ),

            Section(level=1, children=[Text(text="Method")]),
            _p(
                "Describe your experimental or computational methodology "
                "here. In a two-column layout, long equations may need ",
                ("\\begin{equation*}", ["code"]),
                " with manual line-breaking, or the ", ("breqn", ["code"]),
                " package for automatic breaking.",
            ),
            MathBlock(
                latex=r"F = G \frac{m_1 m_2}{r^2}",
                numbered=True, label="eq:newton",
            ),

            Section(level=1, children=[Text(text="Results")]),
            _p(
                "Present your key findings. Tables render well in two "
                "columns as long as you keep them to 3–4 columns of data. "
                "Wider tables should span both columns.",
            ),
            Table(
                rows=[
                    ["Parameter", "Value", "Unit"],
                    ["Temperature", "293.15", "K"],
                    ["Pressure", "101.325", "kPa"],
                    ["Flow rate", "12.5", "mL/min"],
                ],
                caption="Experimental conditions.",
                label="tab:conditions",
                alignment="lrl",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "Summarise the key contributions and suggest directions "
                "for future work.",
            ),
        ],
    )


# --------------------------------------------------------- IEEE

def ieee_conference() -> Document:
    """IEEE conference paper layout using the IEEEtran class — the
    standard format for IEEE conferences and transactions."""
    return Document(
        meta=_meta(
            documentclass="IEEEtran",
            title="An IEEE conference paper",
            author="A. Author",
            column_count=2,
            body_font_pt=10,
            packages=DEFAULT_PACKAGES + ["cite", "hyperref", "url"],
            preamble_extras=(
                "% IEEE recommended packages\n"
                "\\usepackage[cmex10]{amsmath}\n"
                "\\interdisplaylinepenalty=2500"
            ),
        ),
        children=[
            Title(children=[Text(text="An IEEE conference paper template")]),
            Author(children=[Text(text=
                "A. Author, B. Coauthor")]),
            Abstract(children=[Text(text=
                "This template uses the IEEEtran document class, which is "
                "the standard for all IEEE publications — conferences, "
                "transactions and journals. The class enforces the familiar "
                "two-column layout with IEEE-standard fonts, spacing and "
                "heading styles. Common class options include: conference "
                "(default), journal, technote, and compsoc for Computer "
                "Society publications.")]),
            Keywords(children=[Text(text=
                "IEEE · IEEEtran · conference · template")]),

            Section(level=1, children=[Text(text="Introduction")]),
            _p(
                "IEEE publishes over 200 journals and sponsors more than "
                "2,000 conferences annually. The IEEEtran class is maintained "
                "by Michael Shell and available on CTAN. It handles "
                "first-page formatting, author affiliations, abstract layout, "
                "section numbering and bibliography style automatically."
            ),
            _p(
                "Key class options you can set under Document properties:",
            ),
            _items(
                "conference — conference proceedings (default)",
                "journal — IEEE transactions and journals",
                "technote — IEEE technical notes",
                "compsoc — IEEE Computer Society style",
                "comsoc — IEEE Communications Society style",
            ),

            Section(level=1, children=[Text(text="Related work")]),
            _p(
                "Position your contribution relative to the existing "
                "literature. IEEE style uses numbered citations in square "
                "brackets ", Citation(keys=["ref1"], style="cite"),
                ". The cite package sorts and compresses them automatically, "
                "so ", ("\\cite{a,b,c}", ["code"]), " renders as [1]–[3].",
            ),

            Section(level=1, children=[Text(text="System model")]),
            _p(
                "Describe the system, algorithm or architecture. IEEE papers "
                "often include block diagrams as figures and key equations "
                "inline. The standard Shannon capacity:",
            ),
            MathBlock(
                latex=r"C = B \log_2\!\left(1 + \frac{S}{N}\right)",
                numbered=True, label="eq:shannon",
            ),

            Section(level=1, children=[Text(text="Experimental results")]),
            _p(
                "Tables in IEEE papers use the standard table environment. "
                "The class automatically sets the caption above the table "
                "in Roman numeral style.",
            ),
            Table(
                rows=[
                    ["Method", "Accuracy (%)", "Time (ms)"],
                    ["Baseline", "87.3", "12"],
                    ["Proposed", "93.1", "15"],
                    ["Oracle", "98.2", "—"],
                ],
                caption="Comparison of methods on the benchmark dataset.",
                label="tab:ieee-results",
                alignment="lrr",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "Summarise your contribution and outline future directions. "
                "IEEE papers typically end with an acknowledgement section "
                "(unnumbered) and a references section.",
            ),
        ],
    )


# ------------------------------------------------ APS / Physical Review

def revtex_article() -> Document:
    """APS Physical Review article using revtex4-2 — covers PRL, PRA–PRE,
    PRX, Physical Review Research, etc."""
    return Document(
        meta=_meta(
            documentclass="revtex4-2",
            title="A Physical Review article",
            author="A. Author",
            body_font_pt=10,
            packages=DEFAULT_PACKAGES + ["natbib", "hyperref"],
            preamble_extras=(
                "% APS options: aps, prl, pra, prb, prc, prd, pre, prx\n"
                "% Add [twocolumn] to documentclass for final layout\n"
                "% Add [reprint] for single-column reprint style"
            ),
        ),
        children=[
            Title(children=[Text(text="A Physical Review article template")]),
            Author(children=[Text(text="A. Author and B. Coauthor")]),
            Abstract(children=[Text(text=
                "This template uses the revtex4-2 class maintained by the "
                "American Physical Society. It is the required format for "
                "Physical Review Letters, Physical Review A–E, Physical "
                "Review X, Physical Review Research and Reviews of Modern "
                "Physics. The class extends the standard article class with "
                "physics-specific features: PACS/MSC codes, multiple "
                "affiliations and footnote-style author marks.")]),
            Keywords(children=[Text(text=
                "revtex · APS · Physical Review · PRL · template")]),

            Section(level=1, children=[Text(text="Introduction")]),
            _p(
                "The revtex4-2 class supports multiple journal targets via "
                "class options. Set the journal under Document properties by "
                "typing the full class option string, for example ",
                ("revtex4-2", ["code"]),
                " with options ",
                ("aps,prl,preprint", ["code"]),
                " for a PRL preprint. Common journal options:",
            ),
            _items(
                "aps — American Physical Society (default)",
                "aip — American Institute of Physics (e.g., J. Chem. Phys.)",
                "prl — Physical Review Letters",
                "prb — Physical Review B",
                "prx — Physical Review X",
            ),
            _p(
                "Layout options control the column format:",
            ),
            _items(
                "preprint — single-column, double-spaced (for submission)",
                "twocolumn — two-column (for camera-ready)",
                "reprint — single-column reprint style",
            ),

            Section(level=1, children=[Text(text="Theory")]),
            _p(
                "RevTeX is optimised for physics notation. The Dirac "
                "equation in natural units:",
            ),
            MathBlock(
                latex=r"(i \gamma^\mu \partial_\mu - m) \psi = 0",
                numbered=True, label="eq:dirac",
            ),
            _p(
                "Multi-line derivations use the standard ",
                ("align", ["code"]),
                " environment. The class loads amsmath automatically, so "
                "all AMS environments are available without extra packages.",
            ),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  \\hat{H} |\\psi\\rangle &= E |\\psi\\rangle \\\\\n"
                    "  \\langle \\psi | \\hat{H} | \\psi \\rangle &= E\n"
                    "\\end{align}"
                ),
                numbered=True,
            ),

            Section(level=1, children=[Text(text="Experimental details")]),
            _p(
                "RevTeX papers typically include detailed experimental "
                "parameters in tabular form:",
            ),
            Table(
                rows=[
                    ["Quantity", "Value", "Uncertainty"],
                    ["Wavelength", "532 nm", "±0.1 nm"],
                    ["Power", "50 mW", "±2 mW"],
                    ["Pulse width", "10 ns", "±0.5 ns"],
                ],
                caption="Laser parameters used in the experiment.",
                label="tab:laser",
                alignment="lrl",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "Replace this template with your own content. The document "
                "class, packages and APS-specific preamble are ready for "
                "submission.",
            ),
        ],
    )


# -------------------------------------------------------- ACS chemistry

def acs_article() -> Document:
    """American Chemical Society journal article using the achemso class."""
    return Document(
        meta=_meta(
            documentclass="achemso",
            title="An ACS journal article",
            author="A. Author",
            body_font_pt=12,
            packages=DEFAULT_PACKAGES + ["natbib", "hyperref", "chemformula"],
            preamble_extras=(
                "% Set the target journal abbreviation:\n"
                "% \\journal{jacsat}  % J. Am. Chem. Soc.\n"
                "% \\journal{jpcafh}  % J. Phys. Chem. A\n"
                "% \\journal{nalefd}  % Nano Letters\n"
                "% \\journal{ancham}  % Anal. Chem."
            ),
        ),
        children=[
            Title(children=[Text(text="An ACS journal article template")]),
            Author(children=[Text(text="A. Author, B. Coauthor")]),
            Abstract(children=[Text(text=
                "This template uses the achemso class for submissions to "
                "American Chemical Society journals — JACS, Nano Letters, "
                "ACS Nano, Journal of Physical Chemistry and many others. "
                "The class handles ACS-specific formatting: structured "
                "abstracts (for some journals), author affiliations with "
                "superscript markers, and ACS citation style.")]),
            Keywords(children=[Text(text=
                "achemso · ACS · chemistry · JACS · template")]),

            Section(level=1, children=[Text(text="Introduction")]),
            _p(
                "The achemso class is maintained on CTAN and mirrors the "
                "ACS submission guidelines. It automatically loads natbib "
                "and sets the bibliography style to match the target journal. "
                "Common target journals can be set in the preamble with ",
                ("\\journal{abbreviation}", ["code"]), ".",
            ),
            _p("Some frequently used ACS journal codes:"),
            _items(
                "jacsat — Journal of the American Chemical Society",
                "jpcafh — Journal of Physical Chemistry A",
                "nalefd — Nano Letters",
                "ancham — Analytical Chemistry",
                "achre4 — Accounts of Chemical Research",
                "langd5 — Langmuir",
            ),

            Section(level=1, children=[Text(text="Experimental section")]),
            _p(
                "ACS papers place detailed experimental procedures in this "
                "section. Chemical formulae can be typeset inline using "
                "the chemformula package: ",
                MathInline(latex=r"\ch{H2O}"),
                ", ",
                MathInline(latex=r"\ch{CO2}"),
                ", ",
                MathInline(latex=r"\ch{NaCl}"),
                ". For reaction schemes, use the ",
                ("\\ch{}", ["code"]), " command:",
            ),
            MathBlock(
                latex=r"\ch{2 H2 + O2 -> 2 H2O}",
                numbered=False,
            ),
            _p(
                "Thermodynamic quantities follow ACS conventions:",
            ),
            MathBlock(
                latex=r"\Delta G^\circ = \Delta H^\circ - T \Delta S^\circ",
                numbered=True, label="eq:gibbs",
            ),

            Section(level=1, children=[Text(text="Results and discussion")]),
            _p(
                "ACS journals often combine results and discussion. "
                "Quantitative data are best presented in tables:",
            ),
            Table(
                rows=[
                    ["Compound", "Yield (%)", "m.p. (°C)", "Purity (%)"],
                    ["1a", "87", "142–144", "99.2"],
                    ["1b", "72", "156–158", "98.7"],
                    ["1c", "91", "131–133", "99.5"],
                ],
                caption="Synthesis results for compounds 1a–1c.",
                label="tab:synthesis",
                alignment="lrrr",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "Summarise the key chemical findings and their significance. "
                "Replace this template content with your manuscript.",
            ),
        ],
    )


# ---------------------------------------------------- thesis / report

def thesis() -> Document:
    """Thesis or long report layout using the report class with typical
    graduate-school formatting: double-spaced, wide margins for binding."""
    return Document(
        meta=_meta(
            documentclass="report",
            title="A thesis or dissertation",
            author="A. Student",
            body_font_pt=12,
            line_spacing=2.0,
            margin_left_cm=3.5,
            margin_right_cm=2.5,
            margin_top_cm=2.5,
            margin_bottom_cm=2.5,
            packages=DEFAULT_PACKAGES + ["natbib", "hyperref", "appendix"],
        ),
        children=[
            Title(children=[Text(text="Title of the thesis")]),
            Author(children=[Text(text="A. Student")]),
            Abstract(children=[Text(text=
                "This template uses the standard report class configured "
                "for a typical graduate thesis or dissertation. It has "
                "double line-spacing, a wider left margin for binding, "
                "and chapter-level sectioning (Heading 1 = \\chapter). "
                "Adapt the margins and spacing to your institution's "
                "requirements under File > Document properties.")]),

            Section(level=1, children=[Text(text="Introduction")]),
            Section(level=2, children=[Text(text="Motivation")]),
            _p(
                "The report class is the natural choice for any long-form "
                "document with chapters: theses, dissertations, technical "
                "reports, and project write-ups. It differs from the "
                "article class mainly in that Heading 1 produces "
                "\\chapter (starting a new page) rather than \\section.",
            ),
            Section(level=2, children=[Text(text="Objectives")]),
            _p(
                "State the research questions or objectives of the work. "
                "Number them for easy cross-referencing in later chapters.",
            ),
            _ord_items(
                "First research question or objective",
                "Second research question or objective",
                "Third research question or objective",
            ),

            Section(level=1, children=[Text(text="Literature review")]),
            _p(
                "Survey the relevant prior work and identify the gap your "
                "thesis addresses. Use citations extensively: ",
                Citation(keys=["smith2020", "jones2021"], style="citep"),
                ". A typical thesis chapter runs 15–30 pages with dozens "
                "of references.",
            ),

            Section(level=1, children=[Text(text="Methodology")]),
            _p(
                "Describe your methods in enough detail for reproduction. "
                "Mathematical notation follows the same conventions as in "
                "a journal paper:",
            ),
            MathBlock(
                latex=r"\hat{\beta} = (X^\top X)^{-1} X^\top y",
                numbered=True, label="eq:ols",
            ),

            Section(level=1, children=[Text(text="Results")]),
            _p("Present your results here with tables and figures."),

            Section(level=1, children=[Text(text="Discussion")]),
            _p("Interpret the results in the context of the literature."),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "Summarise the thesis contributions and suggest future work.",
            ),
        ],
    )


# -------------------------------------------------------- beamer slides

def beamer_slides() -> Document:
    """Beamer presentation template — a skeleton slide deck."""
    return Document(
        meta=_meta(
            documentclass="beamer",
            title="A presentation",
            author="A. Speaker",
            body_font_pt=11,
            packages=DEFAULT_PACKAGES + ["hyperref"],
            preamble_extras=(
                "\\usetheme{Madrid}\n"
                "\\usecolortheme{default}\n"
                "% Other popular themes: Berlin, Boadilla, CambridgeUS,\n"
                "% Copenhagen, Darmstadt, Frankfurt, Hannover, Luebeck,\n"
                "% Malmoe, Marburg, Montpellier, PaloAlto, Pittsburgh,\n"
                "% Rochester, Singapore, Szeged, Warsaw\n"
                "% Colour themes: albatross, beaver, beetle, crane,\n"
                "% dolphin, dove, fly, lily, orchid, rose, seagull,\n"
                "% seahorse, whale, wolverine"
            ),
        ),
        children=[
            Title(children=[Text(text="Presentation title")]),
            Author(children=[Text(text="A. Speaker — Institution")]),

            Section(level=1, children=[Text(text="Introduction")]),
            _p(
                "This template uses the beamer class for creating PDF "
                "presentations. Each Heading 1 creates a new section; "
                "each Heading 2 creates a new frame (slide). The Madrid "
                "theme is set in the preamble — change it to any of "
                "the themes listed in the comments.",
            ),

            Section(level=2, children=[Text(text="What is beamer?")]),
            _p(
                "Beamer is the standard LaTeX class for slide presentations. "
                "It supports overlays, animations, handout mode and "
                "speaker notes. kherveDOC compiles beamer documents "
                "to PDF — each slide becomes one page.",
            ),
            _items(
                "Bullet points render as standard itemize",
                "Math works exactly as in articles",
                "Tables and figures are supported",
                "Themes control the visual appearance",
            ),

            Section(level=2, children=[Text(text="Mathematics in slides")]),
            _p("Equations work the same as in any LaTeX document:"),
            MathBlock(
                latex=r"e^{i\pi} + 1 = 0",
                numbered=False,
            ),

            Section(level=1, children=[Text(text="Main content")]),
            Section(level=2, children=[Text(text="Key results")]),
            _p("Present your main results here. Keep slides concise."),
            Table(
                rows=[
                    ["Metric", "Before", "After"],
                    ["Accuracy", "82%", "95%"],
                    ["Speed", "120 ms", "45 ms"],
                ],
                caption="Performance comparison.",
                label="tab:beamer-results",
                alignment="lrr",
            ),

            Section(level=2, children=[Text(text="Summary")]),
            _p("Conclude with your key takeaways."),
            _ord_items(
                "First main contribution",
                "Second main contribution",
                "Future work direction",
            ),
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

# Journal and publisher templates — grouped by publisher so the Examples
# menu can present them in a submenu.
JOURNAL_EXAMPLES: list[tuple[str, callable]] = [
    ("&Elsevier preprint (elsarticle)",   elsevier_preprint),
    ("Elsevier &two-column (5p)",         elsevier_twocol),
    ("&IEEE conference (IEEEtran)",       ieee_conference),
    ("APS / Physical &Review (revtex4-2)", revtex_article),
    ("&ACS journal (achemso)",            acs_article),
    ("&Thesis / report",                  thesis),
    ("&Beamer slides",                    beamer_slides),
]
