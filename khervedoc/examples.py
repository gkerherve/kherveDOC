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
