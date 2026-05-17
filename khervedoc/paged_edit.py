"""QTextEdit subclass that paints visible page-break lines.

The text content still flows as a single editable surface — properly
splitting the document into separate page widgets would require a custom
text-document layout, which is much larger work. The page-break overlay
draws horizontal dashed lines at each page boundary computed from the
QTextDocument's pagination, giving users immediate feedback about how
their content will be paginated in the PDF.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QTextEdit, QWidget


_IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".svg",
}


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
        # Preferred: use the *actual* PDF page count from the last
        # compile to distribute break lines across the editor's content
        # height. This is far more accurate than the static page-height
        # heuristic because LaTeX's text density (font, margins,
        # spacing) doesn't match Qt's QTextEdit defaults. With this,
        # the page-N marker in the editor lines up with where page N
        # actually breaks in the compiled PDF.
        pdf_pages = self._edit.pdf_page_count()
        doc_h = int(self._edit.document().size().height())
        if pdf_pages >= 2 and doc_h > 0:
            spacing = doc_h / pdf_pages
            total_pages = pdf_pages
            mode = "compiled"
        else:
            spacing = float(self._edit.page_height_px())
            total_pages = None
            mode = "estimate"
        if spacing <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        pen = QPen(QColor(140, 70, 50, 180), 1, Qt.DashLine)
        painter.setPen(pen)
        scroll_y = self._edit.verticalScrollBar().value()
        h = self.height()
        w = self.width()
        n = 1
        while True:
            y_doc = n * spacing
            y_vp = int(y_doc - scroll_y)
            if y_vp > h + spacing:
                break
            if total_pages is not None and n >= total_pages:
                # Don't draw a "page N / N+1" line past the last PDF page —
                # the document just ends there.
                break
            if 0 <= y_vp <= h:
                painter.drawLine(6, y_vp, w - 6, y_vp)
                label = (f"— page {n} / {n + 1} —" if mode == "compiled"
                         else f"— page {n} / {n + 1} (estimate) —")
                painter.drawText(8, y_vp - 4, label)
            n += 1
        painter.end()


class PagedTextEdit(QTextEdit):
    """A QTextEdit that knows its page size, draws page-break lines and
    accepts pasted/dropped images.

    Image handling: when the user pastes from the clipboard or drops one
    or more image files onto the editor, each image is saved into the
    working images directory (set via `set_images_dir`) and an
    `imageReceived(str)` signal is emitted carrying the saved path. The
    DocumentEditor wires this up to insert a Figure block at the cursor.
    """

    imageReceived = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._page_height_px = 0
        self._page_width_px = 0
        # Number of pages in the most recent compiled PDF. The
        # overlay uses this (when >= 2) to position break lines
        # proportionally to the editor's actual content height —
        # much more accurate than the static page_height_px which
        # ignores LaTeX's text density. 0 = no compile yet → fall
        # back to the heuristic.
        self._pdf_page_count = 0
        self._images_dir: Path | None = None
        self._image_counter = 0
        self._overlay = _PageBreakOverlay(self)
        self.setAcceptDrops(True)

    def set_images_dir(self, path: Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self._images_dir = path

    def page_height_px(self) -> int:
        return self._page_height_px

    def pdf_page_count(self) -> int:
        return self._pdf_page_count

    def set_pdf_page_count(self, n: int) -> None:
        """Record the page count from the most recent successful PDF
        compile. The page-break overlay redraws using this to space
        its dashed indicator lines proportionally to the editor's
        content height. Called by MainWindow after each compile."""
        n = max(0, int(n))
        if n == self._pdf_page_count:
            return
        self._pdf_page_count = n
        self._overlay.update()

    def set_page_size_px(self, width_px: int, height_px: int) -> None:
        """Record the page dimensions used by the break-line overlay.

        We deliberately do NOT call QTextDocument.setPageSize: that forces
        document().size().height() to report a multiple of the page
        height even when the content is short, which made a brand-new
        document render as a fully-empty A4 sheet with the title floating
        in the middle. The page-break overlay paints its dashed indicator
        lines at multiples of page_height_px without help from the layout
        engine; the document itself flows as one continuous sheet that
        grows with content.
        """
        self._page_width_px = width_px
        self._page_height_px = height_px
        self._overlay.update()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._overlay.resize(self.viewport().size())

    # ----- paste / drop: route images through imageReceived signal -----

    def canInsertFromMimeData(self, source) -> bool:
        if source.hasImage():
            return True
        if source.hasUrls():
            for u in source.urls():
                local = u.toLocalFile()
                if local and Path(local).suffix.lower() in _IMAGE_SUFFIXES:
                    return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:
        # Clipboard-image case: e.g. Snipping Tool, screenshots, Slack pastes.
        if source.hasImage():
            img = source.imageData()
            if isinstance(img, QImage) and not img.isNull():
                path = self._save_qimage(img)
                if path is not None:
                    self.imageReceived.emit(str(path))
                    return
        # File-URL case: Explorer drag-and-drop or copy from another app.
        if source.hasUrls():
            handled = False
            for u in source.urls():
                local = u.toLocalFile()
                if local and Path(local).suffix.lower() in _IMAGE_SUFFIXES:
                    path = self._copy_local(Path(local))
                    if path is not None:
                        self.imageReceived.emit(str(path))
                        handled = True
            if handled:
                return
        super().insertFromMimeData(source)

    def _next_image_filename(self, suffix: str) -> Path | None:
        if self._images_dir is None:
            return None
        suffix = suffix.lower() or ".png"
        while True:
            self._image_counter += 1
            candidate = self._images_dir / f"img_{self._image_counter:03d}{suffix}"
            if not candidate.exists():
                return candidate

    def _save_qimage(self, img: QImage) -> Path | None:
        path = self._next_image_filename(".png")
        if path is None:
            return None
        # PNG keeps clipboard quality without compression artefacts; tectonic
        # has no problem with it via \includegraphics.
        if img.save(str(path), "PNG"):
            return path
        return None

    def _copy_local(self, src: Path) -> Path | None:
        path = self._next_image_filename(src.suffix)
        if path is None:
            return None
        try:
            shutil.copy(src, path)
        except OSError:
            return None
        return path
