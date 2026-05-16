"""PDF preview pane backed by Qt's own QPdfView.

Previously we rasterised every page to a QImage and wrapped each one in
a QLabel; that always looked flat because it was, literally, a PNG on a
grey background. QPdfView renders the actual PDF — with proper page
shadows, smooth scrolling, anti-aliased text — and integrates with the
status-bar zoom slider via setZoomFactor.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    _QTPDF_AVAILABLE = True
except ImportError:                           # pragma: no cover
    QPdfDocument = None                       # type: ignore
    QPdfView = None                           # type: ignore
    _QTPDF_AVAILABLE = False


class PdfPreview(QWidget):
    """Embedded PDF viewer with a status header and live zoom."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._zoom_percent = 100
        self._current_pdf: Path | None = None

        self._status = QLabel("No preview yet — start typing to compile.", self)
        self._status.setStyleSheet(
            "color: #333; padding: 8px; background: #f0f0f0; "
            "border-bottom: 1px solid #c0c0c0;")
        self._status.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._status)

        if _QTPDF_AVAILABLE:
            self._doc = QPdfDocument(self)
            self._view = QPdfView(self)
            self._view.setDocument(self._doc)
            self._view.setPageMode(QPdfView.PageMode.MultiPage)
            self._view.setZoomMode(QPdfView.ZoomMode.Custom)
            self._view.setZoomFactor(1.0)
            # Page spacing — the gap rendered between consecutive pages
            # in MultiPage mode. Qt's default is 3 px which is too tight
            # to read as "next sheet of paper".
            self._view.setPageSpacing(18)
            layout.addWidget(self._view, 1)
        else:
            # Defensive fallback message. PySide6 6.4+ ships QtPdf with
            # the Essentials install, so this branch shouldn't trigger in
            # practice — but if someone strips down their wheel we tell
            # them what to install rather than crashing.
            self._view = None
            fallback = QLabel(
                "PDF preview needs QtPdf / QtPdfWidgets.\n"
                "Try:  pip install --upgrade PySide6 PySide6-Addons", self)
            fallback.setAlignment(Qt.AlignCenter)
            fallback.setWordWrap(True)
            layout.addWidget(fallback, 1)

    # ----- public API (unchanged contract with MainWindow) -----

    def show_message(self, msg: str) -> None:
        self._status.setText(msg)
        if _QTPDF_AVAILABLE and self._view is not None:
            # Close any document so the viewer area goes blank rather
            # than leaving stale pages behind a compile-error message.
            self._doc.close()
            self._current_pdf = None

    def show_pdf(self, pdf_path: Path) -> None:
        if not _QTPDF_AVAILABLE or self._view is None:
            return
        self._current_pdf = Path(pdf_path)
        self._doc.close()
        self._doc.load(str(pdf_path))
        # Honour the current zoom; QPdfView resets to its own default
        # after a load, which would override the slider position.
        self._view.setZoomFactor(self._zoom_percent / 100.0)
        self._update_status()

    def set_zoom_percent(self, percent: int) -> None:
        self._zoom_percent = max(25, min(400, int(percent)))
        if _QTPDF_AVAILABLE and self._view is not None:
            self._view.setZoomMode(QPdfView.ZoomMode.Custom)
            self._view.setZoomFactor(self._zoom_percent / 100.0)
            self._update_status()

    def zoom_percent(self) -> int:
        return self._zoom_percent

    # ----- internals -----

    def _update_status(self) -> None:
        if not _QTPDF_AVAILABLE or self._view is None or self._current_pdf is None:
            return
        n = self._doc.pageCount()
        paper = "?"
        if n > 0:
            size_pt = self._doc.pagePointSize(0)
            w_in = size_pt.width() / 72.0
            h_in = size_pt.height() / 72.0
            paper = self._guess_paper_name(w_in, h_in)
        self._status.setText(
            f"{n} page(s) — {self._current_pdf.name} — {paper} "
            f"@ {self._zoom_percent}%")

    @staticmethod
    def _guess_paper_name(w_in: float, h_in: float) -> str:
        def near(a, b): return abs(a - b) < 0.1
        if near(w_in, 8.27) and near(h_in, 11.69): return "A4"
        if near(w_in, 8.5) and near(h_in, 11.0):   return "Letter"
        if near(w_in, 8.5) and near(h_in, 14.0):   return "Legal"
        return f"{w_in:.1f}\" × {h_in:.1f}\""
