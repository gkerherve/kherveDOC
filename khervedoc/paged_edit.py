"""QTextEdit subclass that paints visible page-break lines.

The text content still flows as a single editable surface — properly
splitting the document into separate page widgets would require a custom
text-document layout, which is much larger work. The page-break overlay
draws horizontal dashed lines at each page boundary computed from the
QTextDocument's pagination, giving users immediate feedback about how
their content will be paginated in the PDF.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSizeF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QTextEdit, QWidget


class _PageBreakOverlay(QWidget):
    """Transparent child of the viewport that paints page-break lines."""

    def __init__(self, edit: "PagedTextEdit"):
        super().__init__(edit.viewport())
        self._edit = edit
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # Without this the overlay would paint its own background on top of
        # the QTextEdit's content (covering the text).
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        edit.viewport().installEventFilter(self)
        self.resize(edit.viewport().size())
        self.raise_()

    def eventFilter(self, obj, event):
        if obj is self._edit.viewport():
            if event.type() == QEvent.Resize:
                self.resize(self._edit.viewport().size())
            elif event.type() == QEvent.Paint:
                # Schedule a repaint after the viewport finishes painting.
                self.update()
        return False

    def paintEvent(self, ev):
        page_h = self._edit.page_height_px()
        if page_h <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        pen = QPen(QColor(140, 70, 50, 180), 1, Qt.DashLine)
        painter.setPen(pen)
        # The QTextEdit no longer scrolls internally (the outer QScrollArea
        # owns scrolling), so the viewport top corresponds to the document
        # top. Lines sit at multiples of page_h.
        scroll_y = self._edit.verticalScrollBar().value()
        h = self.height()
        w = self.width()
        n = 1
        while True:
            y_doc = n * page_h
            y_vp = int(y_doc - scroll_y)
            if y_vp > h + page_h:
                break
            if 0 <= y_vp <= h:
                painter.drawLine(6, y_vp, w - 6, y_vp)
                painter.drawText(8, y_vp - 4, f"— page {n} / {n + 1} —")
            n += 1
        painter.end()


class PagedTextEdit(QTextEdit):
    """A QTextEdit that knows its page size and draws page-break lines."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._page_height_px = 0
        self._page_width_px = 0
        self._overlay = _PageBreakOverlay(self)

    def page_height_px(self) -> int:
        return self._page_height_px

    def set_page_size_px(self, width_px: int, height_px: int) -> None:
        """Set the document's pagination size in pixels."""
        self._page_width_px = width_px
        self._page_height_px = height_px
        # QTextDocument.setPageSize tells the layout engine where to break
        # pages — value is in the same units as the document's pixel-size.
        self.document().setPageSize(QSizeF(width_px, height_px))
        self._overlay.update()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._overlay.resize(self.viewport().size())
