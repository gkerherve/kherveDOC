"""PDF preview pane backed by Qt's own QPdfView.

Previously we rasterised every page to a QImage and wrapped each one in
a QLabel; that always looked flat because it was, literally, a PNG on a
grey background. QPdfView renders the actual PDF — with proper page
shadows, smooth scrolling, anti-aliased text — and integrates with the
status-bar zoom slider via setZoomFactor.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
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

        self._status = QLabel(self)
        self._status.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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
        self._status.setStyleSheet(
            "color: #333; padding: 8px; background: #f0f0f0; "
            "border-bottom: 1px solid #c0c0c0;")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.show()
        if _QTPDF_AVAILABLE and self._view is not None:
            self._doc.close()
            self._current_pdf = None

    def show_pdf(self, pdf_path: Path) -> None:
        if not _QTPDF_AVAILABLE or self._view is None:
            return
        # Remember scroll position so a recompile doesn't jump to the top.
        vbar = self._view.verticalScrollBar()
        saved_scroll = vbar.value() if vbar else 0
        self._current_pdf = Path(pdf_path)
        self._doc.close()
        self._doc.load(str(pdf_path))
        self._view.setZoomFactor(self._zoom_percent / 100.0)
        self._status.hide()
        # Restore after Qt lays out the new document.
        if saved_scroll:
            QTimer.singleShot(0, lambda: vbar.setValue(saved_scroll))

    def set_zoom_percent(self, percent: int) -> None:
        self._zoom_percent = max(25, min(400, int(percent)))
        if _QTPDF_AVAILABLE and self._view is not None:
            self._view.setZoomMode(QPdfView.ZoomMode.Custom)
            self._view.setZoomFactor(self._zoom_percent / 100.0)

    def zoom_percent(self) -> int:
        return self._zoom_percent
