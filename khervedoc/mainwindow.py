"""Main application window: editor pane | preview pane, plus File menu."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox, QSplitter, QStatusBar,
    QWidget,
)

from . import git_backend
from .compiler import CompileResult, compile_tex, tectonic_available
from .editor import DocumentEditor
from .model import Document, DocMeta, Paragraph, Section, Text, from_json, to_json
from .preview import PdfPreview
from .serializer import serialize_document


class _CompileWorker(QThread):
    """Compiles LaTeX off the GUI thread so the editor stays responsive."""
    finished_with = Signal(object)  # CompileResult

    def __init__(self, tex_source: str, workdir: Path):
        super().__init__()
        self._tex = tex_source
        self._workdir = workdir

    def run(self) -> None:
        result = compile_tex(self._tex, self._workdir)
        self.finished_with.emit(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("kherveDOC")
        # Size to ~80% of the available screen and centre, so the title bar
        # is never above the visible area regardless of DPI/multi-monitor setup.
        screen = QGuiApplication.primaryScreen().availableGeometry()
        w = min(1400, int(screen.width() * 0.85))
        h = min(900, int(screen.height() * 0.85))
        self.resize(w, h)
        self.move(screen.x() + (screen.width() - w) // 2,
                  screen.y() + (screen.height() - h) // 2)

        self._current_path: Path | None = None  # path to .kdoc.json on disk
        self._build_dir = Path(tempfile.mkdtemp(prefix="khervedoc-"))
        self._compile_worker: _CompileWorker | None = None
        self._pending_recompile = False

        self._editor = DocumentEditor(self)
        self._preview = PdfPreview(self)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._editor)
        splitter.addWidget(self._preview)
        splitter.setSizes([700, 700])
        self.setCentralWidget(splitter)

        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._tectonic_label = QLabel(
            "tectonic: OK" if tectonic_available() else "tectonic: NOT FOUND — preview disabled",
            self,
        )
        self._status.addPermanentWidget(self._tectonic_label)

        self._make_menus()
        self._editor.documentChanged.connect(self._on_doc_changed)

        self._editor.set_document(_starter_document())
        self._kick_compile()

    # ----- menus -----

    def _make_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        new_act = QAction("&New", self, shortcut=QKeySequence.New, triggered=self._new)
        open_act = QAction("&Open...", self, shortcut=QKeySequence.Open, triggered=self._open)
        save_act = QAction("&Save", self, shortcut=QKeySequence.Save, triggered=self._save)
        save_as_act = QAction("Save &As...", self, shortcut=QKeySequence.SaveAs, triggered=self._save_as)
        export_tex = QAction("Export .tex...", self, triggered=self._export_tex)
        export_pdf = QAction("Export .pdf...", self, triggered=self._export_pdf)
        quit_act = QAction("&Quit", self, shortcut=QKeySequence.Quit, triggered=self.close)

        for a in (new_act, open_act, save_act, save_as_act):
            file_menu.addAction(a)
        file_menu.addSeparator()
        for a in (export_tex, export_pdf):
            file_menu.addAction(a)
        file_menu.addSeparator()
        file_menu.addAction(quit_act)

        history_menu = self.menuBar().addMenu("&History")
        history_menu.addAction(QAction("Show commit log...", self, triggered=self._show_history))

    # ----- file ops -----

    def _new(self) -> None:
        self._current_path = None
        self._editor.set_document(_starter_document())
        self.setWindowTitle("kherveDOC — Untitled")

    def _open(self) -> None:
        path_s, _ = QFileDialog.getOpenFileName(
            self, "Open document", "", "kherveDOC documents (*.kdoc.json);;All files (*)")
        if not path_s:
            return
        path = Path(path_s)
        try:
            doc = from_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._current_path = path
        self._editor.set_document(doc)
        self.setWindowTitle(f"kherveDOC — {path.name}")

    def _save(self) -> None:
        if self._current_path is None:
            self._save_as()
            return
        self._write_to(self._current_path)

    def _save_as(self) -> None:
        path_s, _ = QFileDialog.getSaveFileName(
            self, "Save document", "document.kdoc.json",
            "kherveDOC documents (*.kdoc.json)")
        if not path_s:
            return
        path = Path(path_s)
        if not path.name.endswith(".kdoc.json"):
            path = path.with_name(path.stem + ".kdoc.json")
        self._current_path = path
        self.setWindowTitle(f"kherveDOC — {path.name}")
        self._write_to(path)

    def _write_to(self, path: Path) -> None:
        doc = self._editor.get_document()
        json_text = to_json(doc)
        tex_text = serialize_document(doc)
        path.write_text(json_text, encoding="utf-8")
        tex_path = path.with_suffix("").with_suffix(".tex")  # strips .json then .kdoc
        # Above suffix gymnastics: turn foo.kdoc.json -> foo.tex.
        tex_path = path.parent / (path.name.replace(".kdoc.json", "") + ".tex")
        tex_path.write_text(tex_text, encoding="utf-8")

        # Auto-commit to per-document repo.
        repo_dir = path.parent
        commit_msg = f"Save {path.name} at {datetime.now().isoformat(timespec='seconds')}"
        if git_backend.is_available():
            git_backend.init_repo(repo_dir)
            oid = git_backend.commit_all(repo_dir, commit_msg)
            if oid:
                self._status.showMessage(f"Saved + committed {oid[:8]}", 4000)
            else:
                self._status.showMessage("Saved (no git changes)", 4000)
        else:
            self._status.showMessage("Saved (pygit2 unavailable — no commit)", 4000)

    def _export_tex(self) -> None:
        path_s, _ = QFileDialog.getSaveFileName(
            self, "Export LaTeX", "document.tex", "LaTeX (*.tex)")
        if not path_s:
            return
        Path(path_s).write_text(
            serialize_document(self._editor.get_document()), encoding="utf-8")

    def _export_pdf(self) -> None:
        if not tectonic_available():
            QMessageBox.warning(self, "tectonic missing",
                                "Install tectonic to export PDF.")
            return
        path_s, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "document.pdf", "PDF (*.pdf)")
        if not path_s:
            return
        result = compile_tex(serialize_document(self._editor.get_document()),
                             self._build_dir)
        if result.ok and result.pdf_path is not None:
            Path(path_s).write_bytes(result.pdf_path.read_bytes())
            self._status.showMessage(f"Exported {path_s}", 4000)
        else:
            QMessageBox.critical(self, "Compile failed",
                                 result.error or "Unknown error")

    def _show_history(self) -> None:
        if self._current_path is None:
            QMessageBox.information(self, "History", "Save the document first.")
            return
        rows = git_backend.history(self._current_path.parent)
        if not rows:
            QMessageBox.information(self, "History", "No commits yet.")
            return
        text = "\n".join(f"{oid}  {ts}  {msg}" for oid, ts, msg in rows)
        QMessageBox.information(self, "Commit history", text)

    # ----- compile loop -----

    def _on_doc_changed(self) -> None:
        self._kick_compile()

    def _kick_compile(self) -> None:
        if not tectonic_available():
            self._preview.show_message(
                "tectonic not installed — install it to see a live preview.")
            return
        if self._compile_worker is not None and self._compile_worker.isRunning():
            # Coalesce: remember to recompile when current job finishes.
            self._pending_recompile = True
            return
        tex = serialize_document(self._editor.get_document())
        self._compile_worker = _CompileWorker(tex, self._build_dir)
        self._compile_worker.finished_with.connect(self._on_compile_done)
        self._compile_worker.start()
        self._status.showMessage("Compiling...", 0)

    def _on_compile_done(self, result: CompileResult) -> None:
        self._status.clearMessage()
        if result.ok and result.pdf_path is not None:
            self._preview.show_pdf(result.pdf_path)
        else:
            tail = "\n".join(result.log.splitlines()[-8:]) if result.log else ""
            self._preview.show_message(f"{result.error}\n\n{tail}")
        self._compile_worker = None
        if self._pending_recompile:
            self._pending_recompile = False
            self._kick_compile()


def _starter_document() -> Document:
    return Document(
        meta=DocMeta(title="Untitled", author=""),
        children=[
            Section(level=1, children=[Text(text="Welcome to kherveDOC")]),
            Paragraph(children=[
                Text(text="Type here. Use the toolbar to set headings, "),
                Text(text="bold", marks=["bold"]),
                Text(text=" / "),
                Text(text="italic", marks=["italic"]),
                Text(text=" text, or insert math with Ctrl+M."),
            ]),
        ],
    )
