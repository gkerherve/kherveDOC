"""PDF preview pane — vertical scroll of rasterised pages with live zoom."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from .compiler import render_pdf_pages

# Base DPI used to rasterise each page at 100% zoom. 96 makes an A4 page
# 794x1122 px, which fits in the preview pane on a typical 1080p display
# without forcing horizontal scrolling. Users wanting a sharper view can
# zoom up via the status-bar slider — set_zoom_percent re-rasterises at
# the matching DPI.
_BASE_DPI = 96


class PdfPreview(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._zoom_percent = 100
        self._current_pdf: Path | None = None

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self._scroll.setStyleSheet(
            "QScrollArea { background: #d0d4d8; border: none; }")

        self._inner = QWidget()
        self._inner.setStyleSheet("background: #d0d4d8;")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(20, 20, 20, 20)
        self._inner_layout.setSpacing(16)
        self._inner_layout.addStretch(1)
        self._scroll.setWidget(self._inner)

        self._status = QLabel("No preview yet — start typing to compile.", self)
        self._status.setStyleSheet(
            "color: #333; padding: 8px; background: #f0f0f0; "
            "border-bottom: 1px solid #c0c0c0;")
        self._status.setAlignment(Qt.AlignCenter)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._status)
        outer.addWidget(self._scroll, 1)

    # ----- public -----

    def show_message(self, msg: str) -> None:
        self._status.setText(msg)
        self._clear_pages()

    def show_pdf(self, pdf_path: Path) -> None:
        self._current_pdf = pdf_path
        self._render_at_current_zoom()

    def set_zoom_percent(self, percent: int) -> None:
        percent = max(25, min(400, int(percent)))
        if percent == self._zoom_percent:
            return
        self._zoom_percent = percent
        if self._current_pdf is not None:
            self._render_at_current_zoom()

    def zoom_percent(self) -> int:
        return self._zoom_percent

    # ----- internals -----

    def _render_at_current_zoom(self) -> None:
        if self._current_pdf is None:
            return
        dpi = max(36, round(_BASE_DPI * self._zoom_percent / 100))
        try:
            pages = render_pdf_pages(self._current_pdf, dpi=dpi)
        except Exception as exc:
            self.show_message(f"Preview error: {exc}")
            return
        if not pages:
            self.show_message("Compiled PDF has no pages.")
            return
        self._clear_pages()
        for page in pages:
            img = QImage(page.rgb, page.width, page.height, page.stride,
                         QImage.Format_RGB888).copy()
            label = QLabel(self._inner)
            label.setPixmap(QPixmap.fromImage(img))
            label.setAlignment(Qt.AlignHCenter)
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            label.setStyleSheet("background: white; border: 1px solid #b8bcc1;")
            # Drop shadow so each page reads as a sheet of paper on the desk
            # instead of a flat rectangle drifting in grey space.
            shadow = QGraphicsDropShadowEffect(label)
            shadow.setBlurRadius(18)
            shadow.setOffset(0, 3)
            shadow.setColor(QColor(0, 0, 0, 110))
            label.setGraphicsEffect(shadow)
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, label)
        # Tell the user what they're looking at — page count, paper size from
        # the first page's dimensions in inches, and the active zoom.
        first = pages[0]
        in_w = first.width / max(1, _BASE_DPI * self._zoom_percent / 100)
        in_h = first.height / max(1, _BASE_DPI * self._zoom_percent / 100)
        paper = self._guess_paper_name(in_w, in_h)
        self._status.setText(
            f"{len(pages)} page(s) — {self._current_pdf.name}  "
            f"— {paper}  @ {self._zoom_percent}%")

    @staticmethod
    def _guess_paper_name(width_in: float, height_in: float) -> str:
        """Map physical dimensions back to a friendly paper name. Tolerance
        of 0.05 inches absorbs small rounding from the rasteriser."""
        def near(a, b): return abs(a - b) < 0.1
        if near(width_in, 8.27) and near(height_in, 11.69): return "A4"
        if near(width_in, 8.5) and near(height_in, 11.0):   return "Letter"
        if near(width_in, 8.5) and near(height_in, 14.0):   return "Legal"
        return f"{width_in:.1f}\" × {height_in:.1f}\""

    def _clear_pages(self) -> None:
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
