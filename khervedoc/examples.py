"""Example documents shown under the Examples menu and used as the
starting document when KherveTeX opens for the first time.

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
    Figure, Footnote, Frame, Keywords, Link, List as ListNode, ListItem,
    MathBlock, MathInline, Paragraph, RawLatex, Section, Table, Text, Title,
)


# ---------------------------------------------------------------- helpers

def _meta(**overrides) -> DocMeta:
    """Build a DocMeta with the KherveTeX defaults and let callers tweak
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
    """Multi-page tour of KherveTeX's main features — what new users see
    when they open the app."""
    return Document(
        meta=_meta(title="Welcome to KherveTeX", author="The KherveTeX team"),
        children=[
            Title(children=[Text(text="Welcome to KherveTeX")]),
            Author(children=[Text(text="A guided tour of the editor")]),

            # ---- What it is ----
            Section(level=1, children=[Text(text="What KherveTeX is")]),
            _p(
                "KherveTeX is a WYSIWYG editor that produces real LaTeX. "
                "You type the way you would in Word; the preview on the "
                "right compiles to PDF every time you stop typing. "
                "Underneath, the document is stored as a structured model "
                "— section headings, paragraphs, math, tables, figures, "
                "lists — and the serializer turns that into clean .tex "
                "you can hand to a journal, a co-author, or a git diff.",
            ),
            _p(
                "If you have never written LaTeX directly, you will not "
                "need to. If you have, KherveTeX stays out of your way: "
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
                "KherveTeX will push to it automatically. The commits use "
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
                "figure layout works whether you compile from KherveTeX, "
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
                " (which is the LaTeX engine KherveTeX compiles with) "
                "and ",
                Link(url="https://github.com/gkerherve/KherveTeX",
                     children=[Text(text="the KherveTeX repository")]),
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
                "independent KherveTeX window. File > Open in new "
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
                ("— The KherveTeX team", ["italic"]),
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
                "We present a worked example of the KherveTeX editor "
                "in a journal-article layout. The document is intended "
                "as a starting point for new users: every block type "
                "the editor supports is exercised at least once so "
                "that copy-pasting from this skeleton into a real "
                "paper Just Works. We summarise the structure, "
                "describe how each section is typically used, and "
                "include enough mathematics, references and tabular "
                "data to demonstrate the preview pipeline end to end.")]),
        Keywords(children=[Text(text="KherveTeX · template · article · example")]),

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
            "The KherveTeX editor was designed to remove the "
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
            "when round-tripped. KherveTeX takes a third path: keep "
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
            "journal-article skeleton inside KherveTeX. Every "
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
            "KherveTeX.",
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
            "KherveTeX example template",
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
            "KherveTeX two-column template",
        ),
    )


def three_column_document() -> Document:
    """Three-column document — wraps the body in multicols{3}."""
    return Document(
        meta=_meta(title="An example article", author="A. Author",
                   column_count=3, body_font_pt=10),
        children=_article_body(
            "An example article — three columns",
            "KherveTeX three-column template",
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
            Author(children=[Text(text="KherveTeX math example")]),
            Abstract(children=[Text(text=
                "We work through the algebra of the real quadratic "
                "function in some detail, deriving the vertex form, "
                "the quadratic formula and the discriminant test. The "
                "purpose is to exercise the math-typesetting paths of "
                "the KherveTeX editor: inline math, numbered display "
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
            Paragraph(children=[Text(text="University of KherveTeX")], alignment="right"),
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
                "\"A worked example of the KherveTeX editor for "
                "scientific writing,\" for consideration as a "
                "research article in the Journal of Worked Examples. "
                "The work has not been published elsewhere and is "
                "not under consideration at any other journal.",
            ),
            _p(
                "The manuscript presents the design and operation of "
                "KherveTeX, a WYSIWYG editor that stores documents "
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
                "short article more quickly in KherveTeX than in a "
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
                " environment. KherveTeX handles this automatically — "
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
                " (textual). KherveTeX's Insert > Citation dialog lets you "
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
            packages=DEFAULT_PACKAGES + [
                "natbib", "hyperref", "appendix", "algorithm2e",
            ],
        ),
        children=[
            Title(children=[Text(text="Title of the Thesis")]),
            Author(children=[Text(text="A. Student — University of Somewhere")]),
            Abstract(children=[Text(text=
                "This template demonstrates the report class configured "
                "for a typical graduate thesis. It features double "
                "line-spacing, a wider left margin for binding, and "
                "chapter-level sectioning (Heading 1 = \\chapter). The "
                "template showcases cross-references, citations, figures, "
                "tables, equations, algorithms, and appendices.")]),
            Abstract(children=[Text(text=
                "Adapt the margins and spacing to your institution's "
                "requirements under File > Document properties. Replace "
                "the placeholder text with your own content.")]),

            RawLatex(text=(
                "\\chapter*{Dedication}\n"
                "\\addcontentsline{toc}{chapter}{Dedication}\n"
                "\\vspace*{3cm}\n"
                "\\begin{center}\n"
                "\\textit{To my family, for their unwavering support.}\n"
                "\\end{center}\n"
                "\\newpage"
            )),

            RawLatex(text=(
                "\\chapter*{Acknowledgements}\n"
                "\\addcontentsline{toc}{chapter}{Acknowledgements}"
            )),
            _p(
                "I would like to thank my supervisor, Prof. J. Smith, "
                "for their guidance throughout this research. I am also "
                "grateful to the members of the lab for fruitful "
                "discussions, and to the funding body for financial "
                "support.",
            ),

            RawLatex(text="\\tableofcontents\n\\newpage"),

            # --- Chapter 1: Introduction ---
            Section(level=1, children=[Text(text="Introduction")]),

            Section(level=2, children=[Text(text="Background and motivation")]),
            _p(
                "The report class is the natural choice for any long-form "
                "document with chapters: theses, dissertations, technical "
                "reports, and project write-ups. It differs from the "
                "article class mainly in that Heading 1 produces "
                "\\chapter (starting a new page) rather than \\section.",
            ),
            _p(
                "Recent advances in the field ",
                Citation(keys=["smith2020", "jones2021"], style="citep"),
                " have opened new avenues for exploration. However, "
                "several open questions remain, particularly concerning "
                "the scalability of existing approaches and their "
                "applicability to real-world datasets.",
            ),

            Section(level=2, children=[Text(text="Research objectives")]),
            _p(
                "This thesis addresses the following research questions:",
            ),
            _ord_items(
                "How does the proposed method compare to baseline "
                "approaches on standard benchmarks?",
                "What is the computational complexity of the algorithm, "
                "and how does it scale with input size?",
                "Can the method generalise to unseen domains without "
                "re-training?",
            ),

            Section(level=2, children=[Text(text="Thesis outline")]),
            _p(
                "The remainder of this thesis is organised as follows. "
                "Chapter 2 reviews the relevant literature. Chapter 3 "
                "describes the methodology and algorithm design. "
                "Chapter 4 presents the experimental results "
                "(see Table ", CrossRef(label="tab:results", kind="ref"),
                " and Figure ", CrossRef(label="fig:results", kind="ref"),
                "). Chapter 5 discusses the findings, and Chapter 6 "
                "concludes with a summary and directions for future work.",
            ),

            # --- Chapter 2: Literature Review ---
            Section(level=1, children=[Text(text="Literature Review")]),

            Section(level=2, children=[Text(text="Theoretical foundations")]),
            _p(
                "The mathematical framework underpinning this work builds "
                "on the seminal contributions of ",
                Citation(keys=["fourier1822"], style="citet"),
                " and subsequent extensions by ",
                Citation(keys=["shannon1948"], style="citet"),
                ". The key insight is that any signal can be decomposed "
                "into a linear combination of orthogonal basis functions.",
            ),

            Section(level=2, children=[Text(text="Related work")]),
            _p(
                "Several authors have proposed methods that are related "
                "to ours. ",
                Citation(keys=["doe2019"], style="citet"),
                " introduced a variational approach that achieves "
                "competitive accuracy but requires cubic time complexity. ",
                Citation(keys=["lee2022"], style="citet"),
                " later improved upon this with a linearised "
                "approximation, though at the cost of reduced precision.",
            ),

            Section(level=2, children=[Text(text="Identified gap")]),
            _p(
                "Despite these advances, no existing method simultaneously "
                "achieves sub-quadratic complexity and maintains accuracy "
                "above 90\\% on the benchmark suite. This thesis proposes "
                "a novel algorithm that meets both criteria (see Equation ",
                CrossRef(label="eq:objective", kind="eqref"),
                " in Chapter 3).",
            ),

            # --- Chapter 3: Methodology ---
            Section(level=1, children=[Text(text="Methodology")]),

            Section(level=2, children=[Text(text="Problem formulation")]),
            _p(
                "Let the input data be represented as a matrix ",
                MathInline(latex="X \\in \\mathbb{R}^{n \\times d}"),
                " and the target vector as ",
                MathInline(latex="y \\in \\mathbb{R}^n"),
                ". The objective is to find the parameter vector ",
                MathInline(latex="\\beta^*"),
                " that minimises the regularised loss:",
            ),
            MathBlock(
                latex=r"\beta^* = \arg\min_{\beta} \|X\beta - y\|_2^2 "
                      r"+ \lambda \|\beta\|_1",
                numbered=True, label="eq:objective",
            ),

            Section(level=2, children=[Text(text="Proposed algorithm")]),
            _p(
                "We introduce Algorithm 1 below, which solves Equation ",
                CrossRef(label="eq:objective", kind="eqref"),
                " in ", MathInline(latex="O(n \\log n)"), " time.",
            ),
            RawLatex(text=(
                "\\begin{algorithm}[H]\n"
                "\\SetAlgoLined\n"
                "\\KwIn{Data matrix $X$, target $y$, regularisation $\\lambda$}\n"
                "\\KwOut{Optimal parameters $\\beta^*$}\n"
                "Initialise $\\beta_0 \\leftarrow 0$\\;\n"
                "\\For{$t = 1$ \\KwTo $T$}{\n"
                "  Compute gradient $g_t \\leftarrow \\nabla L(\\beta_{t-1})$\\;\n"
                "  Update $\\beta_t \\leftarrow \\mathrm{prox}_{\\lambda}(\\beta_{t-1} - \\eta g_t)$\\;\n"
                "}\n"
                "\\Return $\\beta_T$\\;\n"
                "\\caption{Proximal gradient descent}\n"
                "\\label{alg:pgd}\n"
                "\\end{algorithm}"
            )),

            Section(level=2, children=[Text(text="Implementation details")]),
            _p(
                "The algorithm was implemented in Python 3.12 using NumPy "
                "for linear algebra operations. All experiments were run "
                "on a workstation with an AMD Ryzen 9 CPU and 64 GB RAM. "
                "The convergence tolerance was set to ",
                MathInline(latex="\\epsilon = 10^{-6}"),
                " and the maximum number of iterations to ",
                MathInline(latex="T = 10{,}000"), ".",
            ),

            # --- Chapter 4: Results ---
            Section(level=1, children=[Text(text="Results")]),

            Section(level=2, children=[Text(text="Quantitative evaluation")]),
            _p(
                "Table ", CrossRef(label="tab:results", kind="ref"),
                " summarises the performance of our method against "
                "three baselines across four benchmark datasets.",
            ),
            Table(
                rows=[
                    ["Method", "Dataset A", "Dataset B", "Dataset C", "Dataset D"],
                    ["Baseline 1", "82.3%", "78.1%", "85.6%", "79.4%"],
                    ["Baseline 2", "84.7%", "80.3%", "86.2%", "81.0%"],
                    ["Baseline 3", "86.1%", "82.5%", "87.0%", "83.2%"],
                    ["Ours", "91.4%", "89.7%", "92.1%", "90.3%"],
                ],
                caption="Accuracy comparison across benchmark datasets.",
                label="tab:results",
                alignment="lcccc",
            ),
            _p(
                "Our method outperforms all baselines on every dataset, "
                "with the largest improvement (+7.2 pp) on Dataset B. "
                "The gains are statistically significant at ",
                MathInline(latex="p < 0.01"), " under a paired t-test.",
            ),

            Section(level=2, children=[Text(text="Qualitative analysis")]),
            _p(
                "Figure ", CrossRef(label="fig:results", kind="ref"),
                " illustrates a typical convergence trajectory. The "
                "algorithm reaches near-optimal loss within the first "
                "500 iterations.",
            ),
            Figure(
                path="figures/convergence.pdf",
                caption="Convergence of the objective function over iterations.",
                label="fig:results",
                width="0.75\\textwidth",
            ),

            # --- Chapter 5: Discussion ---
            Section(level=1, children=[Text(text="Discussion")]),

            Section(level=2, children=[Text(text="Interpretation of results")]),
            _p(
                "The results in Table ",
                CrossRef(label="tab:results", kind="ref"),
                " confirm that the ",
                MathInline(latex="\\ell_1"),
                "-regularised formulation (Equation ",
                CrossRef(label="eq:objective", kind="eqref"),
                ") induces sufficient sparsity to improve generalisation "
                "while maintaining computational efficiency.",
            ),

            Section(level=2, children=[Text(text="Limitations")]),
            _items(
                "The current method assumes the features are standardised; "
                "non-standardised inputs may require a pre-processing step.",
                "We evaluated on tabular data only; extension to image or "
                "text domains remains future work.",
                "The convergence guarantee assumes strong convexity, which "
                "may not hold for all loss functions.",
            ),

            # --- Chapter 6: Conclusion ---
            Section(level=1, children=[Text(text="Conclusion")]),

            Section(level=2, children=[Text(text="Summary of contributions")]),
            _ord_items(
                "A novel proximal gradient algorithm (Algorithm 1) that "
                "achieves sub-quadratic complexity.",
                "Empirical validation on four standard benchmarks showing "
                "consistent accuracy gains over existing methods.",
                "An open-source implementation available for "
                "reproducibility.",
            ),

            Section(level=2, children=[Text(text="Future work")]),
            _p(
                "Future directions include extending the algorithm to "
                "streaming data settings, investigating non-convex "
                "variants of the objective, and applying the method to "
                "large-scale industrial datasets.",
            ),

            # --- Appendix ---
            RawLatex(text="\\appendix"),

            Section(level=1, children=[Text(text="Supplementary Data")]),
            _p(
                "This appendix contains supplementary tables and figures "
                "referenced in the main text. Additional experimental "
                "results, including per-fold cross-validation scores, "
                "are available in the accompanying online repository.",
            ),
            Table(
                rows=[
                    ["Fold", "Precision", "Recall", "F1"],
                    ["1", "0.923", "0.911", "0.917"],
                    ["2", "0.935", "0.928", "0.931"],
                    ["3", "0.918", "0.905", "0.911"],
                    ["4", "0.941", "0.932", "0.936"],
                    ["5", "0.929", "0.919", "0.924"],
                ],
                caption="Per-fold cross-validation results on Dataset A.",
                label="tab:cv-results",
                alignment="lccc",
            ),

            Section(level=1, children=[Text(text="Derivations")]),
            _p(
                "This appendix provides the full derivation of the "
                "gradient expression used in Algorithm 1. Starting from "
                "the loss function in Equation ",
                CrossRef(label="eq:objective", kind="eqref"),
                ":",
            ),
            MathBlock(
                latex=r"\nabla L(\beta) = 2 X^\top (X\beta - y) "
                      r"+ \lambda \, \mathrm{sign}(\beta)",
                numbered=True, label="eq:gradient",
            ),

            _p(
                "A complete bibliography should be placed here using "
                "\\\\bibliography\\{refs\\} and \\\\bibliographystyle\\{\\} "
                "commands, or managed via BibTeX / BibLaTeX.",
            ),
        ],
    )


# -------------------------------------------------------- beamer slides

def beamer_slides() -> Document:
    """Beamer presentation template using Frame blocks for slides."""
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

            Frame(children=[Text(text="Outline")]),
            RawLatex(text="\\tableofcontents"),

            Section(level=1, children=[Text(text="Introduction")]),

            Frame(children=[Text(text="What is beamer?")]),
            _p(
                "Beamer is the standard LaTeX class for slide "
                "presentations. It supports overlays, animations, "
                "handout mode and speaker notes.",
            ),
            _items(
                "Each Frame block becomes one slide",
                "Sections create outline entries",
                "Math, tables, and figures work as in articles",
                "Themes control the visual appearance",
            ),

            Frame(children=[Text(text="Mathematics in slides")]),
            _p("Equations work the same as in any LaTeX document:"),
            MathBlock(
                latex=r"e^{i\pi} + 1 = 0",
                numbered=False,
            ),

            Section(level=1, children=[Text(text="Main Content")]),

            Frame(children=[Text(text="Key Results")]),
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

            Frame(children=[Text(text="Summary")]),
            _p("Conclude with your key takeaways."),
            _ord_items(
                "First main contribution",
                "Second main contribution",
                "Future work direction",
            ),
        ],
    )


# ------------------------------------------------------- curriculum vitae

def cv() -> Document:
    """Academic CV / résumé — sections for education, experience,
    publications and skills."""
    return Document(
        meta=_meta(
            title="Curriculum Vitae",
            author="J. Researcher",
            body_font_pt=11,
            margin_left_cm=2.0, margin_right_cm=2.0,
            margin_top_cm=2.0, margin_bottom_cm=2.0,
            paragraph_indent=False,
        ),
        children=[
            Title(children=[Text(text="Dr Jane A. Researcher")]),
            Author(children=[Text(text="Curriculum Vitae")]),

            Paragraph(children=[
                Text(text="Department of Physics, University of Somewhere · "),
                Link(url="mailto:jane.researcher@example.org",
                     children=[Text(text="jane.researcher@example.org")]),
                Text(text=" · "),
                Link(url="https://orcid.org/0000-0000-0000-0001",
                     children=[Text(text="ORCID 0000-0000-0000-0001")]),
            ], alignment="center"),

            Section(level=1, children=[Text(text="Education")]),
            _p(("PhD in Condensed Matter Physics", ["bold"]),
               ", University of Somewhere, 2019–2023"),
            _p("Thesis: ", ("Topological phases in two-dimensional "
               "electron gases under periodic driving", ["italic"])),
            _p("Supervisor: Prof. M. Topologist"),
            Paragraph(children=[Text(text="")]),
            _p(("MSci Physics (First Class)", ["bold"]),
               ", Imperial College London, 2015–2019"),
            _p("Final-year project: ", ("Raman spectroscopy of "
               "graphene heterostructures", ["italic"])),

            Section(level=1, children=[Text(text="Research experience")]),
            _p(("Postdoctoral Research Associate", ["bold"]),
               " — University of Somewhere, Oct 2023–present"),
            _items(
                "Developing theoretical models for Floquet topological "
                "insulators under dissipation",
                "Supervising two PhD students on related projects",
                "Maintaining group computing cluster (48 nodes, SLURM)",
            ),
            Paragraph(children=[Text(text="")]),
            _p(("Graduate Research Assistant", ["bold"]),
               " — University of Somewhere, Sep 2019–Sep 2023"),
            _items(
                "Derived analytic expressions for edge-state "
                "transport in periodically driven honeycomb lattices",
                "Implemented tight-binding simulations in Julia, "
                "achieving 10× speedup over legacy Fortran code",
                "Presented at 5 international conferences (2 invited talks)",
            ),

            Section(level=1, children=[Text(text="Selected publications")]),
            _ord_items(
                "J. A. Researcher, M. Topologist, \"Floquet edge modes "
                "in dissipative honeycomb lattices,\" Phys. Rev. Lett. "
                "132, 076401 (2024).",
                "J. A. Researcher, K. Collaborator, \"Raman signatures "
                "of twist-angle disorder in graphene moiré "
                "superlattices,\" Nano Lett. 21, 4532–4539 (2021).",
                "J. A. Researcher, \"Topological invariants of "
                "periodically driven systems: a pedagogical review,\" "
                "J. Phys. A: Math. Theor. 55, 123001 (2022).",
            ),

            Section(level=1, children=[Text(text="Teaching")]),
            _items(
                "Demonstrator, Quantum Mechanics II (3rd year), "
                "2020–2023",
                "Tutorial leader, Mathematical Methods (2nd year), "
                "2021–2022",
                "Lecturer, Summer school on topological matter, "
                "University of Elsewhere, Jul 2024",
            ),

            Section(level=1, children=[Text(text="Skills")]),
            Table(
                rows=[
                    ["Category",      "Details"],
                    ["Programming",   "Python, Julia, Fortran, C, Bash"],
                    ["Scientific",    "NumPy, SciPy, QuTiP, Kwant, "
                                      "Matplotlib, LaTeX"],
                    ["HPC",           "SLURM, MPI, OpenMP, GPU (CUDA)"],
                    ["Languages",     "English (native), French (fluent), "
                                      "German (intermediate)"],
                ],
                caption="",
                alignment="ll",
            ),

            Section(level=1, children=[Text(text="Awards and grants")]),
            _items(
                "EPSRC Postdoctoral Fellowship, 2024–2027 (£350 k)",
                "Best Poster Prize, Condensed Matter Physics "
                "conference, 2022",
                "Imperial College President's PhD Scholarship, 2019",
                "Dean's List, Department of Physics, 2016–2019",
            ),

            Section(level=1, children=[Text(text="Professional service")]),
            _items(
                "Referee: Phys. Rev. Lett., Phys. Rev. B, "
                "New J. Phys.",
                "Organiser: weekly condensed-matter seminar series, "
                "University of Somewhere, 2024–present",
                "Outreach: annual public lecture on quantum materials, "
                "Science Festival 2023 and 2024",
            ),
        ],
    )


# ------------------------------------------------------------ lab report

def lab_report() -> Document:
    """Undergraduate / graduate lab report with objective, theory,
    apparatus, procedure, data, analysis and conclusion."""
    return Document(
        meta=_meta(
            title="Lab report",
            author="A. Student",
            body_font_pt=12,
            line_spacing=1.15,
        ),
        children=[
            Title(children=[Text(text="Determination of the speed of "
                                      "sound in air by resonance-tube "
                                      "method")]),
            Author(children=[Text(text="A. Student — PHYS 2010 Lab, "
                                       "Group 4B")]),

            Section(level=1, children=[Text(text="Objective")]),
            _p(
                "To determine the speed of sound in air at room "
                "temperature by measuring the resonance lengths of a "
                "closed tube driven by tuning forks of known frequency, "
                "and to compare the result with the accepted value.",
            ),

            Section(level=1, children=[Text(text="Theory")]),
            _p(
                "A closed cylindrical tube supports standing waves "
                "when the air column length satisfies the resonance "
                "condition for odd multiples of a quarter wavelength. "
                "For the ", MathInline(latex="n"),
                "-th resonance (", MathInline(latex="n = 1, 3, 5, \\ldots"),
                ") the effective length is",
            ),
            MathBlock(
                latex=r"L_n + \epsilon = \frac{n \lambda}{4},"
                      r"\qquad n = 1, 3, 5, \ldots",
                numbered=True, label="eq:resonance",
            ),
            _p(
                "where ", MathInline(latex="L_n"),
                " is the measured length from the open end to the "
                "water surface, ", MathInline(latex="\\epsilon"),
                " is the end correction (approximately ",
                MathInline(latex="0.6 r"), " for a tube of radius ",
                MathInline(latex="r"), "), and ",
                MathInline(latex="\\lambda = v / f"),
                " is the wavelength corresponding to frequency ",
                MathInline(latex="f"), " and speed ",
                MathInline(latex="v"), ".",
            ),
            _p(
                "Eliminating the end correction between two "
                "successive resonances gives",
            ),
            MathBlock(
                latex=r"v = 2 f (L_3 - L_1).",
                numbered=True, label="eq:speed",
            ),

            Section(level=1, children=[Text(text="Apparatus")]),
            _items(
                "Glass resonance tube (length 100 cm, inner diameter "
                "3.4 cm) with adjustable water reservoir",
                "Tuning forks: 256 Hz, 440 Hz, 512 Hz (calibrated "
                "±0.5 Hz)",
                "Metre ruler (±0.5 mm) and vernier caliper (±0.02 mm)",
                "Digital thermometer (±0.1 °C)",
                "Rubber mallet for striking the tuning forks",
            ),

            Section(level=1, children=[Text(text="Procedure")]),
            _ord_items(
                "Record ambient temperature and atmospheric pressure.",
                "Strike the 256 Hz tuning fork and hold it at the "
                "open end of the tube.",
                "Slowly lower the water level until the first loud "
                "resonance is heard; record L₁.",
                "Continue lowering until the second resonance is "
                "heard; record L₃.",
                "Repeat three times and average.",
                "Repeat for the 440 Hz and 512 Hz forks.",
            ),

            Section(level=1, children=[Text(text="Data")]),
            _p("Room temperature: ",
               MathInline(latex="T = 21.3 \\pm 0.1"),
               " °C. Atmospheric pressure: 1013 hPa."),
            Table(
                rows=[
                    ["Fork (Hz)", "Trial", "L₁ (cm)", "L₃ (cm)"],
                    ["256",       "1",     "31.8",    "98.2"],
                    ["256",       "2",     "31.6",    "98.0"],
                    ["256",       "3",     "31.9",    "98.4"],
                    ["440",       "1",     "18.2",    "57.3"],
                    ["440",       "2",     "18.4",    "57.1"],
                    ["440",       "3",     "18.3",    "57.4"],
                    ["512",       "1",     "15.6",    "49.0"],
                    ["512",       "2",     "15.5",    "48.8"],
                    ["512",       "3",     "15.7",    "49.1"],
                ],
                caption="Measured resonance lengths for three tuning forks.",
                label="tab:data",
                alignment="llrr",
            ),

            Section(level=1, children=[Text(text="Analysis")]),
            _p(
                "Applying Equation ",
                CrossRef(label="eq:speed", kind="eqref"),
                " to the averaged lengths for the 256 Hz fork:",
            ),
            MathBlock(
                latex=(r"v = 2 \times 256 \times (0.982 - 0.318)"
                       r" = 340.2\;\text{m/s}."),
                numbered=False,
            ),
            _p("Repeating for all three forks:"),
            Table(
                rows=[
                    ["Fork (Hz)", "v (m/s)"],
                    ["256",       "340.2 ± 1.8"],
                    ["440",       "343.1 ± 2.1"],
                    ["512",       "342.0 ± 1.6"],
                ],
                caption="Speed of sound derived from each tuning fork.",
                label="tab:results",
                alignment="lr",
            ),
            _p(
                "The weighted mean is ",
                MathInline(latex="v = 341.6 \\pm 1.0"),
                " m/s. The accepted value at 21.3 °C is",
            ),
            MathBlock(
                latex=r"v_{\text{ref}} = 331.3 + 0.606 \times 21.3 "
                      r"= 344.2\;\text{m/s},",
                numbered=False,
            ),
            _p(
                "giving a percentage discrepancy of 0.8%, which is "
                "within the combined uncertainty.",
            ),

            Section(level=1, children=[Text(text="Discussion")]),
            _p(
                "The systematic under-estimate may be partly explained "
                "by the end correction: the simple formula ",
                MathInline(latex="\\epsilon \\approx 0.6 r"),
                " assumes an infinite baffle, whereas our open tube "
                "end radiates into free space. Additionally, the "
                "tuning forks may have drifted slightly from their "
                "nominal frequencies with age. A future experiment "
                "could use a frequency counter to verify the fork "
                "output directly.",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "The speed of sound in air was measured as ",
                MathInline(latex="341.6 \\pm 1.0"),
                " m/s at 21.3 °C, consistent with the expected value "
                "of 344.2 m/s within experimental uncertainty. The "
                "resonance-tube method provides a straightforward and "
                "reliable measurement of the speed of sound.",
            ),
        ],
    )


# --------------------------------------------------------- homework / problem set

def homework() -> Document:
    """Homework or problem-set template — numbered problems with
    solutions containing display math."""
    return Document(
        meta=_meta(
            title="Problem set",
            author="A. Student",
            body_font_pt=11,
            line_spacing=1.15,
            paragraph_indent=False,
        ),
        children=[
            Title(children=[Text(text="MATH 3120 — Problem Set 7")]),
            Author(children=[Text(text="A. Student — Due: 30 May 2026")]),

            # Problem 1
            Section(level=1, children=[Text(text="Problem 1")]),
            _p(("Statement.", ["bold"]),
               " Let ", MathInline(latex="V"),
               " be a finite-dimensional inner-product space over ",
               MathInline(latex="\\mathbb{R}"),
               " and let ", MathInline(latex="T: V \\to V"),
               " be a self-adjoint linear operator. Prove that all "
               "eigenvalues of ", MathInline(latex="T"),
               " are real."),

            Section(level=2, children=[Text(text="Solution")]),
            _p(
                "Let ", MathInline(latex="\\lambda"),
                " be an eigenvalue of ", MathInline(latex="T"),
                " with eigenvector ",
                MathInline(latex="v \\neq 0"), ". Then",
            ),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  \\lambda \\langle v, v \\rangle "
                    "&= \\langle \\lambda v, v \\rangle "
                    "= \\langle Tv, v \\rangle \\\\\n"
                    "  &= \\langle v, Tv \\rangle "
                    "= \\langle v, \\lambda v \\rangle "
                    "= \\bar{\\lambda} \\langle v, v \\rangle.\n"
                    "\\end{align}"
                ),
                numbered=True, label="eq:selfadj",
            ),
            _p(
                "Since ", MathInline(latex="v \\neq 0"),
                " we have ",
                MathInline(latex="\\langle v, v \\rangle > 0"),
                ", so dividing both sides gives ",
                MathInline(latex="\\lambda = \\bar{\\lambda}"),
                ", i.e. ", MathInline(latex="\\lambda \\in \\mathbb{R}"),
                ". ", MathInline(latex="\\square"),
            ),

            # Problem 2
            Section(level=1, children=[Text(text="Problem 2")]),
            _p(("Statement.", ["bold"]),
               " Evaluate the integral"),
            MathBlock(
                latex=r"I = \int_0^{\infty} \frac{\sin x}{x} \, dx.",
                numbered=True, label="eq:sinc",
            ),

            Section(level=2, children=[Text(text="Solution")]),
            _p(
                "Consider the Laplace-transform trick. Define",
            ),
            MathBlock(
                latex=r"F(s) = \int_0^{\infty} \frac{e^{-sx} \sin x}{x}"
                      r"\, dx, \qquad s > 0.",
                numbered=True, label="eq:laplace",
            ),
            _p("Differentiating under the integral sign:"),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  F'(s) &= -\\int_0^{\\infty} e^{-sx} \\sin x \\, dx "
                    "= -\\frac{1}{s^2 + 1}.\n"
                    "\\end{align}"
                ),
                numbered=True,
            ),
            _p(
                "Integrating: ",
                MathInline(latex="F(s) = C - \\arctan s"),
                ". As ", MathInline(latex="s \\to \\infty"),
                ", ", MathInline(latex="F(s) \\to 0"),
                ", so ", MathInline(latex="C = \\pi/2"), ". Therefore",
            ),
            MathBlock(
                latex=r"I = \lim_{s \to 0^+} F(s) = \frac{\pi}{2} - 0 "
                      r"= \frac{\pi}{2}.",
                numbered=True, label="eq:sinc-result",
            ),

            # Problem 3
            Section(level=1, children=[Text(text="Problem 3")]),
            _p(("Statement.", ["bold"]),
               " Find all groups of order 6, up to isomorphism."),

            Section(level=2, children=[Text(text="Solution")]),
            _p(
                "Let ", MathInline(latex="G"),
                " be a group with ", MathInline(latex="|G| = 6 = 2 \\cdot 3"),
                ". By Cauchy's theorem, ", MathInline(latex="G"),
                " contains elements of order 2 and 3.",
            ),
            _p(
                ("Case 1: ", ["bold"]), MathInline(latex="G"),
                (" is abelian.", ["italic"]),
                " Then by the fundamental theorem of finitely generated "
                "abelian groups, ",
                MathInline(latex="G \\cong \\mathbb{Z}/6\\mathbb{Z}"),
                ", which is cyclic.",
            ),
            _p(
                ("Case 2: ", ["bold"]), MathInline(latex="G"),
                (" is non-abelian.", ["italic"]),
                " By Sylow's theorem, the number of Sylow 3-subgroups "
                "divides 2 and is ", MathInline(latex="\\equiv 1 \\pmod{3}"),
                ", so there is exactly one Sylow 3-subgroup ",
                MathInline(latex="N \\cong \\mathbb{Z}/3\\mathbb{Z}"),
                ", which is therefore normal. Let ",
                MathInline(latex="t"), " have order 2. Then ",
                MathInline(latex="G = N \\rtimes \\langle t \\rangle"),
                " where ", MathInline(latex="t"),
                " acts on ", MathInline(latex="N"),
                " by inversion. This is precisely ",
                MathInline(latex="S_3"), ", the symmetric group on "
                "three letters.",
            ),
            _p(
                "Therefore the only groups of order 6 are ",
                MathInline(latex="\\mathbb{Z}/6\\mathbb{Z}"),
                " and ", MathInline(latex="S_3"),
                ". ", MathInline(latex="\\square"),
            ),

            # Problem 4
            Section(level=1, children=[Text(text="Problem 4")]),
            _p(("Statement.", ["bold"]),
               " Let ", MathInline(latex="f: [0,1] \\to \\mathbb{R}"),
               " be continuous and suppose ",
               MathInline(latex="\\int_0^1 f(x) x^n \\, dx = 0"),
               " for all ", MathInline(latex="n \\geq 0"),
               ". Show that ", MathInline(latex="f \\equiv 0"), "."),

            Section(level=2, children=[Text(text="Solution")]),
            _p(
                "By the Weierstrass approximation theorem, for every ",
                MathInline(latex="\\epsilon > 0"),
                " there exists a polynomial ",
                MathInline(latex="p"), " such that ",
                MathInline(latex="\\|f - p\\|_\\infty < \\epsilon"),
                ". By linearity of the integral and the hypothesis, ",
                MathInline(latex="\\int_0^1 f(x) p(x) \\, dx = 0"),
                ". Therefore",
            ),
            MathBlock(
                latex=(
                    "\\begin{align}\n"
                    "  \\int_0^1 f(x)^2 \\, dx "
                    "&= \\int_0^1 f(x)(f(x) - p(x)) \\, dx \\\\\n"
                    "  &\\leq \\|f\\|_\\infty \\cdot \\epsilon.\n"
                    "\\end{align}"
                ),
                numbered=True,
            ),
            _p(
                "Since ", MathInline(latex="\\epsilon"),
                " is arbitrary, ",
                MathInline(latex="\\int_0^1 f(x)^2 \\, dx = 0"),
                ". Because ", MathInline(latex="f"),
                " is continuous and non-negative under the square, "
                "this forces ",
                MathInline(latex="f \\equiv 0"),
                ". ", MathInline(latex="\\square"),
            ),
        ],
    )


# --------------------------------------------------------- technical memo

def memo() -> Document:
    """Short technical memo — one-page internal document with wide
    margins and no abstract."""
    return Document(
        meta=_meta(
            title="", author="",
            body_font_pt=11,
            margin_left_cm=3.0, margin_right_cm=3.0,
            margin_top_cm=2.5, margin_bottom_cm=2.5,
            paragraph_indent=False,
        ),
        children=[
            # Header block
            Paragraph(children=[
                Text(text="TECHNICAL MEMO", marks=["bold"]),
            ], alignment="center"),
            Paragraph(children=[Text(text="")]),
            Table(
                rows=[
                    ["To:",      "Engineering team"],
                    ["From:",    "J. Author, Systems lead"],
                    ["Date:",    "20 May 2026"],
                    ["Subject:", "Migration from PostgreSQL 14 to 16"],
                ],
                alignment="ll",
            ),

            RawLatex(text="\\noindent\\rule{\\textwidth}{0.4pt}"),
            Paragraph(children=[Text(text="")]),

            Section(level=1, children=[Text(text="Summary")]),
            _p(
                "We propose migrating the production database from "
                "PostgreSQL 14 to PostgreSQL 16 during the next "
                "maintenance window (7–8 June 2026). The upgrade "
                "brings logical-replication improvements that unblock "
                "the event-sourcing work planned for Q3, and addresses "
                "three CVEs in the current version.",
            ),

            Section(level=1, children=[Text(text="Background")]),
            _p(
                "PostgreSQL 14 reached community end-of-life in "
                "November 2025. While our managed-service provider "
                "still ships security patches, several extensions we "
                "depend on (pg_partman, pgvector) have dropped CI "
                "testing against version 14. Staying on it increases "
                "our surface area for compatibility regressions.",
            ),

            Section(level=1, children=[Text(text="Proposal")]),
            _ord_items(
                "Spin up a PG 16 replica using pg_upgrade on the "
                "staging cluster this week.",
                "Run the full regression-test suite against staging "
                "for two weeks (24 May – 6 June).",
                "Execute the cutover on the production primary during "
                "the 7 June maintenance window using pg_basebackup.",
                "Keep the PG 14 standby alive for 48 hours as a "
                "rollback target.",
                "Decommission the old cluster once sign-off is "
                "received from the on-call rotation.",
            ),

            Section(level=1, children=[Text(text="Risks")]),
            Table(
                rows=[
                    ["Risk",                        "Likelihood", "Mitigation"],
                    ["Extension incompatibility",   "Low",
                     "Pre-tested in staging"],
                    ["Replication lag during cutover", "Medium",
                     "Schedule during low-traffic window"],
                    ["Rollback needed after 48 h",  "Very low",
                     "WAL archiving to S3"],
                ],
                caption="Risk assessment for the migration.",
                label="tab:risks",
                alignment="llp{6cm}",
            ),

            Section(level=1, children=[Text(text="Decision requested")]),
            _p(
                "Please confirm by 28 May whether the 7 June window "
                "is acceptable, or suggest an alternative date. If "
                "there are no objections by that date we will proceed "
                "as described above.",
            ),
        ],
    )


# ---------------------------------------------------- literature review

def literature_review() -> Document:
    """Citation-heavy literature review — demonstrates extensive use of
    citations, thematic sections, and critical synthesis."""
    return Document(
        meta=_meta(
            title="Literature review",
            author="A. Researcher",
            body_font_pt=12,
            line_spacing=1.5,
            packages=DEFAULT_PACKAGES + ["natbib", "hyperref"],
        ),
        children=[
            Title(children=[Text(text="Machine learning for materials "
                                      "discovery: a literature review")]),
            Author(children=[Text(text="A. Researcher — Department of "
                                       "Materials Science")]),
            Abstract(children=[Text(text=
                "This review surveys the application of machine-learning "
                "techniques to the discovery and design of novel "
                "materials, covering work published between 2018 and "
                "2026. We organise the literature into three themes: "
                "property prediction, generative design, and active "
                "learning for experimental guidance. For each theme "
                "we identify the dominant methods, the benchmark "
                "datasets, and the principal open challenges.")]),
            Keywords(children=[Text(text="machine learning · materials "
                "science · property prediction · generative models · "
                "active learning")]),

            Section(level=1, children=[Text(text="Introduction")]),
            _p(
                "The intersection of machine learning and materials "
                "science has grown rapidly over the past decade. Early "
                "work focused on supervised learning for property "
                "prediction ",
                Citation(keys=["ward2016", "xie2018"], style="citep"),
                ", but the field has since broadened to encompass "
                "generative models that propose new compositions ",
                Citation(keys=["noh2019", "dan2020"], style="citep"),
                " and active-learning frameworks that guide expensive "
                "experiments toward the most informative measurements ",
                Citation(keys=["lookman2019"], style="citep"),
                ".",
            ),
            _p(
                "The goal of this review is to provide a structured "
                "overview of these three threads and to identify gaps "
                "where future research is most needed. We restrict "
                "ourselves to inorganic crystalline materials; organic "
                "and polymer systems are covered elsewhere ",
                Citation(keys=["butler2018"], style="citep"), ".",
            ),

            Section(level=1, children=[Text(text="Property prediction")]),
            _p(
                "The most mature sub-field uses supervised learning "
                "to map material descriptors to target properties. "
                "Early models relied on hand-crafted feature vectors ",
                Citation(keys=["ward2016"], style="citep"),
                ", whereas more recent approaches learn "
                "representations directly from crystal graphs ",
                Citation(keys=["xie2018", "chen2019"], style="citep"),
                ".",
            ),
            _p(
                "Graph neural networks (GNNs) have emerged as the "
                "dominant architecture. ",
                Citation(keys=["xie2018"], style="citet"),
                " introduced the Crystal Graph Convolutional Neural "
                "Network (CGCNN), achieving mean absolute errors below "
                "0.05 eV/atom for formation energy on the Materials "
                "Project dataset. Subsequent work by ",
                Citation(keys=["chen2019"], style="citet"),
                " extended this with multi-edge interactions, reaching "
                "state-of-the-art accuracy on 7 of 10 benchmark tasks.",
            ),
            _p(
                "Despite these advances, two limitations persist. "
                "First, most models are trained on DFT-computed "
                "properties, which themselves carry systematic errors "
                "relative to experiment. Second, extrapolation to "
                "chemistries outside the training distribution remains "
                "unreliable ",
                Citation(keys=["bartel2020"], style="citep"), ".",
            ),

            Section(level=1, children=[Text(text="Generative design")]),
            _p(
                "Generative models aim to propose novel materials "
                "that optimise one or more target properties. "
                "Variational autoencoders (VAEs) were among the first "
                "architectures applied ",
                Citation(keys=["noh2019"], style="citep"),
                ", followed by generative adversarial networks ",
                Citation(keys=["dan2020"], style="citep"),
                " and, more recently, diffusion models ",
                Citation(keys=["xie2022"], style="citep"), ".",
            ),
            _p(
                "A central challenge is ensuring that generated "
                "structures are synthesisable. ",
                Citation(keys=["dan2020"], style="citet"),
                " addressed this by conditioning the generator on "
                "stability criteria from the convex hull. ",
                Citation(keys=["xie2022"], style="citet"),
                " took a different approach, training a denoising "
                "diffusion model on relaxed DFT structures so that "
                "the generated samples are already near local energy "
                "minima.",
            ),

            Section(level=1, children=[Text(text="Active learning")]),
            _p(
                "Active learning closes the loop between prediction "
                "and experiment by selecting the next measurement to "
                "maximise information gain. ",
                Citation(keys=["lookman2019"], style="citet"),
                " demonstrated this for shape-memory alloys, reducing "
                "the number of experiments needed to find a target "
                "composition by a factor of three compared to grid "
                "search.",
            ),
            _p(
                "Bayesian optimisation is the dominant framework, "
                "typically using a Gaussian process surrogate ",
                Citation(keys=["frazier2018"], style="citep"),
                ". Recent work has explored multi-fidelity "
                "acquisition functions that mix cheap DFT evaluations "
                "with expensive experimental measurements, further "
                "reducing the total cost of exploration ",
                Citation(keys=["palizhati2022"], style="citep"),
                ".",
            ),

            Section(level=1, children=[Text(text="Open challenges")]),
            _items(
                "Data scarcity for experimental (as opposed to "
                "computed) properties remains a bottleneck.",
                "Uncertainty quantification in deep-learning models "
                "is still rudimentary compared to Gaussian processes.",
                "Multi-objective optimisation — balancing stability, "
                "cost, toxicity and performance — is under-explored.",
                "Reproducibility: few papers release both code and "
                "data sufficient to replicate results end-to-end.",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "Machine learning has already accelerated several "
                "stages of the materials-discovery pipeline, from "
                "screening candidates to guiding synthesis. The most "
                "impactful next step is likely the integration of "
                "these tools into closed-loop autonomous laboratories "
                "where data generation, model updating and decision-"
                "making happen without human intervention.",
            ),
        ],
    )


# ------------------------------------------------------- research proposal

def research_proposal() -> Document:
    """Research / grant proposal — objectives, background, methodology,
    timeline, budget overview."""
    return Document(
        meta=_meta(
            title="Research proposal",
            author="A. Researcher",
            body_font_pt=12,
            line_spacing=1.15,
            packages=DEFAULT_PACKAGES + ["natbib", "hyperref"],
        ),
        children=[
            Title(children=[Text(text="Proposal: Quantum error correction "
                                      "in superconducting circuits")]),
            Author(children=[Text(text="Dr A. Researcher — Department "
                                       "of Quantum Engineering")]),

            Section(level=1, children=[Text(text="Project summary")]),
            _p(
                "This proposal requests funding for a three-year "
                "programme to develop and experimentally validate a "
                "new family of quantum error-correcting codes tailored "
                "to the noise characteristics of transmon-based "
                "superconducting circuits. The expected outcomes are "
                "(i) a code family with provably lower overhead than "
                "the surface code for biased noise, (ii) a prototype "
                "implementation on a 20-qubit device, and (iii) "
                "open-source software for simulating and benchmarking "
                "the codes.",
            ),

            Section(level=1, children=[Text(text="Background and motivation")]),
            _p(
                "Quantum error correction (QEC) is widely regarded as "
                "essential for practical quantum computing ",
                Citation(keys=["terhal2015", "campbell2017"], style="citep"),
                ". The surface code ",
                Citation(keys=["fowler2012"], style="citep"),
                " is the current front-runner because of its high "
                "threshold and local stabiliser checks. However, its "
                "overhead — roughly ",
                MathInline(latex="O(d^2)"),
                " physical qubits per logical qubit for code distance ",
                MathInline(latex="d"),
                " — remains prohibitive for near-term hardware.",
            ),
            _p(
                "Recent theoretical work has shown that when the "
                "physical noise is biased (i.e. phase-flip errors "
                "dominate bit-flip errors, as is typical for transmons "
                "at long coherence times), tailored codes can achieve "
                "the same logical error rate with significantly fewer "
                "qubits ",
                Citation(keys=["tuckett2020", "dua2024"], style="citep"),
                ". This project aims to move those theoretical gains "
                "into the laboratory.",
            ),

            Section(level=1, children=[Text(text="Objectives")]),
            _ord_items(
                "Design a family of bias-tailored stabiliser codes "
                "optimised for the noise profile of state-of-the-art "
                "transmon qubits.",
                "Develop an open-source decoder that runs within the "
                "real-time feedback latency budget of current "
                "cryogenic electronics (< 1 μs per syndrome round).",
                "Implement the best candidate code on a 20-qubit "
                "superconducting device and measure the logical error "
                "rate at distances 3, 5 and 7.",
                "Benchmark the code against the surface code under "
                "identical hardware conditions.",
            ),

            Section(level=1, children=[Text(text="Methodology")]),
            Section(level=2, children=[Text(text="Code construction")]),
            _p(
                "We will use a computer search over the space of CSS "
                "codes with biased distance, parameterised by the "
                "physical noise bias ratio ",
                MathInline(latex="\\eta = p_Z / p_X"),
                ". The search objective is to minimise the number of "
                "physical qubits ",
                MathInline(latex="n"),
                " subject to a target logical error rate:",
            ),
            MathBlock(
                latex=r"p_L \leq p_{\text{phys}}^{\lfloor d/2 \rfloor}"
                      r"\binom{d}{\lfloor d/2 \rfloor}",
                numbered=True, label="eq:threshold",
            ),

            Section(level=2, children=[Text(text="Decoder design")]),
            _p(
                "We will adapt the Union-Find decoder ",
                Citation(keys=["delfosse2021"], style="citep"),
                " to exploit the noise bias. The key modification is "
                "a weighted growth rule that expands clusters "
                "anisotropically in the Tanner graph, reducing the "
                "average number of growth steps and thus the wall-clock "
                "decoding time.",
            ),

            Section(level=2, children=[Text(text="Experimental validation")]),
            _p(
                "The experimental work will be carried out on the "
                "20-qubit device in our laboratory. Each code instance "
                "will be run for ", MathInline(latex="10^6"),
                " syndrome rounds, and the logical error rate will be "
                "extracted by majority-vote decoding of repeated "
                "stabiliser measurements.",
            ),

            Section(level=1, children=[Text(text="Timeline")]),
            Table(
                rows=[
                    ["Period",       "Milestone"],
                    ["Months 1–6",   "Code family enumeration and "
                                     "simulation"],
                    ["Months 7–12",  "Decoder implementation and "
                                     "benchmarking (simulation)"],
                    ["Months 13–18", "Device calibration and preliminary "
                                     "experiments at distance 3"],
                    ["Months 19–30", "Full experimental campaign at "
                                     "distances 3, 5 and 7"],
                    ["Months 31–36", "Analysis, publication and software "
                                     "release"],
                ],
                caption="Proposed timeline.",
                label="tab:timeline",
                alignment="lp{10cm}",
            ),

            Section(level=1, children=[Text(text="Budget overview")]),
            Table(
                rows=[
                    ["Item",                     "Cost (£k)"],
                    ["Postdoc (36 months)",       "180"],
                    ["PhD student (36 months)",   "90"],
                    ["Cryostat maintenance",      "40"],
                    ["Consumables and travel",    "25"],
                    ["Total",                     "335"],
                ],
                caption="Budget summary.",
                label="tab:budget",
                alignment="lr",
            ),

            Section(level=1, children=[Text(text="Expected impact")]),
            _p(
                "If successful, this project will demonstrate that "
                "bias-tailored codes offer a practical route to "
                "lower-overhead quantum error correction on real "
                "hardware. The open-source decoder and simulation "
                "tools will be of immediate use to other experimental "
                "groups, and the experimental data will provide a "
                "benchmark for future code designs.",
            ),
        ],
    )


# ------------------------------------------------------- book chapter

def book_chapter() -> Document:
    """Book chapter using the report class — longer-form prose with
    sub-sections, figures, and footnotes."""
    return Document(
        meta=_meta(
            documentclass="report",
            title="Book chapter",
            author="A. Author",
            body_font_pt=12,
            line_spacing=1.5,
            margin_left_cm=3.0, margin_right_cm=3.0,
            packages=DEFAULT_PACKAGES + ["hyperref"],
        ),
        children=[
            Title(children=[Text(text="The discovery of the neutron")]),
            Author(children=[Text(text="A. Author — in ",
                                       marks=["italic"]),
                             Text(text="Milestones in Nuclear Physics",
                                  marks=["italic"]),
                             Text(text=", ed. B. Editor")]),

            Section(level=1, children=[Text(text="The discovery of the "
                                                  "neutron")]),

            Section(level=2, children=[Text(text="The puzzle of the "
                                                  "nucleus")]),
            _p(
                "By 1930, the atomic nucleus was known to be much "
                "heavier than its charge alone could explain. The "
                "prevailing model posited a nucleus of protons and "
                "electrons, but this created immediate difficulties. "
                "The spin-statistics problem — nitrogen-14, with 14 "
                "protons and 7 electrons, should obey Fermi–Dirac "
                "statistics yet was observed to obey Bose–Einstein "
                "statistics — was especially troubling",
                Footnote(children=[Text(text=
                    "Ehrenfest and Oppenheimer raised this objection "
                    "as early as 1931; see their paper in Phys. Rev. "
                    "37, 333.")]),
                ".",
            ),
            _p(
                "The nuclear-electron model also struggled to explain "
                "the binding energy. Electrons confined to a region "
                "the size of a nucleus (", MathInline(latex="\\sim 10^{-15}"),
                " m) would have kinetic energies of order ",
                MathInline(latex="\\sim 100"), " MeV by the "
                "uncertainty principle, far exceeding the observed "
                "binding energies of a few MeV per nucleon.",
            ),

            Section(level=2, children=[Text(text="Bothe and Becker's "
                                                  "radiation")]),
            _p(
                "In 1930, Walther Bothe and Herbert Becker bombarded "
                "beryllium with alpha particles from a polonium "
                "source and observed a penetrating radiation that they "
                "interpreted as high-energy gamma rays. The radiation "
                "was unusually penetrating — far more so than any "
                "gamma ray known at the time — but without a charge "
                "measurement there was no way to identify the "
                "particles directly.",
            ),

            Section(level=2, children=[Text(text="The Joliot-Curie "
                                                  "experiment")]),
            _p(
                "In January 1932, Irène Joliot-Curie and Frédéric "
                "Joliot repeated the experiment and placed a paraffin "
                "target in the path of the radiation. They observed "
                "that the paraffin emitted protons with energies up "
                "to about 5.7 MeV. They explained the observation as "
                "Compton scattering of gamma rays off hydrogen nuclei, "
                "but the kinematics required a gamma-ray energy of "
                "roughly 55 MeV — far higher than any known nuclear "
                "transition.",
            ),

            Section(level=2, children=[Text(text="Chadwick's "
                                                  "identification")]),
            _p(
                "James Chadwick, working at the Cavendish Laboratory "
                "in Cambridge, realised within days that the "
                "Joliot-Curie explanation was untenable. He repeated "
                "the experiment with several target materials "
                "(hydrogen, helium, nitrogen) and measured the recoil "
                "energies. The data were consistent with a neutral "
                "particle of mass close to that of the proton.",
            ),
            _p(
                "Chadwick published his results on 27 February 1932 "
                "in a short letter to ", ("Nature", ["italic"]),
                Footnote(children=[Text(text=
                    "J. Chadwick, \"Possible existence of a neutron,\""
                    " Nature 129, 312 (1932).")]),
                ". A more detailed paper followed in June in the "
                "Proceedings of the Royal Society. The neutral "
                "particle, which Chadwick named the neutron, resolved "
                "both the spin-statistics problem and the binding-"
                "energy puzzle in one stroke.",
            ),

            Section(level=2, children=[Text(text="The kinematics")]),
            _p(
                "Consider the beryllium reaction:",
            ),
            MathBlock(
                latex=r"{}^9\text{Be} + {}^4\text{He} \to "
                      r"{}^{12}\text{C} + n.",
                numbered=True, label="eq:reaction",
            ),
            _p(
                "Conservation of energy and momentum, combined with "
                "the measured recoil energies, allowed Chadwick to "
                "determine the neutron mass. His original estimate was",
            ),
            MathBlock(
                latex=r"m_n = 1.0067 \pm 0.0005 \;\text{u},",
                numbered=False,
            ),
            _p(
                "remarkably close to the modern value of ",
                MathInline(latex="1.008665"), " u.",
            ),

            Section(level=2, children=[Text(text="Aftermath")]),
            _p(
                "The discovery of the neutron opened the door to "
                "nuclear fission (realised within seven years), to "
                "the proton–neutron model of the nucleus proposed "
                "independently by Heisenberg and Ivanenko, and "
                "ultimately to the nuclear shell model of Mayer and "
                "Jensen. Chadwick was awarded the Nobel Prize in "
                "Physics in 1935 — just three years after his "
                "discovery, an unusually short interval that reflects "
                "the immediate impact of the work.",
            ),
            _p(
                "It is worth noting how close others came. Bothe and "
                "Becker had the radiation; the Joliot-Curies had the "
                "proton recoils. What Chadwick brought was the "
                "willingness to abandon the gamma-ray interpretation "
                "and follow the kinematics wherever they led — a "
                "textbook example of how theoretical prejudice can "
                "delay experimental discovery.",
            ),
        ],
    )


# ------------------------------------------------------ meeting minutes

def meeting_minutes() -> Document:
    """Meeting minutes template — attendees, agenda, action items."""
    return Document(
        meta=_meta(
            title="", author="",
            body_font_pt=11,
            margin_left_cm=2.5, margin_right_cm=2.5,
            paragraph_indent=False,
        ),
        children=[
            Title(children=[Text(text="Project Phoenix — Sprint review "
                                      "meeting")]),
            Author(children=[Text(text="20 May 2026, 14:00–15:00 (Teams)")]),

            Section(level=1, children=[Text(text="Attendees")]),
            _items(
                "J. Manager (chair)",
                "A. Developer",
                "B. Developer",
                "C. Designer",
                "D. QA Engineer",
                "E. Product Owner (remote)",
            ),
            _p(("Apologies:", ["bold"]), " F. DevOps (on leave)."),

            Section(level=1, children=[Text(text="Agenda")]),
            _ord_items(
                "Sprint 14 demo and retrospective",
                "Sprint 15 planning",
                "Infrastructure update",
                "Any other business",
            ),

            Section(level=1, children=[Text(text="Sprint 14 demo")]),
            _p(
                "A. Developer demonstrated the new bulk-import "
                "endpoint. The endpoint processes CSV uploads "
                "asynchronously and returns a job ID for polling. "
                "E. Product Owner confirmed the feature matches the "
                "acceptance criteria in ticket PX-312.",
            ),
            _p(
                "C. Designer walked through the updated settings "
                "page. Two minor spacing issues were noted and logged "
                "as PX-345 and PX-346.",
            ),

            Section(level=1, children=[Text(text="Retrospective")]),
            _p(("What went well:", ["bold"])),
            _items(
                "Pair programming on the import endpoint caught two "
                "edge cases before they reached QA.",
                "Daily stand-ups stayed under 10 minutes every day.",
                "The new staging environment was stable for the full "
                "sprint.",
            ),
            _p(("What could improve:", ["bold"])),
            _items(
                "Flaky integration tests blocked the pipeline three "
                "times — needs investigation.",
                "Late requirement change on PX-330 caused scope creep.",
            ),

            Section(level=1, children=[Text(text="Sprint 15 planning")]),
            _p("The following stories were committed for Sprint 15:"),
            Table(
                rows=[
                    ["Ticket",  "Title",                    "Owner",
                     "Points"],
                    ["PX-350",  "Role-based access control", "A. Dev",
                     "8"],
                    ["PX-351",  "Password reset flow",       "B. Dev",
                     "5"],
                    ["PX-345",  "Settings page spacing fix", "C. Des",
                     "2"],
                    ["PX-346",  "Settings page icon alignment", "C. Des",
                     "1"],
                    ["PX-352",  "Flaky test investigation",  "D. QA",
                     "3"],
                ],
                caption="Sprint 15 backlog.",
                label="tab:sprint15",
                alignment="llllr",
            ),

            Section(level=1, children=[Text(text="Infrastructure update")]),
            _p(
                "In F. DevOps' absence, J. Manager relayed the "
                "update: the Kubernetes cluster will be upgraded to "
                "v1.30 on 1 June. No application changes are "
                "expected, but all teams should verify their Helm "
                "charts against the new API deprecations.",
            ),

            Section(level=1, children=[Text(text="Action items")]),
            Table(
                rows=[
                    ["#", "Action",                           "Owner",
                     "Due"],
                    ["1", "Investigate flaky tests",          "D. QA",
                     "23 May"],
                    ["2", "Review Helm charts for k8s 1.30",  "F. DevOps",
                     "28 May"],
                    ["3", "Send password-reset wireframes",   "C. Des",
                     "22 May"],
                    ["4", "Schedule PX-330 scope review",     "E. PO",
                     "21 May"],
                ],
                caption="Action items from this meeting.",
                label="tab:actions",
                alignment="rlll",
            ),

            Section(level=1, children=[Text(text="Next meeting")]),
            _p("Sprint 15 review: 3 June 2026, 14:00, same Teams link."),
        ],
    )


# ---------------------------------------------------- lecture notes

def lecture_notes() -> Document:
    """Lecture notes / course notes — definitions, theorems, proofs,
    and examples in a structured format."""
    return Document(
        meta=_meta(
            title="Lecture notes",
            author="Prof. A. Lecturer",
            body_font_pt=11,
            line_spacing=1.15,
            packages=DEFAULT_PACKAGES + ["hyperref"],
            preamble_extras=(
                "\\newtheorem{theorem}{Theorem}[section]\n"
                "\\newtheorem{definition}[theorem]{Definition}\n"
                "\\newtheorem{lemma}[theorem]{Lemma}\n"
                "\\newtheorem{corollary}[theorem]{Corollary}\n"
                "\\newtheorem{example}[theorem]{Example}\n"
                "\\newtheorem{remark}[theorem]{Remark}"
            ),
        ),
        children=[
            Title(children=[Text(text="MATH 4200 — Metric Spaces")]),
            Author(children=[Text(text="Prof. A. Lecturer — Lecture 12: "
                                       "Compactness")]),

            Section(level=1, children=[Text(text="Compactness")]),
            _p(
                "Compactness is one of the central concepts in "
                "analysis and topology. Informally, a compact set "
                "behaves like a finite set in many important respects: "
                "continuous functions attain their extrema on compact "
                "sets, sequences have convergent subsequences, and "
                "open covers can always be reduced to finite "
                "sub-covers.",
            ),

            Section(level=2, children=[Text(text="Definitions")]),
            RawLatex(text=(
                "\\begin{definition}[Open cover]\n"
                "Let $(X, d)$ be a metric space and $K \\subseteq X$. "
                "An \\emph{open cover} of $K$ is a collection "
                "$\\{U_\\alpha\\}_{\\alpha \\in A}$ of open sets such that "
                "$K \\subseteq \\bigcup_{\\alpha \\in A} U_\\alpha$.\n"
                "\\end{definition}"
            )),
            RawLatex(text=(
                "\\begin{definition}[Compact set]\n"
                "A subset $K$ of a metric space $(X, d)$ is "
                "\\emph{compact} if every open cover of $K$ has a "
                "finite sub-cover.\n"
                "\\end{definition}"
            )),
            _p(
                "Note that compactness is an intrinsic property: it "
                "does not depend on the ambient space ",
                MathInline(latex="X"),
                ", only on the induced metric on ",
                MathInline(latex="K"), ".",
            ),

            Section(level=2, children=[Text(text="First properties")]),
            RawLatex(text=(
                "\\begin{theorem}\n"
                "Every compact subset of a metric space is closed and "
                "bounded.\n"
                "\\end{theorem}"
            )),
            RawLatex(text=(
                "\\begin{proof}\n"
                "Let $K$ be compact in $(X, d)$. Fix $p \\in X$ and "
                "consider the open cover $\\{B(p, n)\\}_{n=1}^\\infty$ "
                "of $K$. By compactness there is a finite sub-cover, "
                "so $K \\subseteq B(p, N)$ for some $N$; hence $K$ is "
                "bounded.\n\n"
                "To show $K$ is closed, let $q \\notin K$. For each "
                "$x \\in K$, let $r_x = d(x, q)/2$ and consider the "
                "open cover $\\{B(x, r_x)\\}_{x \\in K}$. Extract a "
                "finite sub-cover $B(x_1, r_1), \\ldots, B(x_n, r_n)$. "
                "Then $B(q, \\min_i r_i) \\cap K = \\emptyset$, so $q$ "
                "is an interior point of $X \\setminus K$. Since $q$ "
                "was arbitrary, $X \\setminus K$ is open, so $K$ is "
                "closed.\n"
                "\\end{proof}"
            )),
            _p(
                ("Remark.", ["bold"]),
                " The converse is false in general metric spaces. "
                "The closed unit ball in an infinite-dimensional "
                "Banach space is closed and bounded but not compact.",
            ),

            Section(level=2, children=[Text(text="The Heine–Borel theorem")]),
            RawLatex(text=(
                "\\begin{theorem}[Heine--Borel]\n"
                "\\label{thm:heine-borel}\n"
                "A subset of $\\mathbb{R}^n$ is compact if and only if "
                "it is closed and bounded.\n"
                "\\end{theorem}"
            )),
            _p(
                "We will not prove the full theorem here (see the "
                "textbook, Chapter 4, §3). Instead we prove the key "
                "lemma from which the result follows.",
            ),
            RawLatex(text=(
                "\\begin{lemma}[Bolzano--Weierstrass]\n"
                "Every bounded sequence in $\\mathbb{R}^n$ has a "
                "convergent subsequence.\n"
                "\\end{lemma}"
            )),
            RawLatex(text=(
                "\\begin{proof}\n"
                "We argue by repeated bisection. Given a bounded "
                "sequence $(x_k)$ in $\\mathbb{R}$, it lies in some "
                "interval $[a, b]$. At least one of $[a, (a+b)/2]$ "
                "or $[(a+b)/2, b]$ contains infinitely many terms; "
                "pick that half-interval and a term from it. Repeat. "
                "This produces a nested sequence of closed intervals "
                "whose lengths tend to zero, and by the nested-"
                "intervals theorem their intersection is a single "
                "point $\\ell$. The subsequence of terms chosen at "
                "each step converges to $\\ell$.\n\n"
                "For $\\mathbb{R}^n$, apply the one-dimensional "
                "argument to each coordinate in turn (a diagonal "
                "argument).\n"
                "\\end{proof}"
            )),

            Section(level=2, children=[Text(text="Compactness and "
                                                  "continuity")]),
            RawLatex(text=(
                "\\begin{theorem}[Extreme value theorem]\n"
                "\\label{thm:evt}\n"
                "Let $K$ be a non-empty compact subset of a metric "
                "space and let $f: K \\to \\mathbb{R}$ be continuous. "
                "Then $f$ attains its maximum and minimum on $K$.\n"
                "\\end{theorem}"
            )),
            RawLatex(text=(
                "\\begin{proof}\n"
                "Since $f$ is continuous and $K$ is compact, $f(K)$ "
                "is a compact subset of $\\mathbb{R}$ (continuous "
                "images of compact sets are compact). By Heine--Borel "
                "(Theorem~\\ref{thm:heine-borel}), $f(K)$ is closed "
                "and bounded. In particular $\\sup f(K)$ exists and "
                "belongs to $f(K)$ (because $f(K)$ is closed), so "
                "the supremum is attained. The argument for the "
                "infimum is identical.\n"
                "\\end{proof}"
            )),

            Section(level=2, children=[Text(text="Worked example")]),
            RawLatex(text=(
                "\\begin{example}\n"
                "Show that the set $K = \\{(x, y) \\in \\mathbb{R}^2 "
                ": x^2 + y^2 \\leq 1\\}$ is compact.\n"
                "\\end{example}"
            )),
            _p(
                ("Solution.", ["bold"]),
                " The set ", MathInline(latex="K"),
                " is bounded (it lies inside the ball of radius 1) "
                "and closed (it is the pre-image of ",
                MathInline(latex="(-\\infty, 1]"),
                " under the continuous function ",
                MathInline(latex="f(x,y) = x^2 + y^2"),
                "). By the Heine–Borel theorem (Theorem ",
                CrossRef(label="thm:heine-borel", kind="ref"),
                "), ", MathInline(latex="K"), " is compact.",
            ),

            Section(level=2, children=[Text(text="Exercises")]),
            _ord_items(
                "Prove that a finite union of compact sets is compact.",
                "Give an example of a closed and bounded subset of a "
                "metric space that is not compact.",
                "Let f: K → ℝ be continuous on a compact set K. "
                "Prove that f is uniformly continuous on K.",
                "Show that the intersection of a compact set and a "
                "closed set is compact.",
            ),
        ],
    )


# --------------------------------------------------- conference poster

def poster() -> Document:
    """Conference poster layout using a0poster class — large-format
    multi-column poster with sections, figures and equations."""
    return Document(
        meta=_meta(
            documentclass="article",
            title="Conference poster",
            author="A. Researcher",
            body_font_pt=12,
            column_count=2,
            margin_left_cm=2.0, margin_right_cm=2.0,
            margin_top_cm=2.0, margin_bottom_cm=2.0,
            paragraph_indent=False,
            packages=DEFAULT_PACKAGES + ["natbib", "hyperref"],
        ),
        children=[
            Title(children=[Text(text="Efficient Monte Carlo sampling "
                                      "of Bayesian posteriors in "
                                      "high dimensions")]),
            Author(children=[Text(text="A. Researcher¹, B. Supervisor¹, "
                                       "C. Collaborator²"),
                             Footnote(children=[Text(text=
                                 "¹ Department of Statistics, University "
                                 "of Somewhere; ² Institute of Applied "
                                 "Mathematics, ETH Zürich")])]),

            Section(level=1, children=[Text(text="Motivation")]),
            _p(
                "Bayesian inference in high-dimensional parameter "
                "spaces is computationally challenging. Standard "
                "Markov chain Monte Carlo (MCMC) methods suffer from "
                "slow mixing when the posterior has strong "
                "correlations or multiple modes. We propose a "
                "preconditioned Hamiltonian Monte Carlo (HMC) sampler "
                "that adapts its mass matrix online, achieving "
                "effective sample sizes 5–20× larger than the "
                "No-U-Turn Sampler (NUTS) for the same wall-clock "
                "time.",
            ),

            Section(level=1, children=[Text(text="Method")]),
            _p(
                "We augment the target density ",
                MathInline(latex="\\pi(\\theta)"),
                " with momentum variables ",
                MathInline(latex="p \\sim \\mathcal{N}(0, M)"),
                " and simulate the Hamiltonian",
            ),
            MathBlock(
                latex=r"H(\theta, p) = -\log \pi(\theta) + "
                      r"\tfrac{1}{2} p^\top M^{-1} p.",
                numbered=True, label="eq:hamiltonian",
            ),
            _p(
                "The mass matrix ", MathInline(latex="M"),
                " is updated every ", MathInline(latex="K"),
                " leapfrog steps using a rank-one update from the "
                "sample covariance of the last ",
                MathInline(latex="W"), " accepted states. The update "
                "converges to the posterior covariance and the sampler "
                "becomes asymptotically optimal in the Gaussian limit.",
            ),

            Section(level=1, children=[Text(text="Key results")]),
            Table(
                rows=[
                    ["Problem (d)",           "NUTS ESS/s", "Ours ESS/s",
                     "Speedup"],
                    ["Logistic regression (50)",  "420",    "2 100",
                     "5.0×"],
                    ["Gaussian process (200)",    "38",     "540",
                     "14.2×"],
                    ["Hierarchical model (500)",  "12",     "240",
                     "20.0×"],
                ],
                caption="Effective sample size per second on three "
                        "benchmarks.",
                label="tab:poster-results",
                alignment="lrrr",
            ),
            _p(
                "The gains are most pronounced when the posterior "
                "has strong off-diagonal correlations, because the "
                "adapted mass matrix de-correlates the geometry for "
                "the leapfrog integrator.",
            ),

            Section(level=1, children=[Text(text="Convergence guarantee")]),
            _p(
                "Under mild regularity conditions on ",
                MathInline(latex="\\pi"), ", the adaptive chain "
                "satisfies a diminishing-adaptation criterion ",
                Citation(keys=["roberts2007"], style="citep"),
                " and therefore preserves ergodicity. Specifically, "
                "if the update schedule satisfies",
            ),
            MathBlock(
                latex=r"\sum_{k=1}^{\infty} \|M_{k+1} - M_k\|_F < \infty,",
                numbered=True, label="eq:diminishing",
            ),
            _p(
                "then the chain has the correct stationary "
                "distribution. Our rank-one schedule satisfies this "
                "by construction, since the covariance estimate "
                "converges almost surely.",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _items(
                "Online mass-matrix adaptation dramatically improves "
                "HMC efficiency in high dimensions.",
                "The method is a drop-in replacement for NUTS in "
                "probabilistic programming frameworks.",
                "Code available at github.com/aresearcher/adaptive-hmc.",
            ),
        ],
    )


# ------------------------------------------------ report / white paper

def white_paper() -> Document:
    """Short white paper / technical report — executive summary, problem
    statement, proposed solution, and recommendations."""
    return Document(
        meta=_meta(
            title="White paper",
            author="A. Author",
            body_font_pt=11,
            line_spacing=1.15,
            paragraph_indent=False,
            packages=DEFAULT_PACKAGES + ["hyperref"],
        ),
        children=[
            Title(children=[Text(text="Reducing build times in "
                                      "large-scale monorepos")]),
            Author(children=[Text(text="A. Author — Developer "
                                       "Productivity Team")]),
            Abstract(children=[Text(text=
                "Build times in our monorepo have grown from 8 minutes "
                "to 35 minutes over the past 18 months, driven by a "
                "3× increase in module count and inadequate caching. "
                "This white paper analyses the root causes, evaluates "
                "three mitigation strategies, and recommends a phased "
                "rollout of remote caching combined with dependency-"
                "graph pruning. We project a reduction to under "
                "12 minutes for 90% of incremental builds.")]),

            Section(level=1, children=[Text(text="Problem statement")]),
            _p(
                "The CI pipeline for the main monorepo currently "
                "averages 35 minutes per push, with P95 at 52 minutes. "
                "Developer surveys consistently rank build latency as "
                "the top friction point. The problem compounds: slow "
                "builds encourage batching changes into larger PRs, "
                "which are harder to review, more likely to cause "
                "merge conflicts, and slower to build — a vicious "
                "cycle.",
            ),
            _p(
                "Three factors contribute roughly equally to the "
                "regression:",
            ),
            _ord_items(
                "Module count grew from 120 to 380 without revisiting "
                "the dependency graph. Many modules pull in transitive "
                "dependencies they do not actually use.",
                "The local cache is invalidated by environment drift "
                "(different JDK patch versions, locale settings, "
                "timezone). Cache hit rates on CI are below 40%.",
                "Test execution is not parallelised effectively: the "
                "slowest test suite (integration tests for the "
                "payments module) takes 14 minutes and runs on a "
                "single executor.",
            ),

            Section(level=1, children=[Text(text="Evaluation of "
                                                  "strategies")]),
            Section(level=2, children=[Text(text="Strategy A: Remote "
                                                  "build cache")]),
            _p(
                "A shared, content-addressed cache (e.g. Gradle "
                "remote cache or Bazel remote execution) eliminates "
                "the environment-drift problem by keying on input "
                "hashes rather than machine state. Internal pilots "
                "on two smaller repos raised cache hit rates from "
                "38% to 87%, cutting median build time by 60%.",
            ),

            Section(level=2, children=[Text(text="Strategy B: Dependency "
                                                  "pruning")]),
            _p(
                "Static analysis of the dependency graph identified "
                "94 unused transitive edges. Removing them reduces "
                "the rebuild set for a typical one-module change from "
                "~70 modules to ~25. The pruning is low-risk: each "
                "edge removal is verified by a clean build before "
                "merging.",
            ),

            Section(level=2, children=[Text(text="Strategy C: Test "
                                                  "sharding")]),
            _p(
                "Splitting the payments integration suite across four "
                "parallel executors reduces its wall-clock time from "
                "14 minutes to 4.5 minutes. The implementation "
                "requires tagging tests with shard indices, which "
                "is straightforward but touches 340 test files.",
            ),

            Section(level=1, children=[Text(text="Recommendation")]),
            _p(
                "We recommend a phased approach:",
            ),
            Table(
                rows=[
                    ["Phase", "Strategy",          "Timeline",
                     "Expected impact"],
                    ["1",     "Remote cache",       "Jun 2026",
                     "−60% median build time"],
                    ["2",     "Dependency pruning",  "Jul–Aug 2026",
                     "−30% rebuild set size"],
                    ["3",     "Test sharding",       "Sep 2026",
                     "−10 min on P95"],
                ],
                caption="Phased rollout plan.",
                label="tab:phases",
                alignment="clll",
            ),
            _p(
                "Phases 1 and 2 are independent and can proceed in "
                "parallel if staffing allows. Phase 3 depends on "
                "Phase 2 (the shard assignment assumes the pruned "
                "graph). Total estimated effort: 1.5 engineer-months.",
            ),

            Section(level=1, children=[Text(text="Risks and mitigations")]),
            _items(
                "Cache poisoning: mitigated by content-addressable "
                "keys and a nightly cache-integrity check.",
                "False-positive pruning: each edge removal is gated "
                "on a green CI run; any breakage is caught before "
                "merge.",
                "Shard imbalance: monitored via a dashboard; "
                "re-balance quarterly.",
            ),

            Section(level=1, children=[Text(text="Conclusion")]),
            _p(
                "Build latency is a solvable problem. The three "
                "strategies described here are complementary and, "
                "taken together, should bring the median incremental "
                "build time back below 12 minutes. We request "
                "approval to begin Phase 1 in the June maintenance "
                "window.",
            ),
        ],
    )


# ------------------------------------------------- recipe / how-to guide

def recipe() -> Document:
    """Step-by-step how-to guide / recipe — numbered steps with tips
    and a summary table. Demonstrates ordered lists, tips in italic,
    and a compact single-page layout."""
    return Document(
        meta=_meta(
            title="How-to guide",
            author="",
            body_font_pt=11,
            margin_left_cm=2.5, margin_right_cm=2.5,
            paragraph_indent=False,
        ),
        children=[
            Title(children=[Text(text="Setting up a reproducible Python "
                                      "project from scratch")]),
            Author(children=[Text(text="A practical step-by-step guide")]),

            Section(level=1, children=[Text(text="Prerequisites")]),
            _items(
                "Python 3.12 or newer installed and on your PATH",
                "Git installed and configured (git config user.name / "
                "user.email)",
                "A terminal (bash, zsh, PowerShell, or Windows Terminal)",
                "A text editor or IDE of your choice",
            ),

            Section(level=1, children=[Text(text="Steps")]),

            Section(level=2, children=[Text(text="1. Create the project "
                                                  "directory")]),
            _p("Open a terminal and run:"),
            RawLatex(text=(
                "\\begin{verbatim}\n"
                "mkdir my-project && cd my-project\n"
                "git init\n"
                "\\end{verbatim}"
            )),
            _p(("Tip:", ["italic"]),
               " Choose a short, lowercase, hyphen-separated name. "
               "Avoid spaces and special characters."),

            Section(level=2, children=[Text(text="2. Set up a virtual "
                                                  "environment")]),
            _p("Create and activate a virtual environment:"),
            RawLatex(text=(
                "\\begin{verbatim}\n"
                "python -m venv .venv\n"
                "source .venv/bin/activate   # Linux / macOS\n"
                ".venv\\Scripts\\activate      # Windows\n"
                "\\end{verbatim}"
            )),
            _p(("Tip:", ["italic"]),
               " Add ", ("/.venv/", ["code"]),
               " to your ", (".gitignore", ["code"]),
               " so the environment is never committed."),

            Section(level=2, children=[Text(text="3. Pin your "
                                                  "dependencies")]),
            _p(
                "Create a ", ("pyproject.toml", ["code"]),
                " with your project metadata and dependencies. Then "
                "generate a lock file:",
            ),
            RawLatex(text=(
                "\\begin{verbatim}\n"
                "pip install pip-tools\n"
                "pip-compile -o requirements.lock pyproject.toml\n"
                "pip install -r requirements.lock\n"
                "\\end{verbatim}"
            )),

            Section(level=2, children=[Text(text="4. Add a test "
                                                  "framework")]),
            _p("Install pytest and create a minimal test:"),
            RawLatex(text=(
                "\\begin{verbatim}\n"
                "pip install pytest\n"
                "mkdir tests\n"
                "echo 'def test_smoke(): assert True' > tests/test_smoke.py\n"
                "pytest -q\n"
                "\\end{verbatim}"
            )),

            Section(level=2, children=[Text(text="5. Configure linting "
                                                  "and formatting")]),
            _p("Install ruff for both linting and formatting:"),
            RawLatex(text=(
                "\\begin{verbatim}\n"
                "pip install ruff\n"
                "ruff check .\n"
                "ruff format .\n"
                "\\end{verbatim}"
            )),

            Section(level=2, children=[Text(text="6. Make your first "
                                                  "commit")]),
            RawLatex(text=(
                "\\begin{verbatim}\n"
                "git add pyproject.toml requirements.lock .gitignore\n"
                "git add src/ tests/\n"
                "git commit -m \"Initial project skeleton\"\n"
                "\\end{verbatim}"
            )),

            Section(level=1, children=[Text(text="Summary")]),
            Table(
                rows=[
                    ["Step", "Tool",         "Purpose"],
                    ["1",    "git init",      "Version control"],
                    ["2",    "python -m venv", "Isolation"],
                    ["3",    "pip-tools",     "Reproducible deps"],
                    ["4",    "pytest",        "Testing"],
                    ["5",    "ruff",          "Linting + formatting"],
                    ["6",    "git commit",    "Checkpoint"],
                ],
                caption="Quick reference for each step.",
                label="tab:steps",
                alignment="cll",
            ),

            Section(level=1, children=[Text(text="Next steps")]),
            _items(
                "Add a CI pipeline (GitHub Actions, GitLab CI) that "
                "runs pytest and ruff on every push.",
                "Set up pre-commit hooks to catch issues before they "
                "reach CI.",
                "Add a README.md with setup instructions for "
                "collaborators.",
                "Consider adding type checking with mypy or pyright.",
            ),
        ],
    )


# --------------------------------------------------- daily journal

def _daily_planner_latex(year: int, month: int, day: int) -> str:
    """Build a single-page daily planner in raw LaTeX.

    Layout (all on one A4 page with 0.5 cm margins):
    - Header: day number in black box, weekday, date right-aligned
    - Middle: schedule grid 8:00–20:00 (left) + Notes/Memo (right)
    - Bottom: Top priorities (left) + Low priorities / Follow up (right)
    """
    import calendar as _cal
    import datetime as _dt

    dt = _dt.date(year, month, day)
    weekday = _cal.day_name[dt.weekday()]
    month_name = _cal.month_name[month]

    L: list[str] = []

    # --- Header ---
    L.append(
        "\\noindent"
        "\\fcolorbox{black}{black}"
        "{\\textcolor{white}{\\Large\\bfseries\\,\\," + str(day) + "\\,\\,}}"
        "\\hspace{4pt}"
        "{\\large\\bfseries " + weekday.lower() + "}"
        "\\hfill"
        "{\\large " + month_name.lower() + " " + str(day) + "}"
    )
    L.append("\\vspace{2pt}")
    L.append("\\noindent\\rule{\\textwidth}{0.5pt}")
    L.append("\\vspace{3pt}")

    # --- Schedule grid (left) + Notes/Memo (right) ---
    # Row height: fit 8:00–20:00 = 13 hours in ~21 cm available height
    # after header (~1.2 cm) and bottom boxes (~6 cm) → ~22 cm for grid.
    # Each hour row = 22/13 ≈ 1.69 cm; use 0.76 cm per half-hour slot.
    slot_h = "0.76cm"

    L.append("\\noindent\\begin{minipage}[t]{0.48\\textwidth}")
    L.append("\\renewcommand{\\arraystretch}{0}")
    L.append("\\begin{tabular}{@{}r|p{4.5cm}@{}}")
    for h in range(8, 21):
        L.append(
            f"\\scriptsize {h:02d}:00 & "
            f"\\rule{{0pt}}{{{slot_h}}} \\\\"
            "\\cline{2-2}"
        )
        L.append(
            f"\\scriptsize {h:02d}:30 & "
            f"\\rule{{0pt}}{{{slot_h}}} \\\\"
            "\\cline{2-2}"
        )
    L.append("\\end{tabular}")
    L.append("\\end{minipage}")
    L.append("\\hfill")

    # Notes / Memo column — same height as schedule grid
    n_note_lines = 26   # matches 13 hours × 2 slots
    L.append("\\begin{minipage}[t]{0.48\\textwidth}")
    L.append(
        "{\\scriptsize\\textbf{Notes} \\textbar\\ Memo}"
        "\\par\\vspace{2pt}"
    )
    for _ in range(n_note_lines):
        L.append(
            "\\noindent\\rule{\\textwidth}{0.2pt}"
            "\\par\\vspace{4.3pt}"
        )
    L.append("\\end{minipage}")

    L.append("\\vspace{4pt}")

    # --- Bottom boxes: Top priorities (left) + Low priorities & Follow up (right) ---
    L.append("\\noindent\\begin{minipage}[t]{0.48\\textwidth}")
    L.append(
        "\\fbox{\\begin{minipage}"
        "{\\dimexpr\\textwidth-2\\fboxsep-2\\fboxrule}"
        "{\\scriptsize\\textbf{Top priorities}}\\par\\vspace{2pt}"
    )
    for _ in range(6):
        L.append(
            "\\noindent$\\square$\\hspace{4pt}"
            "\\rule{0.86\\textwidth}{0.2pt}"
            "\\par\\vspace{2pt}"
        )
    L.append("\\end{minipage}}")
    L.append("\\end{minipage}")
    L.append("\\hfill")

    L.append("\\begin{minipage}[t]{0.48\\textwidth}")
    # Low priorities
    L.append(
        "\\fbox{\\begin{minipage}"
        "{\\dimexpr\\textwidth-2\\fboxsep-2\\fboxrule}"
        "{\\scriptsize\\textbf{Low priorities}}\\par\\vspace{2pt}"
    )
    for _ in range(3):
        L.append(
            "\\noindent$\\square$\\hspace{4pt}"
            "\\rule{0.86\\textwidth}{0.2pt}"
            "\\par\\vspace{2pt}"
        )
    L.append("\\end{minipage}}")
    L.append("\\vspace{3pt}")
    # Follow up
    L.append(
        "\\fbox{\\begin{minipage}"
        "{\\dimexpr\\textwidth-2\\fboxsep-2\\fboxrule}"
        "{\\scriptsize\\textbf{Follow up}}\\par\\vspace{2pt}"
    )
    for _ in range(3):
        L.append(
            "\\noindent$\\bullet$\\hspace{4pt}"
            "\\rule{0.86\\textwidth}{0.2pt}"
            "\\par\\vspace{2pt}"
        )
    L.append("\\end{minipage}}")
    L.append("\\end{minipage}")

    return "\n".join(L)


def daily_journal() -> Document:
    """Daily planner — single A4 page with hourly schedule grid
    (8:00–20:30), notes/memo lines, top priorities with checkboxes,
    low priorities, and follow-up. Generates today's date."""
    from datetime import date as _date
    today = _date.today()

    return Document(
        meta=_meta(
            title="", author="",
            body_font_pt=10,
            margin_left_cm=0.5, margin_right_cm=0.5,
            margin_top_cm=0.5, margin_bottom_cm=0.5,
            paragraph_indent=False,
            page_size="A4",
            packages=DEFAULT_PACKAGES + ["xcolor"],
        ),
        children=[
            RawLatex(text=_daily_planner_latex(
                today.year, today.month, today.day)),
        ],
    )


# --------------------------------------------------- weekly journal

def weekly_journal() -> Document:
    """Weekly journal / planner — goals, schedule overview, daily
    highlights, and end-of-week review."""
    return Document(
        meta=_meta(
            title="Weekly journal",
            author="",
            body_font_pt=11,
            margin_left_cm=2.0, margin_right_cm=2.0,
            margin_top_cm=2.0, margin_bottom_cm=2.0,
            paragraph_indent=False,
            line_spacing=1.15,
        ),
        children=[
            Title(children=[Text(text="Weekly Journal")]),
            Author(children=[Text(text="Week 21 · 19–25 May 2026")]),

            # --- Goals ---
            Section(level=1, children=[Text(text="Goals for this week")]),
            _ord_items(
                "Submit revised manuscript to Phys. Rev. B",
                "Finish poster abstract for ICML deadline (Friday)",
                "Run the full benchmark suite on the new cluster nodes",
                "30 min exercise at least 4 days",
                "Read two chapters of Tao's Analysis I",
            ),

            # --- Schedule overview ---
            Section(level=1, children=[Text(text="Schedule overview")]),
            Table(
                rows=[
                    ["Day",       "Morning",           "Afternoon",
                     "Evening"],
                    ["Mon",       "Deep work: paper",  "Group meeting",
                     "Gym"],
                    ["Tue",       "Deep work: paper",  "Seminar (Prof. N.)",
                     "Reading"],
                    ["Wed",       "Poster abstract",   "Lab meeting",
                     "Free"],
                    ["Thu",       "Benchmarks",        "1:1 with supervisor",
                     "Gym"],
                    ["Fri",       "Poster abstract",   "ICML deadline 17:00",
                     "Dinner out"],
                    ["Sat",       "Reading",           "Free",
                     "Free"],
                    ["Sun",       "Weekly review",     "Meal prep",
                     "Free"],
                ],
                caption="",
                alignment="llll",
            ),

            # --- Daily highlights ---
            Section(level=1, children=[Text(text="Daily highlights")]),

            Section(level=2, children=[Text(text="Monday 19 May")]),
            _p(
                "Finished the last round of revisions. Sent the "
                "manuscript to co-authors for a final read before "
                "submission. Group meeting ran long — new PhD student "
                "presented their literature review and needed feedback "
                "on scope.",
            ),

            Section(level=2, children=[Text(text="Tuesday 20 May")]),
            _p(
                "Co-authors signed off on the paper. Submitted to "
                "Phys. Rev. B at 15:22 — ", ("Goal 1 done.", ["bold"]),
                " Attended Prof. N.'s seminar on stochastic optimal "
                "control; good connection to our RL side-project.",
            ),

            Section(level=2, children=[Text(text="Wednesday 21 May")]),
            _p(
                "Drafted 80% of the poster abstract. Lab meeting "
                "feedback: need to clarify the error-bar methodology "
                "in Figure 3. Opened an issue to track that.",
            ),

            Section(level=2, children=[Text(text="Thursday 22 May")]),
            _p(
                "Benchmarks running on the new nodes — first results "
                "show a 1.8× speedup over the old cluster, consistent "
                "with the core-count ratio. 1:1 with supervisor: "
                "agreed to target NeurIPS for the follow-up paper.",
            ),

            Section(level=2, children=[Text(text="Friday 23 May")]),
            _p(
                "Polished and submitted the poster abstract at 14:30 "
                "— ", ("Goal 2 done.", ["bold"]),
                " Benchmark suite finished overnight; all 48 tests "
                "passed — ", ("Goal 3 done.", ["bold"]),
                " Celebrated with dinner at the Italian place.",
            ),

            Section(level=2, children=[Text(text="Weekend")]),
            _p(
                "Read chapters 4 and 5 of Tao — ",
                ("Goal 5 done.", ["bold"]),
                " Exercise: Mon gym, Thu gym, Sat 5 km run, Sun yoga "
                "— 4 days — ", ("Goal 4 done.", ["bold"]), ".",
            ),

            # --- Review ---
            Section(level=1, children=[Text(text="End-of-week review")]),

            _p(("Wins:", ["bold"])),
            _items(
                "All five goals completed — first clean sweep in a "
                "month",
                "Paper submitted ahead of the internal deadline",
                "New cluster benchmarks provide data for the NeurIPS "
                "intro section",
            ),

            _p(("Lessons:", ["bold"])),
            _items(
                "Setting a hard morning focus block works — protect "
                "it from meetings",
                "The poster abstract took longer than expected; start "
                "earlier next time",
                "Need a reproducible figure-generation script; manual "
                "re-plotting wasted an hour",
            ),

            _p(("Carry-over to next week:", ["bold"])),
            _items(
                "Fix the bootstrap error-bar code (from lab meeting "
                "feedback)",
                "Start NeurIPS paper outline",
                "Kitchen tap still leaking — call a plumber",
            ),
        ],
    )


# --------------------------------------------------- monthly journal

def monthly_journal() -> Document:
    """Monthly journal / review — goals, key events, metrics,
    achievements, and planning for next month."""
    return Document(
        meta=_meta(
            title="Monthly journal",
            author="",
            body_font_pt=11,
            margin_left_cm=2.5, margin_right_cm=2.5,
            margin_top_cm=2.0, margin_bottom_cm=2.0,
            paragraph_indent=False,
            line_spacing=1.15,
        ),
        children=[
            Title(children=[Text(text="Monthly Review")]),
            Author(children=[Text(text="May 2026")]),

            # --- Overview ---
            Section(level=1, children=[Text(text="Month at a glance")]),
            _p(
                "A strong month overall. The Phys. Rev. B paper was "
                "submitted after three rounds of internal review, the "
                "ICML poster was accepted, and the new cluster is now "
                "fully operational. On the personal side, maintained "
                "the exercise habit (17 out of 22 working days) and "
                "finished Tao's Analysis I.",
            ),

            # --- Goals review ---
            Section(level=1, children=[Text(text="Goals: review")]),
            Table(
                rows=[
                    ["Goal",                                "Status",
                     "Notes"],
                    ["Submit Phys. Rev. B paper",           "✓ Done",
                     "Submitted 20 May"],
                    ["ICML poster abstract",                "✓ Done",
                     "Accepted 28 May"],
                    ["Benchmark new cluster",               "✓ Done",
                     "1.8× speedup confirmed"],
                    ["Read Tao's Analysis I (Ch. 1–8)",     "✓ Done",
                     "Finished 25 May"],
                    ["Exercise 4×/week",                    "✓ 4.25 avg",
                     "17/20 target days"],
                    ["Draft NeurIPS outline",               "◻ Partial",
                     "Intro + methods only"],
                    ["Fix kitchen tap",                     "◻ Not done",
                     "Plumber booked for 3 Jun"],
                ],
                caption="May 2026 goals scorecard.",
                label="tab:monthly-goals",
                alignment="llp{5cm}",
            ),
            _p(
                "Five of seven goals completed. The NeurIPS outline "
                "stalled in weeks 3–4 because the poster deadline "
                "consumed the time I had planned for it. Realistic "
                "assessment: I over-committed by one goal this month.",
            ),

            # --- Key events ---
            Section(level=1, children=[Text(text="Key events")]),
            Table(
                rows=[
                    ["Date",    "Event"],
                    ["5 May",   "Group retreat — brainstormed Q3 "
                                "research directions"],
                    ["12 May",  "Prof. N.'s colloquium on stochastic "
                                "control"],
                    ["20 May",  "Phys. Rev. B submission"],
                    ["23 May",  "ICML poster abstract submitted"],
                    ["28 May",  "ICML acceptance notification — poster "
                                "accepted"],
                    ["30 May",  "New PhD student E. joined the group"],
                ],
                caption="",
                alignment="lp{12cm}",
            ),

            # --- Metrics ---
            Section(level=1, children=[Text(text="Metrics")]),
            Table(
                rows=[
                    ["Metric",                  "April", "May",
                     "Trend"],
                    ["Papers submitted",        "0",     "1",
                     "↑"],
                    ["Conference submissions",  "0",     "1",
                     "↑"],
                    ["Deep-work hours",         "62",    "71",
                     "↑ +15%"],
                    ["Exercise days",           "14",    "17",
                     "↑"],
                    ["Books / chapters read",   "4",     "8",
                     "↑"],
                    ["Meetings attended",       "18",    "16",
                     "↓ (good)"],
                ],
                caption="Month-over-month tracking.",
                label="tab:monthly-metrics",
                alignment="lrrr",
            ),

            # --- Reflection ---
            Section(level=1, children=[Text(text="Reflection")]),

            _p(("What went well:", ["bold"])),
            _items(
                "Protecting the morning focus block paid off — deep-"
                "work hours up 15%",
                "Starting the paper revision early meant the deadline "
                "felt comfortable instead of rushed",
                "The exercise habit is now self-sustaining; missed "
                "days feel wrong rather than normal",
            ),

            _p(("What to improve:", ["bold"])),
            _items(
                "Over-committed on goals again — cap at 5 next month",
                "Spent too long on email in the afternoons; batch it "
                "to two 20-minute windows",
                "The reading goal was met but at the expense of the "
                "NeurIPS outline — need to prioritise better",
            ),

            _p(("Surprises:", ["bold"])),
            _items(
                "The cluster speedup was higher than expected — worth "
                "re-running older experiments",
                "ICML poster acceptance came faster than anticipated; "
                "need to start making the poster now",
            ),

            # --- Next month ---
            Section(level=1, children=[Text(text="Goals for June 2026")]),
            _ord_items(
                "Complete NeurIPS paper outline and first draft of "
                "Introduction + Methods",
                "Design and print ICML poster (conference 15–20 July)",
                "Onboard new PhD student E. — set up their dev "
                "environment and assign first reading list",
                "Start Tao's Analysis II (target: chapters 1–4)",
                "Exercise 4×/week (maintain)",
            ),

            _p(("Key dates:", ["bold"])),
            Table(
                rows=[
                    ["Date",    "Event"],
                    ["3 Jun",   "Plumber visit (finally)"],
                    ["7 Jun",   "Database migration maintenance window"],
                    ["10 Jun",  "Group meeting: NeurIPS outline review"],
                    ["15 Jun",  "ICML poster draft to co-authors"],
                    ["30 Jun",  "Monthly review"],
                ],
                caption="",
                alignment="ll",
            ),
        ],
    )


# --------------------------------------------------- calendar

def _calendar_latex(year: int, month: int) -> str:
    """Build a landscape monthly calendar grid in raw LaTeX.

    Matches the classic wall-calendar / desk-planner style:
    - centred month + year heading in large caps
    - seven day-of-week column headers in small caps
    - tall cells with the day number at the top-right
    - fills the full landscape A4 page (0.5 cm margins)
    """
    import calendar as _cal

    month_name = _cal.month_name[month].upper()
    cal = _cal.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)
    n_weeks = len(weeks)

    # A4 landscape usable: 29.7 − 2×0.5 = 28.7 cm wide,
    # 21.0 − 2×0.5 = 20.0 cm tall.
    # Reserve ~1.2 cm for heading + header row → ~18.8 cm for weeks.
    available_h = 18.8
    cell_h_cm = round(available_h / n_weeks, 2)

    # Column width: 28.7 cm / 7 ≈ 4.1 cm each, minus tabcolsep+rules.
    col_spec = (
        "p{\\dimexpr\\textwidth/7-2\\tabcolsep-\\arrayrulewidth\\relax}"
    )

    day_names = ["Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday", "Sunday"]

    L: list[str] = []
    L.append("\\begin{center}")
    L.append(
        f"{{\\LARGE\\bfseries {month_name}}}\\\\[1pt]"
        f"{{\\large {year}}}"
    )
    L.append("\\end{center}")
    L.append("\\vspace{-2pt}")

    L.append("\\noindent\\makebox[\\textwidth]{%")
    L.append("\\begin{tabular}{|" + "|".join([col_spec] * 7) + "|}")
    L.append("\\hline")

    # Day-of-week header
    hdr = []
    for i, dn in enumerate(day_names):
        prefix = "\\centering\\arraybackslash" if i == 6 else "\\centering"
        hdr.append(f"{prefix}\\textsc{{{dn}}}")
    L.append(" & ".join(hdr) + " \\\\")
    L.append("\\hline")

    # Week rows — use a \parbox so the day number sits at the top-right
    # and the rest of the cell is empty writing space below.
    for w in weeks:
        cells: list[str] = []
        for d in w:
            inner_w = (
                "\\dimexpr\\textwidth/7-2\\tabcolsep"
                "-\\arrayrulewidth-2\\fboxsep\\relax"
            )
            if d == 0:
                cells.append(
                    f"\\parbox[t][{cell_h_cm}cm][t]{{{inner_w}}}"
                    "{\\mbox{}}"
                )
            else:
                cells.append(
                    f"\\parbox[t][{cell_h_cm}cm][t]{{{inner_w}}}"
                    "{\\raggedleft\\footnotesize\\textbf{"
                    + str(d) + "}\\par}"
                )
        L.append(" & ".join(cells) + " \\\\")
        L.append("\\hline")

    L.append("\\end{tabular}}")
    return "\n".join(L)


def calendar() -> Document:
    """Monthly calendar — landscape full-page planner grid for the
    current month with day-of-week headers and tall writable cells.
    Generated dynamically so it always shows the real calendar."""
    from datetime import date as _date
    today = _date.today()

    return Document(
        meta=_meta(
            title="", author="",
            body_font_pt=10,
            margin_left_cm=0.5, margin_right_cm=0.5,
            margin_top_cm=0.5, margin_bottom_cm=0.5,
            paragraph_indent=False,
            page_size="A4",
            class_options="landscape",
            preamble_extras="\\geometry{landscape}",
        ),
        children=[
            RawLatex(text=_calendar_latex(today.year, today.month)),
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
    ("&CV / résumé",          cv),
    ("La&b report",           lab_report),
    ("&Homework / problem set", homework),
    ("Technical &memo",       memo),
    ("L&iterature review",    literature_review),
    ("&Research proposal",    research_proposal),
    ("Boo&k chapter",         book_chapter),
    ("Meeti&ng minutes",      meeting_minutes),
    ("Lec&ture notes",        lecture_notes),
    ("&Poster / two-column",  poster),
    ("&White paper",          white_paper),
    ("How-to &guide",         recipe),
    ("&Daily journal",        daily_journal),
    ("Wee&kly journal",       weekly_journal),
    ("Mo&nthly journal",      monthly_journal),
    ("Ca&lendar",             calendar),
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
