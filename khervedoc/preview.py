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
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget


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
        self._fit_to_width = True
        self._current_pdf: Path | None = None
        self._extra_context_actions: list[tuple[str, object]] = []

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
            self._view.setContextMenuPolicy(Qt.CustomContextMenu)
            self._view.customContextMenuRequested.connect(
                self._show_context_menu)
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
        if self._fit_to_width:
            self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        else:
            self._view.setZoomFactor(self._zoom_percent / 100.0)
        self._status.hide()
        # Restore after Qt lays out the new document.
        if saved_scroll:
            QTimer.singleShot(0, lambda: vbar.setValue(saved_scroll))

    def set_zoom_percent(self, percent: int) -> None:
        self._zoom_percent = max(25, min(400, int(percent)))
        self._fit_to_width = False
        if _QTPDF_AVAILABLE and self._view is not None:
            self._view.setZoomMode(QPdfView.ZoomMode.Custom)
            self._view.setZoomFactor(self._zoom_percent / 100.0)

    def set_fit_to_width(self, enabled: bool) -> None:
        self._fit_to_width = enabled
        if enabled and _QTPDF_AVAILABLE and self._view is not None:
            self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def fit_to_width(self) -> bool:
        return self._fit_to_width

    def zoom_percent(self) -> int:
        return self._zoom_percent

    def current_page(self) -> int:
        """Return the 0-based page index currently most visible."""
        if not _QTPDF_AVAILABLE or self._view is None:
            return 0
        nav = self._view.pageNavigator()
        return nav.currentPage() if nav else 0

    def go_to_page(self, page: int) -> None:
        """Scroll to the given 0-based page."""
        if not _QTPDF_AVAILABLE or self._view is None:
            return
        n = self._doc.pageCount()
        if n < 1 or page < 0:
            return
        page = min(page, n - 1)
        # Compute the vertical offset by summing page heights (in points,
        # scaled by the current zoom factor) plus inter-page spacing.
        zoom = self._view.zoomFactor()
        spacing = self._view.pageSpacing()
        y = 0.0
        for i in range(page):
            size = self._doc.pagePointSize(i)
            y += size.height() * zoom + spacing
        vbar = self._view.verticalScrollBar()
        if vbar:
            vbar.setValue(int(y))

    def page_count(self) -> int:
        if not _QTPDF_AVAILABLE:
            return 0
        return self._doc.pageCount()

    def _show_context_menu(self, pos) -> None:
        if not self._extra_context_actions:
            return
        menu = QMenu(self)
        for label, callback in self._extra_context_actions:
            menu.addAction(label, callback)
        menu.exec(self._view.viewport().mapToGlobal(pos))
