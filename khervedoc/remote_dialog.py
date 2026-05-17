"""Configure git remotes — name + URL pairs — without leaving the
editor. Lets the user wire up GitHub, GitLab, Bitbucket or any plain
git server so that File > Git > Pull / Push has somewhere to talk to.

Validation is intentionally permissive: we accept any non-empty URL
(https://, git@, ssh://, file://) so users on internal git servers
aren't blocked. The actual auth is handled by libgit2's credentials
helpers when the user later pulls or pushes."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import git_backend


_COMMON_HINTS = (
    "GitHub:    https://github.com/<user>/<repo>.git",
    "GitLab:    https://gitlab.com/<user>/<repo>.git",
    "Bitbucket: https://bitbucket.org/<user>/<repo>.git",
    "SSH form:  git@github.com:<user>/<repo>.git",
)


class RemoteDialog(QDialog):
    """List / add / edit / remove remotes for one document's repo."""

    def __init__(self, repo_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo_dir = repo_dir
        self.setWindowTitle("Configure git remotes")
        self.resize(640, 380)

        intro = QLabel(
            "Remotes the editor can pull from and push to. Most users only "
            "need one called <code>origin</code>. You can paste any git URL "
            "here — examples:<br><br>"
            + "<br>".join(f"<code>{h}</code>" for h in _COMMON_HINTS))
        intro.setWordWrap(True)
        intro.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Name", "URL"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)

        btn_add = QPushButton("&Add…")
        btn_edit = QPushButton("&Edit URL…")
        btn_del = QPushButton("&Remove")
        btn_add.clicked.connect(self._add)
        btn_edit.clicked.connect(self._edit)
        btn_del.clicked.connect(self._remove)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_edit)
        btn_row.addWidget(btn_del)
        btn_row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)

        outer = QVBoxLayout(self)
        outer.addWidget(intro)
        outer.addWidget(self._table, 1)
        outer.addLayout(btn_row)
        outer.addWidget(buttons)

        self._refresh()

    # ---- model / view sync ---------------------------------------------

    def _refresh(self) -> None:
        remotes = git_backend.get_remotes(self._repo_dir)
        self._table.setRowCount(0)
        for name, url in remotes:
            row = self._table.rowCount()
            self._table.insertRow(row)
            n_item = QTableWidgetItem(name)
            u_item = QTableWidgetItem(url)
            for it in (n_item, u_item):
                it.setToolTip(it.text())
            self._table.setItem(row, 0, n_item)
            self._table.setItem(row, 1, u_item)
        if self._table.rowCount():
            self._table.setCurrentCell(0, 0)

    def _current_row(self) -> tuple[str, str] | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        n_item = self._table.item(row, 0)
        u_item = self._table.item(row, 1)
        if n_item is None or u_item is None:
            return None
        return n_item.text(), u_item.text()

    # ---- actions --------------------------------------------------------

    def _add(self) -> None:
        existing = {n for n, _ in git_backend.get_remotes(self._repo_dir)}
        default_name = "origin" if "origin" not in existing else ""
        name, ok = QInputDialog.getText(
            self, "Add remote", "Remote name (e.g. origin):", text=default_name)
        name = name.strip()
        if not ok or not name:
            return
        if name in existing:
            QMessageBox.warning(
                self, "Remote exists",
                f"A remote named {name!r} already exists. Use Edit URL to "
                "change its URL instead.")
            return
        url, ok = QInputDialog.getText(
            self, "Add remote",
            "URL (https://…, git@…, ssh://…, file://…):")
        url = url.strip()
        if not ok or not url:
            return
        if not git_backend.set_remote(self._repo_dir, name, url):
            QMessageBox.critical(self, "Add remote",
                                 "Failed to add the remote — see the log.")
            return
        self._refresh()

    def _edit(self) -> None:
        current = self._current_row()
        if current is None:
            return
        name, old_url = current
        new_url, ok = QInputDialog.getText(
            self, f"Edit remote {name!r}",
            f"New URL for {name!r}:", text=old_url)
        new_url = new_url.strip()
        if not ok or not new_url or new_url == old_url:
            return
        if not git_backend.set_remote(self._repo_dir, name, new_url):
            QMessageBox.critical(self, "Edit remote",
                                 "Failed to update the remote URL.")
            return
        self._refresh()

    def _remove(self) -> None:
        current = self._current_row()
        if current is None:
            return
        name, _ = current
        confirm = QMessageBox.question(
            self, "Remove remote",
            f"Remove the remote {name!r}? This only removes the "
            "configured URL — nothing is deleted from the remote server.")
        if confirm != QMessageBox.Yes:
            return
        if not git_backend.remove_remote(self._repo_dir, name):
            QMessageBox.critical(self, "Remove remote",
                                 f"Failed to remove {name!r}.")
            return
        self._refresh()
