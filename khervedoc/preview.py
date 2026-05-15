"""PDF preview pane — vertical scroll of rasterised pages."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QLabel, QScrollArea, QVBoxLayout, QWidget, QSizePolicy,
)

from .compiler import render_pdf_pages


class PdfPreview(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        # Light grey backdrop so the white PDF pages still have visible edges.
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

    def show_message(self, msg: str) -> None:
        self._status.setText(msg)
        self._clear_pages()

    def show_pdf(self, pdf_path: Path, dpi: int = 144) -> None:
        try:
            pages = render_pdf_pages(pdf_path, dpi=dpi)
        except Exception as exc:
            self.show_message(f"Preview error: {exc}")
            return
        if not pages:
            self.show_message("Compiled PDF has no pages.")
            return
        self._clear_pages()
        for page in pages:
            img = QImage(page.rgb, page.width, page.height, page.stride, QImage.Format_RGB888)
            # Copy so the QImage owns its buffer (the source bytes object can
            # be garbage-collected once this function returns).
            img = img.copy()
            label = QLabel(self._inner)
            label.setPixmap(QPixmap.fromImage(img))
            label.setAlignment(Qt.AlignHCenter)
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            label.setStyleSheet("background: white; border: 1px solid #888;")
            # Insert before the stretch.
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, label)
        self._status.setText(f"{len(pages)} page(s) — {pdf_path.name}")

    def _clear_pages(self) -> None:
        # Remove every widget except the trailing stretch item.
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
