"""Live-preview template editors: LaTeX equations and mhchem chemistry.

Kept out of ``mainwindow`` so ``editor`` can open these dialogs when the
user double-clicks a rendered equation without importing the main window
(which imports ``editor``). Mirrors KherveSlide's ``equation_editor``.
"""
from __future__ import annotations

import re as _re

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFrame, QGridLayout,
    QLabel, QPlainTextEdit, QScrollArea, QStackedWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from . import chemistry, equations, icons


_BEGIN_RE = _re.compile(r"\\begin\{(\w+\*?)\}$")


class _EquationLatexEdit(QPlainTextEdit):
    """LaTeX input field that intercepts Tab/Shift+Tab to navigate
    between placeholder slots instead of inserting tab chars.

    The slot token is configurable because mhchem chokes on a bare
    ``\\square`` — see ``chemistry.PLACEHOLDER``."""

    def __init__(self, placeholder: str = r"\square", parent=None):
        super().__init__(parent)
        self._PLACEHOLDER = placeholder

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Tab and not ev.modifiers():
            self._jump_placeholder(forward=True)
            return
        if ev.key() == Qt.Key_Backtab or (
                ev.key() == Qt.Key_Tab
                and ev.modifiers() == Qt.ShiftModifier):
            self._jump_placeholder(forward=False)
            return
        if ev.text() == "}":
            if self._auto_close_begin():
                return
        super().keyPressEvent(ev)

    def _auto_close_begin(self) -> bool:
        """If the cursor sits right after ``\\begin{xxx``, insert the
        closing ``}`` plus ``\\n\\square\\n\\end{xxx}`` and return True."""
        cursor = self.textCursor()
        text = self.toPlainText()
        before = text[:cursor.position()]
        m = _BEGIN_RE.search(before + "}")
        if not m:
            return False
        env = m.group(1)
        self.insertPlainText(f"}}\n{self._PLACEHOLDER}\n\\end{{{env}}}")
        return True

    def _jump_placeholder(self, forward: bool) -> None:
        text = self.toPlainText()
        cursor = self.textCursor()
        pos = cursor.position()
        ph = self._PLACEHOLDER
        if forward:
            idx = text.find(ph, pos)
            if idx < 0:
                idx = text.find(ph)  # wrap around
        else:
            idx = text.rfind(ph, 0, pos)
            if idx < 0:
                idx = text.rfind(ph)  # wrap around
        if idx < 0:
            return
        cursor.setPosition(idx)
        cursor.setPosition(idx + len(ph), QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)


class _TemplatePaletteDialog(QDialog):
    """Shared shell for the equation and chemistry editors.

    Shows a rendered preview that updates as you type, a category
    toolbar with template buttons, and a source field with
    Tab-navigable placeholders. Clicking Insert emits the final
    LaTeX for insertion into the document.

    Subclasses supply the template data, the two preview renderers and
    the placeholder token; everything else is identical.
    """

    _TITLE = "Template editor"
    # Each entry is a zero-arg QIcon factory, or a str to label the button
    # with text when no drawn icon exists for that category.
    _CATEGORY_ICONS: list = []
    _CAT_COLS = 6
    _CAT_BTN_SIZE = (40, 34)
    _EMPTY_HINT = "Click a template to start"
    _EDIT_HINT = ""
    _SOURCE_LABEL = "LaTeX source:"
    _PLACEHOLDER = r"\square"

    def _groups(self) -> list:
        raise NotImplementedError

    def _render_template(self, latex: str):
        raise NotImplementedError

    def _render_live(self, latex: str):
        raise NotImplementedError

    def _extra_widgets(self, root: QVBoxLayout) -> None:
        """Hook for subclass controls between the source field and the
        button box."""

    def __init__(self, parent: QWidget | None = None,
                 initial_latex: str = ""):
        super().__init__(parent)
        self.setWindowTitle(self._TITLE)
        self.resize(640, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ---- live preview ----
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setMinimumHeight(80)
        self._preview.setStyleSheet(
            "QLabel { background: white; border: 1px solid #ccc; "
            "border-radius: 4px; padding: 12px; }")
        self._preview.setText(
            f"<span style='color:#999;'>{self._EMPTY_HINT}</span>")
        root.addWidget(self._preview)

        # ---- category toolbar ----
        toolbar = QFrame()
        toolbar.setFrameShape(QFrame.StyledPanel)
        tb_grid = QGridLayout(toolbar)
        tb_grid.setSpacing(2)
        tb_grid.setContentsMargins(4, 4, 4, 4)
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        groups = self._groups()
        cols = self._CAT_COLS
        for idx, (group_name, _items) in enumerate(groups):
            btn = QToolButton()
            btn.setCheckable(True)
            spec = (self._CATEGORY_ICONS[idx]
                    if idx < len(self._CATEGORY_ICONS) else None)
            if callable(spec):
                btn.setIcon(spec())
                btn.setIconSize(QSize(24, 24))
            else:
                btn.setText(spec if spec else group_name[:3])
            btn.setToolTip(group_name)
            btn.setFixedSize(*self._CAT_BTN_SIZE)
            btn.setStyleSheet(
                "QToolButton { border: 1px solid transparent; "
                "border-radius: 3px; }"
                "QToolButton:checked { border: 1px solid #1a6dd8; "
                "background: #e0edfa; }")
            self._btn_group.addButton(btn, idx)
            tb_grid.addWidget(btn, idx // cols, idx % cols)
        root.addWidget(toolbar)

        # ---- category label ----
        self._cat_label = QLabel()
        self._cat_label.setStyleSheet(
            "font-weight: bold; color: #444; padding: 2px 4px;")
        root.addWidget(self._cat_label)

        # ---- template panel (stacked, one page per category) ----
        self._stack = QStackedWidget()
        self._populated: set[int] = set()
        for _ in groups:
            page = QWidget()
            QVBoxLayout(page)
            self._stack.addWidget(page)
        self._stack.setMaximumHeight(160)
        root.addWidget(self._stack)

        self._btn_group.idClicked.connect(self._show_category)
        first = self._btn_group.button(0)
        if first:
            first.setChecked(True)
            self._show_category(0)

        # ---- LaTeX input field ----
        latex_label = QLabel(self._SOURCE_LABEL)
        latex_label.setStyleSheet("color: #666; font-size: 9pt;")
        root.addWidget(latex_label)
        self._edit = _EquationLatexEdit(self._PLACEHOLDER)
        self._edit.setMaximumHeight(72)
        from PySide6.QtGui import QFont as _QFont
        mf = _QFont("Consolas"); mf.setStyleHint(_QFont.Monospace)
        mf.setPointSize(10)
        self._edit.setFont(mf)
        self._edit.setPlaceholderText(self._EDIT_HINT)
        root.addWidget(self._edit)

        self._extra_widgets(root)

        # ---- Insert / Cancel buttons ----
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText("Insert")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

        # ---- debounced live preview ----
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._update_preview)
        self._edit.textChanged.connect(self._preview_timer.start)

        # Seed with initial LaTeX if provided
        if initial_latex:
            self._edit.setPlainText(initial_latex)

    def latex(self) -> str:
        return self._edit.toPlainText().strip()

    # ---- category / template plumbing (reused from old builder) ----

    def _show_category(self, index: int) -> None:
        groups = self._groups()
        if index < 0 or index >= len(groups):
            return
        group_name, items = groups[index]
        self._cat_label.setText(group_name)
        self._stack.setCurrentIndex(index)
        if index not in self._populated:
            self._populate_page(index, items)
            self._populated.add(index)

    def _populate_page(self, index: int, items: list) -> None:
        page = self._stack.widget(index)
        old_layout = page.layout()
        if old_layout:
            while old_layout.count():
                old_layout.takeAt(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(4)
        grid.setContentsMargins(4, 4, 4, 4)
        btn_cols = 5
        for i, (latex, preview_text) in enumerate(items):
            btn = QToolButton()
            btn.setToolTip(f"{preview_text}\n{latex}")
            pixmap = self._render_template(latex)
            if pixmap and not pixmap.isNull():
                btn.setIcon(QIcon(pixmap))
                pw, ph = pixmap.width(), pixmap.height()
                btn.setIconSize(QSize(min(pw, 100), min(ph, 50)))
                btn.setFixedSize(min(pw + 12, 112), min(ph + 8, 58))
            else:
                btn.setText(preview_text)
                btn.setFixedSize(80, 40)
            btn.setStyleSheet(
                "QToolButton { border: 1px solid #ccc; "
                "border-radius: 3px; padding: 2px; }"
                "QToolButton:hover { border: 1px solid #1a6dd8; "
                "background: #e8f0fa; }")
            btn.clicked.connect(
                lambda checked=False, tex=latex: self._insert_template(tex))
            grid.addWidget(btn, i // btn_cols, i % btn_cols)
        scroll.setWidget(inner)
        old_layout.addWidget(scroll)

    def _insert_template(self, latex: str) -> None:
        """Insert a template at the cursor, replacing the selected
        placeholder if one is selected."""
        cursor = self._edit.textCursor()
        cursor.insertText(latex)
        self._edit.setFocus()
        # Jump to first placeholder in what we just inserted
        self._edit._jump_placeholder(forward=True)

    def _update_preview(self) -> None:
        text = self._edit.toPlainText().strip()
        if not text:
            self._preview.setPixmap(QPixmap())
            self._preview.setText(
                f"<span style='color:#999;'>{self._EMPTY_HINT}</span>")
            return
        px = self._render_live(text)
        if px and not px.isNull():
            self._preview.setText("")
            self._preview.setPixmap(px)
        else:
            self._preview.setPixmap(QPixmap())
            self._preview.setText(
                "<span style='color:#c00;'>Cannot render: check "
                "syntax</span>")


class EquationEditorDialog(_TemplatePaletteDialog):
    """Live-preview LaTeX equation editor."""

    _TITLE = "Equation editor"
    _EMPTY_HINT = "Click a template to start building your equation"
    _EDIT_HINT = r"e.g.  \frac{x+1}{2} + \sqrt{y}"
    _CATEGORY_ICONS = [
        icons.eq_fractions, icons.eq_sums, icons.eq_integrals,
        icons.eq_scripts, icons.eq_derivatives, icons.eq_greek,
        icons.eq_vectors, icons.eq_brackets, icons.eq_relations,
        icons.eq_functions, icons.eq_environments,
    ]

    def _groups(self):
        return equations.EQUATION_GROUPS

    def _render_template(self, latex: str):
        return equations.render_template_preview(latex)

    def _render_live(self, latex: str):
        return equations.render_live_preview(latex)


class ChemistryEditorDialog(_TemplatePaletteDialog):
    """Live-preview editor for mhchem chemical equations.

    The source field holds the *body* of ``\\ce{...}`` — the user never
    types the wrapper. :meth:`latex` adds it back.
    """

    _TITLE = "Chemistry editor"
    _EMPTY_HINT = "Click a template to start building your reaction"
    _EDIT_HINT = "e.g.  2H2 + O2 -> 2H2O"
    _SOURCE_LABEL = "Formula (mhchem syntax, inserted inside \\ce{…}):"
    _PLACEHOLDER = chemistry.PLACEHOLDER
    _CAT_COLS = 6
    _CAT_BTN_SIZE = (48, 34)
    _CATEGORY_ICONS = ["A→B", "→", "(s)", "±", "H₂O", "A−B"]

    def _groups(self):
        return chemistry.CHEM_GROUPS

    def _render_template(self, latex: str):
        return chemistry.render_template_preview(latex)

    def _render_live(self, latex: str):
        return chemistry.render_live_preview(latex)

    def _extra_widgets(self, root: QVBoxLayout) -> None:
        self._display_cb = QCheckBox(
            "Display on its own line (numbered equation)")
        root.addWidget(self._display_cb)

    def is_display(self) -> bool:
        return self._display_cb.isChecked()

    def latex(self) -> str:
        return chemistry.wrap_ce(self._edit.toPlainText())
