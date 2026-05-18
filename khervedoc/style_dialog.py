"""Dialog for viewing, importing and removing LaTeX style files."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from . import style_manager


class StyleDialog(QDialog):
    """Lists bundled and user style files, lets users import new ones."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage LaTeX styles")
        self.resize(700, 500)

        # ---- info label ---------------------------------------------------
        info = QLabel(
            "<b>Bundled styles</b> ship with kherveDOC and are always "
            "available. <b>User styles</b> are files you imported — they "
            "live in a personal folder and survive app updates.<br><br>"
            "Any <code>.cls</code> (document class), <code>.sty</code> "
            "(package) or <code>.bst</code> (bibliography style) file "
            "placed here is found automatically by the LaTeX compiler."
        )
        info.setWordWrap(True)

        # ---- table --------------------------------------------------------
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["File", "Type", "Location", "Path"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.Interactive)
        hdr.setSectionResizeMode(3, QHeaderView.Interactive)
        hdr.resizeSection(1, 60)
        hdr.resizeSection(2, 80)
        hdr.resizeSection(3, 200)
        self._table.currentCellChanged.connect(self._on_selection)

        # ---- buttons ------------------------------------------------------
        self._btn_import = QPushButton("Import style file…")
        self._btn_import.setToolTip(
            "Copy a .cls, .sty or .bst file into your user styles folder")
        self._btn_import.clicked.connect(self._import)

        self._btn_remove = QPushButton("Remove")
        self._btn_remove.setToolTip("Remove the selected user style file")
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove)

        self._btn_open_folder = QPushButton("Open styles folder")
        self._btn_open_folder.setToolTip(
            "Open the user styles folder in the file explorer")
        self._btn_open_folder.clicked.connect(self._open_folder)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn_import)
        btn_row.addWidget(self._btn_remove)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_open_folder)

        # ---- paths label --------------------------------------------------
        bundled = style_manager.bundled_styles_dir()
        user = style_manager.user_styles_dir()
        paths_label = QLabel(
            f"<span style='color:#666;font-size:9pt;'>"
            f"Bundled: <code>{bundled}</code><br>"
            f"User: <code>{user}</code></span>")
        paths_label.setWordWrap(True)
        paths_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # ---- layout -------------------------------------------------------
        lay = QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self._table, 1)
        lay.addLayout(btn_row)
        lay.addWidget(paths_label)

        self._refresh()

    # ---- data -------------------------------------------------------------

    def _refresh(self) -> None:
        self._table.setRowCount(0)
        self._entries: list[dict] = []

        for s in style_manager.list_styles(style_manager.user_styles_dir()):
            s["location"] = "User"
            self._entries.append(s)
        for s in style_manager.list_styles(style_manager.bundled_styles_dir()):
            s["location"] = "Bundled"
            self._entries.append(s)

        for row, e in enumerate(self._entries):
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(e["name"]))
            ext_label = {".cls": "Class", ".sty": "Package",
                         ".bst": "Bib style"}.get(e["ext"], e["ext"])
            self._table.setItem(row, 1, QTableWidgetItem(ext_label))
            loc_item = QTableWidgetItem(e["location"])
            if e["location"] == "Bundled":
                loc_item.setForeground(Qt.gray)
            self._table.setItem(row, 2, loc_item)
            self._table.setItem(row, 3, QTableWidgetItem(str(e["path"])))
        self._table.resizeRowsToContents()
        self._on_selection()

    def _on_selection(self, *_) -> None:
        row = self._table.currentRow()
        can_remove = (0 <= row < len(self._entries)
                      and self._entries[row]["location"] == "User")
        self._btn_remove.setEnabled(can_remove)

    # ---- actions ----------------------------------------------------------

    def _import(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import style files",
            "",
            "LaTeX style files (*.cls *.sty *.bst);;All files (*)")
        if not paths:
            return
        imported: list[str] = []
        for p in paths:
            src = Path(p)
            if src.suffix.lower() not in (".cls", ".sty", ".bst"):
                QMessageBox.warning(
                    self, "Skipped",
                    f"{src.name} is not a .cls, .sty or .bst file — skipped.")
                continue
            dest = style_manager.import_style(src)
            imported.append(dest.name)
        if imported:
            self._refresh()
            QMessageBox.information(
                self, "Imported",
                f"Imported {len(imported)} file(s):\n"
                + "\n".join(f"  • {n}" for n in imported))

    def _remove(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        e = self._entries[row]
        if e["location"] != "User":
            QMessageBox.information(
                self, "Cannot remove",
                "Bundled styles cannot be removed — they ship with "
                "kherveDOC.")
            return
        reply = QMessageBox.question(
            self, "Remove style",
            f"Remove <b>{e['name']}</b> from your user styles?")
        if reply != QMessageBox.Yes:
            return
        style_manager.remove_style(e["path"])
        self._refresh()

    def _open_folder(self) -> None:
        folder = str(style_manager.user_styles_dir())
        if sys.platform == "win32":
            subprocess.Popen(["explorer", folder])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
