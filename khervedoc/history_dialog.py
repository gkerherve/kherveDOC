"""Commit-browser dialog.

A two-pane window:

  - Left:  table of every commit on HEAD (date, short SHA, subject,
           author), newest first. Click a row to load that commit.
  - Right: top half  — full commit message and metadata.
           bottom half — the unified diff for that commit with
           PyCharm-style red/green line highlighting.

Replaces the old "show every commit in a QMessageBox" approach, which
was unreadable past about three commits and offered no diff at all.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from . import git_backend


class _DiffHighlighter(QSyntaxHighlighter):
    """Colour a unified-diff text block the way most code editors do:

      - header (diff/index/---/+++): muted grey
      - hunk header (@@ ... @@): blue + bold
      - addition (+ at column 0): green text on pale green
      - removal (- at column 0): red text on pale red
      - everything else: default (context lines)
    """

    def __init__(self, document) -> None:
        super().__init__(document)
        # Decide whether the surrounding palette is dark so the diff
        # colours stay legible either way. We sample the document's
        # default background.
        bg = self.document().defaultFont()  # unused; we go by widget bg later
        # Pick fixed-ish colours that work on both light and dark
        # editor backgrounds — the row is highlighted, not the page,
        # so we can use saturated tints without crushing the text.
        self._fmt_header = QTextCharFormat()
        self._fmt_header.setForeground(QColor("#7a7a7a"))
        self._fmt_header.setFontItalic(True)

        self._fmt_hunk = QTextCharFormat()
        self._fmt_hunk.setForeground(QColor("#1a4fa0"))
        self._fmt_hunk.setFontWeight(QFont.Bold)

        self._fmt_add = QTextCharFormat()
        self._fmt_add.setForeground(QColor("#0a6f00"))
        self._fmt_add.setBackground(QColor("#e6f7e6"))

        self._fmt_del = QTextCharFormat()
        self._fmt_del.setForeground(QColor("#a8001a"))
        self._fmt_del.setBackground(QColor("#fde0e0"))

    def highlightBlock(self, text: str) -> None:
        if not text:
            return
        first = text[:4]
        # Order matters: +++ / --- (file headers) before +/- (line ops).
        if (text.startswith("+++") or text.startswith("---")
                or text.startswith("diff ") or text.startswith("index ")
                or text.startswith("new file")
                or text.startswith("deleted file")
                or text.startswith("similarity ")
                or text.startswith("rename ")):
            self.setFormat(0, len(text), self._fmt_header)
            return
        if text.startswith("@@"):
            self.setFormat(0, len(text), self._fmt_hunk)
            return
        if text.startswith("+"):
            self.setFormat(0, len(text), self._fmt_add)
            return
        if text.startswith("-"):
            self.setFormat(0, len(text), self._fmt_del)
            return
        # context line: leave as default


class HistoryDialog(QDialog):
    """Browse the commits behind the current document and view each
    commit's diff. Self-contained — accepts a directory and reads the
    git history through `git_backend`."""

    def __init__(self, repo_dir: Path, parent: QWidget | None = None,
                 file_stem: str | None = None) -> None:
        super().__init__(parent)
        title = file_stem or repo_dir.name
        self.setWindowTitle(f"Commit history — {title}")
        self.resize(1100, 700)
        self._repo_dir = repo_dir
        self._commits = git_backend.history_detailed(repo_dir,
                                                     file_stem=file_stem)

        # ---- Left: commit table -----------------------------------------
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["When", "SHA", "Message", "Author"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(True)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Interactive)
        hdr.resizeSection(0, 150)
        hdr.resizeSection(1, 70)
        hdr.resizeSection(3, 80)

        for row, c in enumerate(self._commits):
            self._table.insertRow(row)
            for col, key in enumerate(("timestamp", "short_oid",
                                       "subject", "author")):
                item = QTableWidgetItem(c[key])
                item.setToolTip(c[key])
                if col == 1:
                    # Monospace the SHA so they line up nicely.
                    f = item.font(); f.setFamily("Consolas"); item.setFont(f)
                self._table.setItem(row, col, item)
        self._table.resizeRowsToContents()
        self._table.currentCellChanged.connect(self._on_row_changed)

        # ---- Right: details + diff --------------------------------------
        self._meta_label = QLabel("Select a commit to see its diff.")
        self._meta_label.setWordWrap(True)
        self._meta_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._meta_label.setStyleSheet(
            "padding: 8px; background: palette(alternate-base);")

        self._diff = QPlainTextEdit()
        self._diff.setReadOnly(True)
        f = QFont("Consolas"); f.setStyleHint(QFont.Monospace); f.setPointSize(10)
        self._diff.setFont(f)
        # Wrap long lines at the widget edge instead of forcing a
        # horizontal scrollbar. Diffs of prose-y LaTeX (long body
        # paragraphs, multi-sentence captions) end up with
        # multi-hundred-char lines that the user couldn't read
        # without scrolling sideways one line at a time.
        self._diff.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        # Attach the syntax highlighter to the editor's QTextDocument so
        # every block reload gets re-coloured automatically.
        self._highlighter = _DiffHighlighter(self._diff.document())

        # ---- Restore button ---------------------------------------------
        # Brings the selected commit's files back into the working tree
        # without rewriting history. The user can then save normally and
        # auto-commit produces a fresh commit on top — like Word's
        # "Restore version" in Document History.
        self._restore_btn = QPushButton("↩ Restore this version")
        self._restore_btn.setToolTip(
            "Roll the document files back to the selected commit. "
            "Your current state stays in the history — restoring just "
            "creates a new commit on top with the older contents.")
        self._restore_btn.clicked.connect(self._on_restore_clicked)
        # Remember the parent window so we can hand the restored
        # document back to it for reload.
        self._parent_window = parent

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.addWidget(self._meta_label)
        rlay.addWidget(self._diff, 1)
        rlay.addWidget(self._restore_btn)

        # ---- Splitter ----------------------------------------------------
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._table)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([400, 700])

        outer = QHBoxLayout(self)
        outer.addWidget(split)

        # Auto-select the newest commit so the dialog opens already
        # showing a diff — there's nothing more useless than an empty
        # right-hand pane.
        if self._commits:
            self._table.setCurrentCell(0, 0)

    # ---- selection handling ---------------------------------------------

    def _on_row_changed(self, row: int, *_) -> None:
        if row < 0 or row >= len(self._commits):
            self._meta_label.setText("")
            self._diff.setPlainText("")
            return
        c = self._commits[row]
        # The label is HTML so we can put the SHA / author / date in a
        # subtler weight than the message itself.
        body_html = ("<br><pre style='margin:6px 0 0 0;white-space:pre-wrap;'>"
                     f"{_html_escape(c['body'])}</pre>") if c["body"] else ""
        self._meta_label.setText(
            f"<b style='font-size: 12pt;'>{_html_escape(c['subject'])}</b>"
            f"<br><span style='color:#666;'>"
            f"{_html_escape(c['short_oid'])} &middot; "
            f"{_html_escape(c['author'])} &middot; "
            f"{_html_escape(c['timestamp'])}</span>"
            f"{body_html}"
        )
        diff = git_backend.diff_for_commit(self._repo_dir, c["oid"])
        if not diff:
            diff = "(no diff — empty commit or root commit with no tree)"
        self._diff.setPlainText(diff)

    # ---- restore handling -----------------------------------------------

    def _on_restore_clicked(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._commits):
            return
        c = self._commits[row]
        # Confirm — restoring overwrites whatever is in the working
        # tree right now. We don't lose history (HEAD doesn't move),
        # but unsaved edits to the current file would vanish.
        confirm = QMessageBox.question(
            self, "Restore this version",
            f"<b>Roll the document back to this version?</b><br><br>"
            f"<code>{_html_escape(c['short_oid'])}</code> &middot; "
            f"{_html_escape(c['timestamp'])}<br>"
            f"<i>{_html_escape(c['subject'])}</i><br><br>"
            f"<span style='color:#666;'>"
            f"Your current document state isn't lost — every saved "
            f"version is still in the history. The next Ctrl+S will "
            f"record the restored contents as a new commit on top."
            f"</span>",
            QMessageBox.Yes | QMessageBox.Cancel)
        if confirm != QMessageBox.Yes:
            return
        ok, msg = git_backend.restore_to_commit(self._repo_dir, c["oid"])
        if not ok:
            QMessageBox.critical(self, "Restore failed", msg)
            return
        # Ask the parent window (the MainWindow) to reload the doc
        # from disk so the editor immediately shows the restored
        # contents instead of whatever it had loaded.
        reload_method = getattr(self._parent_window, "_reload_current", None)
        if callable(reload_method):
            reload_method()
        QMessageBox.information(
            self, "Restored",
            f"The document was rolled back to commit "
            f"<code>{_html_escape(c['short_oid'])}</code>.<br><br>"
            f"Save (Ctrl+S) when you're ready — that records the "
            f"restored contents as a new commit on top.")


def _html_escape(s: str) -> str:
    """Minimal HTML escape so commit metadata can't break the label."""
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))
