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
_DOCUMENT_SUFFIXES = {
    ".kdocz", ".ktexz", ".tex", ".md", ".markdown", ".docx",
}


def _is_document_file(p: Path) -> bool:
    name = p.name.lower()
    if name.endswith(".kdoc.json") or name.endswith(".ktex.json"):
        return True
    return p.suffix.lower() in _DOCUMENT_SUFFIXES


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
        # Preferred path: the compiler hands us a list of "first text
        # of each PDF page" anchors (page_no, y_doc_pixels). We
        # painted those by finding each snippet in the editor and
        # recording the Y position of its block. That maps the
        # editor's pagination 1:1 to the PDF's, even when LaTeX's
        # text density (title block, abstract, floats) means the
        # break is nowhere near halfway through the editor content.
        anchors = self._edit.page_anchor_positions()
        if anchors:
            self._paint_anchored(anchors)
            return
        # Fallback: even spacing using doc_height / pdf_page_count.
        # Used between compile attempts or when the snippet match
        # fails. Less accurate than the anchored path but better
        # than the static page_height_px from before.
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
                break
            if 0 <= y_vp <= h:
                painter.drawLine(6, y_vp, w - 6, y_vp)
                label = (f"— page {n} / {n + 1} —" if mode == "compiled"
                         else f"— page {n} / {n + 1} (estimate) —")
                painter.drawText(8, y_vp - 4, label)
            n += 1
        painter.end()

    def _paint_anchored(self,
                        anchors: list[tuple[int, float]]) -> None:
        """Draw one break line per anchor (page_no, y_doc). Each
        anchor is "page N starts at this Y pixel in the editor"."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        pen = QPen(QColor(140, 70, 50, 180), 1, Qt.DashLine)
        painter.setPen(pen)
        scroll_y = self._edit.verticalScrollBar().value()
        h = self.height()
        w = self.width()
        for page_no, y_doc in anchors:
            y_vp = int(y_doc - scroll_y)
            if y_vp < -20 or y_vp > h + 20:
                continue
            painter.drawLine(6, y_vp, w - 6, y_vp)
            painter.drawText(8, y_vp - 4,
                             f"— page {page_no - 1} / {page_no} —")
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
    documentDropped = Signal(str)

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
        # Raw [(page_no, snippet), ...] anchors handed in by the
        # compiler. Re-resolved into y-positions on every paint so
        # the lookup happens after the QTextDocument layout pass
        # has finished — resolving at set_page_anchors() time would
        # return y=0 for every anchor before the editor is shown.
        self._page_anchors: list[tuple[int, str]] = []
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

    def page_anchor_positions(self) -> list[tuple[int, float]]:
        """Lazily resolve the stored (page_no, snippet) anchors to
        (page_no, y_doc) on each request. Layout-dependent values
        like QTextLine geometry only become real after the editor
        has actually been painted, so we resolve at paint time
        rather than at set_page_anchors time.

        Returns the Y of the WRAPPED LINE the snippet sits on, not
        just the block top — that's the difference between "page
        break in the middle of this paragraph" (right) and "page
        break at the start of this paragraph" (wrong, what the
        previous version did)."""
        if not self._page_anchors:
            return []
        qdoc = self.document()
        layout = qdoc.documentLayout()
        resolved: list[tuple[int, float]] = []
        for page_no, snippet in self._page_anchors:
            key = (snippet or "").strip()[:24]
            if not key:
                continue
            block = qdoc.firstBlock()
            while block.isValid():
                text = block.text()
                idx = text.find(key)
                if idx >= 0:
                    block_rect = layout.blockBoundingRect(block)
                    if block_rect.height() > 0 or block_rect.top() > 0:
                        y_doc = block_rect.top()
                        # Refine with QTextLine: where inside this
                        # block is the matched substring drawn?
                        # A long paragraph that wraps over 5 lines
                        # in the editor needs the break line on the
                        # exact wrapped line that starts the PDF
                        # page, not the block's top.
                        blk_layout = block.layout()
                        if blk_layout is not None:
                            line = blk_layout.lineForTextPosition(idx)
                            if line.isValid():
                                y_doc = block_rect.top() + line.y()
                        resolved.append((int(page_no), float(y_doc)))
                    break
                block = block.next()
        return resolved

    def set_page_anchors(self,
                         anchors: list[tuple[int, str]]) -> None:
        """Receive [(page_no, first_text_snippet), ...] from the
        compiler. We store them as-is and resolve them to
        y-positions lazily on each paint (see
        `page_anchor_positions`)."""
        self._page_anchors = list(anchors or [])
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
                if not local:
                    continue
                p = Path(local)
                if p.suffix.lower() in _IMAGE_SUFFIXES:
                    path = self._copy_local(p)
                    if path is not None:
                        self.imageReceived.emit(str(path))
                        handled = True
                elif _is_document_file(p):
                    self.documentDropped.emit(local)
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
