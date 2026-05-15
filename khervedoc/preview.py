"""PDF preview pane — vertical scroll of rasterised pages with live zoom."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .compiler import render_pdf_pages

# Base DPI used to rasterise each page. The zoom factor multiplies this so
# 100% zoom looks crisp on most monitors; >100% raises DPI for sharper
# zoomed-in viewing, <100% drops DPI to keep the redraw cheap.
_BASE_DPI = 144


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
            label.setStyleSheet("background: white; border: 1px solid #888;")
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, label)
        self._status.setText(
            f"{len(pages)} page(s) — {self._current_pdf.name}  "
            f"@ {self._zoom_percent}%")

    def _clear_pages(self) -> None:
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
