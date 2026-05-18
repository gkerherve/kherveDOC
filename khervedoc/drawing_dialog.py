"""Freehand / shape drawing dialog.

Lets the user sketch a quick diagram inside the editor and have it
inserted as a Figure block — the figure path points at a PNG the
dialog wrote into the document's images folder, so \\includegraphics
in the compiled PDF picks it up automatically.

Tools: pen (freehand), straight line, rectangle, ellipse, arrow,
text caption, eraser. Plus an Undo button — the canvas keeps a
flat list of QGraphicsItems so undo just pops the last one off.

The whole dialog is a QGraphicsView over a QGraphicsScene; on
accept we render the scene into a QImage with white background
and save it as PNG. Nothing TikZ-specific; the resulting PDF is
identical no matter what LaTeX engine you compile with.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QAction, QActionGroup, QBrush, QColor, QFont, QImage, QKeySequence,
    QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QDialog, QDialogButtonBox, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsPathItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsTextItem, QGraphicsView, QHBoxLayout, QInputDialog, QLabel,
    QPushButton, QSlider, QToolBar, QToolButton, QVBoxLayout, QWidget,
)


# Pre-set colour palette — clicking a swatch sets the current pen.
_PALETTE = [
    "#000000",  # black
    "#1a6dd8",  # blue (KherveTeX accent)
    "#d8000c",  # red
    "#0a6f00",  # green
    "#d96b00",  # orange
    "#8e44ad",  # purple
    "#7a7a7a",  # grey
]


class _Canvas(QGraphicsView):
    """A QGraphicsView that builds items from mouse events according
    to the currently-selected tool."""

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.setBackgroundBrush(QBrush(QColor("white")))
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.NoDrag)
        self._tool = "pen"
        self._pen_color = QColor("#000000")
        self._pen_width = 2
        self._origin: QPointF | None = None
        self._active_item = None
        self._pen_path: QPainterPath | None = None
        # History stack for undo — we keep the actual QGraphicsItems so
        # we can put them back if we ever want redo. Drop or eraser
        # operations push (None, removed_items) so the user gets a
        # one-step undo from "I just erased that".
        self._history: list[list] = []

    # ----- tool / style accessors -------------------------------------

    def set_tool(self, tool: str) -> None:
        self._tool = tool

    def set_color(self, color: QColor) -> None:
        self._pen_color = color

    def set_width(self, width: int) -> None:
        self._pen_width = max(1, int(width))

    def _pen(self) -> QPen:
        pen = QPen(self._pen_color, self._pen_width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    # ----- mouse handling ---------------------------------------------

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return super().mousePressEvent(ev)
        scene_pos = self.mapToScene(ev.position().toPoint())
        if self._tool == "pen":
            self._pen_path = QPainterPath(scene_pos)
            self._active_item = QGraphicsPathItem(self._pen_path)
            self._active_item.setPen(self._pen())
            self.scene().addItem(self._active_item)
        elif self._tool == "line":
            self._origin = scene_pos
            self._active_item = QGraphicsLineItem(
                scene_pos.x(), scene_pos.y(),
                scene_pos.x(), scene_pos.y())
            self._active_item.setPen(self._pen())
            self.scene().addItem(self._active_item)
        elif self._tool == "rect":
            self._origin = scene_pos
            self._active_item = QGraphicsRectItem(
                QRectF(scene_pos, scene_pos))
            self._active_item.setPen(self._pen())
            self.scene().addItem(self._active_item)
        elif self._tool == "ellipse":
            self._origin = scene_pos
            self._active_item = QGraphicsEllipseItem(
                QRectF(scene_pos, scene_pos))
            self._active_item.setPen(self._pen())
            self.scene().addItem(self._active_item)
        elif self._tool == "arrow":
            self._origin = scene_pos
            self._active_item = QGraphicsPathItem()
            self._active_item.setPen(self._pen())
            self.scene().addItem(self._active_item)
        elif self._tool == "eraser":
            item = self.scene().itemAt(scene_pos, self.transform())
            if item is not None:
                self.scene().removeItem(item)
                self._history.append([("removed", item)])
        elif self._tool == "text":
            text, ok = QInputDialog.getText(self, "Add text", "Text:")
            if ok and text:
                item = QGraphicsTextItem(text)
                f = QFont("Arial")
                f.setPointSize(max(8, self._pen_width * 4))
                item.setFont(f)
                item.setDefaultTextColor(self._pen_color)
                item.setPos(scene_pos)
                self.scene().addItem(item)
                self._history.append([("added", item)])
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._active_item is None:
            return super().mouseMoveEvent(ev)
        scene_pos = self.mapToScene(ev.position().toPoint())
        if self._tool == "pen" and self._pen_path is not None:
            self._pen_path.lineTo(scene_pos)
            self._active_item.setPath(self._pen_path)
        elif self._tool == "line" and self._origin is not None:
            self._active_item.setLine(
                self._origin.x(), self._origin.y(),
                scene_pos.x(), scene_pos.y())
        elif self._tool in ("rect", "ellipse") and self._origin is not None:
            r = QRectF(self._origin, scene_pos).normalized()
            self._active_item.setRect(r)
        elif self._tool == "arrow" and self._origin is not None:
            self._active_item.setPath(
                self._arrow_path(self._origin, scene_pos))
        return super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._active_item is not None:
            self._history.append([("added", self._active_item)])
        self._active_item = None
        self._origin = None
        self._pen_path = None
        return super().mouseReleaseEvent(ev)

    def _arrow_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        """Straight line from start to end with a small triangular
        head at the end. Head size scales with pen width."""
        path = QPainterPath(start)
        path.lineTo(end)
        # Arrowhead
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length = math.hypot(dx, dy)
        if length < 1e-3:
            return path
        head_len = 6 + self._pen_width * 2
        ux, uy = dx / length, dy / length
        # Perpendicular for the wings
        px, py = -uy, ux
        base_x = end.x() - ux * head_len
        base_y = end.y() - uy * head_len
        wing_a = QPointF(base_x + px * head_len * 0.4,
                         base_y + py * head_len * 0.4)
        wing_b = QPointF(base_x - px * head_len * 0.4,
                         base_y - py * head_len * 0.4)
        path.moveTo(end)
        path.lineTo(wing_a)
        path.moveTo(end)
        path.lineTo(wing_b)
        return path

    # ----- history actions --------------------------------------------

    def undo(self) -> None:
        if not self._history:
            return
        last = self._history.pop()
        for action, item in last:
            if action == "added":
                self.scene().removeItem(item)
            elif action == "removed":
                self.scene().addItem(item)

    def clear_all(self) -> None:
        # Capture every current item so undo can put the page back.
        items = list(self.scene().items())
        for it in items:
            self.scene().removeItem(it)
        if items:
            self._history.append([("removed", it) for it in items])


class DrawingDialog(QDialog):
    """Modal dialog: draw something, click OK, get a PNG path back.

    The PNG is written into `images_dir` so the inserted Figure
    block's `\\includegraphics{...}` path resolves both in the
    editor's preview and in any downstream LaTeX build."""

    drawingSaved = Signal(str)   # absolute path to the saved PNG

    def __init__(self, images_dir: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Drawing")
        self.resize(900, 660)
        self._images_dir = Path(images_dir)
        self._images_dir.mkdir(parents=True, exist_ok=True)
        self._saved_path: Path | None = None

        # ---- canvas ------------------------------------------------------
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(0, 0, 1200, 800)
        self._canvas = _Canvas(self._scene, self)

        # ---- tool toolbar ------------------------------------------------
        tb = QToolBar(self)
        tb.setIconSize(tb.iconSize())
        self._tool_group = QActionGroup(self)
        self._tool_group.setExclusive(True)
        for name, label in (
            ("pen", "✎ Pen"),
            ("line", "／ Line"),
            ("rect", "▭ Rect"),
            ("ellipse", "◯ Ellipse"),
            ("arrow", "→ Arrow"),
            ("text", "T Text"),
            ("eraser", "✗ Eraser"),
        ):
            act = QAction(label, self)
            act.setCheckable(True)
            act.triggered.connect(
                lambda checked=False, n=name: self._canvas.set_tool(n))
            self._tool_group.addAction(act)
            tb.addAction(act)
            if name == "pen":
                act.setChecked(True)
        tb.addSeparator()
        undo_act = QAction("⤺ Undo", self)
        undo_act.setShortcut(QKeySequence.Undo)
        undo_act.triggered.connect(self._canvas.undo)
        tb.addAction(undo_act)
        clear_act = QAction("Clear", self)
        clear_act.triggered.connect(self._canvas.clear_all)
        tb.addAction(clear_act)

        # ---- color palette + width slider --------------------------------
        palette_row = QHBoxLayout()
        palette_row.setSpacing(4)
        palette_row.addWidget(QLabel("Colour:"))
        for color in _PALETTE:
            btn = QPushButton()
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(
                f"background:{color}; border:1px solid #888;"
                "border-radius:11px;")
            btn.setToolTip(color)
            btn.clicked.connect(
                lambda checked=False, c=color: self._canvas.set_color(QColor(c)))
            palette_row.addWidget(btn)
        custom = QPushButton("…")
        custom.setFixedSize(28, 22)
        custom.setToolTip("Pick a custom colour")
        custom.clicked.connect(self._pick_custom_color)
        palette_row.addWidget(custom)
        palette_row.addSpacing(16)
        palette_row.addWidget(QLabel("Width:"))
        self._width_slider = QSlider(Qt.Horizontal)
        self._width_slider.setRange(1, 20)
        self._width_slider.setValue(2)
        self._width_slider.setFixedWidth(140)
        self._width_slider.valueChanged.connect(self._canvas.set_width)
        palette_row.addWidget(self._width_slider)
        self._width_label = QLabel("2 px")
        palette_row.addWidget(self._width_label)
        self._width_slider.valueChanged.connect(
            lambda v: self._width_label.setText(f"{v} px"))
        palette_row.addStretch(1)

        # ---- buttons -----------------------------------------------------
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_and_save)
        buttons.rejected.connect(self.reject)

        # ---- layout ------------------------------------------------------
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(tb)
        outer.addLayout(palette_row)
        outer.addWidget(self._canvas, 1)
        outer.addWidget(buttons)

    def saved_path(self) -> Path | None:
        return self._saved_path

    # ---- actions -------------------------------------------------------

    def _pick_custom_color(self) -> None:
        c = QColorDialog.getColor(QColor("#000000"), self,
                                   "Pick colour")
        if c.isValid():
            self._canvas.set_color(c)

    def _accept_and_save(self) -> None:
        # Render the scene to an image, save as PNG, finish.
        items = list(self._scene.items())
        if not items:
            self.reject()
            return
        bounds = self._scene.itemsBoundingRect()
        if bounds.isEmpty():
            self.reject()
            return
        pad = 16
        bounds.adjust(-pad, -pad, pad, pad)
        # Render at 2× scene size for crisp output.
        scale = 2
        img = QImage(int(bounds.width() * scale),
                     int(bounds.height() * scale),
                     QImage.Format_ARGB32)
        img.fill(QColor("white"))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        self._scene.render(painter, target=QRectF(img.rect()),
                           source=bounds)
        painter.end()
        # Pick a non-clashing filename.
        i = 1
        while True:
            candidate = self._images_dir / f"drawing_{i:03d}.png"
            if not candidate.exists():
                break
            i += 1
        if not img.save(str(candidate), "PNG"):
            self.reject()
            return
        self._saved_path = candidate
        self.drawingSaved.emit(str(candidate))
        self.accept()
