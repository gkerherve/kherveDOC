"""Beamer Studio — a WYSIWYG slide designer.

The canvas is a fixed-aspect slide rectangle holding free-floating text
and picture boxes. Each box can be dragged anywhere, resized from any of
its eight handles, and raised / lowered in the z-stack — all directly on
the slide, the way the user wants to see it. Geometry is stored in the
:mod:`khervedoc.beamer_model` deck as ``0..1`` fractions, so the
``textpos`` serializer reproduces the exact placement in the compiled
PDF.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QAction, QBrush, QColor, QFont, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QCheckBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGraphicsItem, QGraphicsObject, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QSplitter, QToolBar, QVBoxLayout, QWidget,
)

from . import beamer_templates as templates
from .beamer_model import (
    Deck, Slide, SlideText, SlidePicture,
    deck_to_json, deck_from_json,
    raise_object, lower_object, to_front, to_back,
)
from .beamer_serializer import serialize_deck
from .compiler import compile_tex, tectonic_available
from .preview import PdfPreview


SCENE_H = 720.0                 # slide height in scene units (px)
# beamer's slide height is ~96 mm ≈ 272.8 pt regardless of aspect ratio,
# so this converts a font's pt size into canvas pixels for WYSIWYG sizing.
FONT_SCALE = SCENE_H / 272.8
HANDLE = 9.0                    # half-size of a resize handle, in px
MIN_PX = 24.0                   # smallest box dimension

_ASPECT_RATIO = {              # width : height multiplier
    "169": 16 / 9, "1610": 16 / 10, "43": 4 / 3,
    "32": 3 / 2, "54": 5 / 4, "141": 1.41,
}

# Resize-handle ids, clockwise from top-left.
TL, T, TR, R, BR, B, BL, L = range(8)
_LEFT = {TL, L, BL}
_RIGHT = {TR, R, BR}
_TOP = {TL, T, TR}
_BOTTOM = {BL, B, BR}


def scene_width(aspect: str) -> float:
    return SCENE_H * _ASPECT_RATIO.get(aspect, 16 / 9)


class BoxItem(QGraphicsObject):
    """A movable, eight-handle-resizable rectangle bound to a model
    object. Position is the item's scene pos; size is the local rect
    ``(0, 0, w, h)``. Subclasses paint the content."""

    geometryChanged = Signal()
    selectedChanged = Signal()

    def __init__(self, obj, scene_w: float):
        super().__init__()
        self.obj = obj
        self._scene_w = scene_w
        self._rect = QRectF(0, 0, max(MIN_PX, obj.w * scene_w),
                            max(MIN_PX, obj.h * SCENE_H))
        self.setPos(obj.x * scene_w, obj.y * SCENE_H)
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self._resize_handle: int | None = None
        self._press_scene = QPointF()
        self._start_rect = QRectF()
        self._start_pos = QPointF()

    # -- geometry --------------------------------------------------
    def boundingRect(self) -> QRectF:
        m = HANDLE + 1
        return self._rect.adjusted(-m, -m, m, m)

    def _handle_rects(self) -> dict[int, QRectF]:
        r = self._rect
        cx, cy = r.center().x(), r.center().y()
        pts = {
            TL: (r.left(), r.top()), T: (cx, r.top()), TR: (r.right(), r.top()),
            R: (r.right(), cy), BR: (r.right(), r.bottom()),
            B: (cx, r.bottom()), BL: (r.left(), r.bottom()), L: (r.left(), cy),
        }
        return {h: QRectF(x - HANDLE, y - HANDLE, 2 * HANDLE, 2 * HANDLE)
                for h, (x, y) in pts.items()}

    def _handle_at(self, pos: QPointF) -> int | None:
        for h, rect in self._handle_rects().items():
            if rect.contains(pos):
                return h
        return None

    # -- mouse -----------------------------------------------------
    def hoverMoveEvent(self, event):
        h = self._handle_at(event.pos()) if self.isSelected() else None
        cursors = {
            TL: Qt.SizeFDiagCursor, BR: Qt.SizeFDiagCursor,
            TR: Qt.SizeBDiagCursor, BL: Qt.SizeBDiagCursor,
            T: Qt.SizeVerCursor, B: Qt.SizeVerCursor,
            L: Qt.SizeHorCursor, R: Qt.SizeHorCursor,
        }
        self.setCursor(cursors.get(h, Qt.SizeAllCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        h = self._handle_at(event.pos()) if self.isSelected() else None
        if h is not None:
            self._resize_handle = h
            self._press_scene = event.scenePos()
            self._start_rect = QRectF(self._rect)
            self._start_pos = self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resize_handle is None:
            super().mouseMoveEvent(event)
            return
        d = event.scenePos() - self._press_scene
        x, y = self._start_pos.x(), self._start_pos.y()
        w, h = self._start_rect.width(), self._start_rect.height()
        hd = self._resize_handle
        if hd in _LEFT:
            x += d.x(); w -= d.x()
        if hd in _RIGHT:
            w += d.x()
        if hd in _TOP:
            y += d.y(); h -= d.y()
        if hd in _BOTTOM:
            h += d.y()
        if w < MIN_PX:
            if hd in _LEFT:
                x = self._start_pos.x() + self._start_rect.width() - MIN_PX
            w = MIN_PX
        if h < MIN_PX:
            if hd in _TOP:
                y = self._start_pos.y() + self._start_rect.height() - MIN_PX
            h = MIN_PX
        self.prepareGeometryChange()
        self._rect = QRectF(0, 0, w, h)
        self.setPos(x, y)
        self.update()
        self._write_geometry()
        self.geometryChanged.emit()

    def mouseReleaseEvent(self, event):
        self._resize_handle = None
        self._write_geometry()
        self.geometryChanged.emit()
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # Keep the box inside the slide.
            sw = scene_width(self._aspect())
            nx = min(max(0.0, value.x()), sw - self._rect.width())
            ny = min(max(0.0, value.y()), SCENE_H - self._rect.height())
            return QPointF(nx, ny)
        if change == QGraphicsItem.ItemPositionHasChanged:
            self._write_geometry()
            self.geometryChanged.emit()
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.selectedChanged.emit()
        return super().itemChange(change, value)

    def _aspect(self) -> str:
        sc = self.scene()
        return getattr(sc, "aspect", "169") if sc else "169"

    def _write_geometry(self) -> None:
        sw = scene_width(self._aspect())
        self.obj.x = round(self.pos().x() / sw, 4)
        self.obj.y = round(self.pos().y() / SCENE_H, 4)
        self.obj.w = round(self._rect.width() / sw, 4)
        self.obj.h = round(self._rect.height() / SCENE_H, 4)

    def sync_from_model(self) -> None:
        """Re-read geometry from the model (after spinbox edits)."""
        sw = scene_width(self._aspect())
        self.prepareGeometryChange()
        self._rect = QRectF(0, 0, max(MIN_PX, self.obj.w * sw),
                            max(MIN_PX, self.obj.h * SCENE_H))
        self.setPos(self.obj.x * sw, self.obj.y * SCENE_H)
        self.update()

    # -- painting helpers -----------------------------------------
    def _paint_selection(self, painter):
        if not self.isSelected():
            painter.setPen(QPen(QColor(150, 150, 150), 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self._rect)
            return
        painter.setPen(QPen(QColor(40, 120, 220), 0, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self._rect)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(40, 120, 220), 0))
        for rect in self._handle_rects().values():
            painter.drawRect(rect)


class TextBoxItem(BoxItem):
    def paint(self, painter, option, widget=None):
        obj: SlideText = self.obj
        if obj.fill:
            painter.fillRect(self._rect, QColor(obj.fill))
        font = QFont("Helvetica")
        font.setPixelSize(max(6, int(obj.font_pt * FONT_SCALE)))
        font.setBold(obj.bold)
        font.setItalic(obj.italic)
        painter.setFont(font)
        painter.setPen(QPen(QColor(obj.color or "#000000")))
        flag = {"center": Qt.AlignHCenter, "right": Qt.AlignRight}.get(
            obj.align, Qt.AlignLeft)
        painter.drawText(self._rect.adjusted(4, 2, -4, -2),
                         int(flag | Qt.AlignTop | Qt.TextWordWrap),
                         obj.text or "")
        self._paint_selection(painter)


class PictureBoxItem(BoxItem):
    def __init__(self, obj, scene_w):
        super().__init__(obj, scene_w)
        self._pix: QPixmap | None = None
        self._pix_path = None

    def _pixmap(self) -> QPixmap | None:
        if self.obj.path != self._pix_path:
            self._pix_path = self.obj.path
            pm = QPixmap(self.obj.path) if self.obj.path else QPixmap()
            self._pix = pm if not pm.isNull() else None
        return self._pix

    def paint(self, painter, option, widget=None):
        pm = self._pixmap()
        if pm is not None:
            mode = (Qt.KeepAspectRatio if self.obj.keep_aspect
                    else Qt.IgnoreAspectRatio)
            scaled = pm.scaled(self._rect.size().toSize(), mode,
                               Qt.SmoothTransformation)
            x = self._rect.x() + (self._rect.width() - scaled.width()) / 2
            y = self._rect.y() + (self._rect.height() - scaled.height()) / 2
            painter.drawPixmap(QPointF(x, y), scaled)
        else:
            painter.fillRect(self._rect, QColor(235, 235, 235))
            painter.setPen(QPen(QColor(150, 150, 150)))
            painter.drawText(self._rect, Qt.AlignCenter,
                             "Image\n(set path)")
        self._paint_selection(painter)


class SlideScene(QGraphicsScene):
    def __init__(self, aspect="169"):
        super().__init__()
        self.aspect = aspect
        self._set_rect()

    def _set_rect(self):
        self.setSceneRect(0, 0, scene_width(self.aspect), SCENE_H)

    def set_aspect(self, aspect):
        self.aspect = aspect
        self._set_rect()

    def drawBackground(self, painter, rect):
        painter.fillRect(self.sceneRect(), QColor("#FFFFFF"))
        painter.setPen(QPen(QColor(200, 200, 200), 0))
        painter.drawRect(self.sceneRect())


class BeamerStudio(QMainWindow):
    """Standalone WYSIWYG slide designer window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Beamer Studio — WYSIWYG slides")
        self.resize(1200, 760)
        self.store = templates.TemplateStore()
        self.deck: Deck = templates.instantiate_builtin("Title + content")
        self.current = 0
        self.path: Path | None = None
        self._items: list[BoxItem] = []
        self._loading = False

        self._build_ui()
        self._reload_slide_list()
        self._reload_scene()

    # ---------------- UI scaffolding ----------------
    def _build_ui(self):
        self._build_toolbar()

        self.scene = SlideScene(self.deck.aspect)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(self.view.renderHints())
        self.scene.selectionChanged.connect(self._on_selection)

        self.slide_list = QListWidget()
        self.slide_list.setMaximumWidth(150)
        self.slide_list.currentRowChanged.connect(self._on_slide_changed)
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(4, 4, 4, 4)
        lv.addWidget(QLabel("Slides"))
        lv.addWidget(self.slide_list)
        row = QHBoxLayout()
        b_add = QPushButton("+"); b_add.clicked.connect(self._add_slide)
        b_del = QPushButton("−"); b_del.clicked.connect(self._del_slide)
        b_up = QPushButton("▲"); b_up.clicked.connect(lambda: self._move_slide(-1))
        b_dn = QPushButton("▼"); b_dn.clicked.connect(lambda: self._move_slide(1))
        for b in (b_add, b_del, b_up, b_dn):
            b.setMaximumWidth(34); row.addWidget(b)
        lv.addLayout(row)

        self.props = self._build_props_panel()

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(self.view)
        split.addWidget(self.props)
        split.setStretchFactor(1, 1)
        split.setSizes([150, 760, 290])
        self.setCentralWidget(split)
        self.statusBar().showMessage("Ready")

    def _build_toolbar(self):
        tb = QToolBar("Main"); self.addToolBar(tb)

        def act(text, slot, tip=""):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if tip:
                a.setToolTip(tip)
            tb.addAction(a); return a

        act("Add Text", self._add_text, "Add a text box")
        act("Add Image", self._add_picture, "Add a picture box")
        tb.addSeparator()
        act("Raise", lambda: self._zorder("raise"))
        act("Lower", lambda: self._zorder("lower"))
        act("To Front", lambda: self._zorder("front"))
        act("To Back", lambda: self._zorder("back"))
        act("Delete", self._delete_selected)
        tb.addSeparator()
        act("Templates…", self._templates_menu, "New from / manage templates")
        act("Compile ▶", self._compile, "Compile to PDF preview")
        tb.addSeparator()
        act("Open…", self._open_deck)
        act("Save…", self._save_deck)
        act("Export .tex", self._export_tex)

    def _build_props_panel(self) -> QWidget:
        w = QWidget(); w.setMinimumWidth(280)
        v = QVBoxLayout(w)

        # Deck-level
        v.addWidget(QLabel("<b>Deck</b>"))
        deck_form = QFormLayout()
        self.f_title = QLineEdit(); self.f_title.editingFinished.connect(
            self._apply_deck)
        self.f_author = QLineEdit(); self.f_author.editingFinished.connect(
            self._apply_deck)
        self.f_theme = QComboBox(); self.f_theme.setEditable(True)
        self.f_theme.addItems(["default", "Madrid", "Berlin", "Copenhagen",
                               "Frankfurt", "Singapore", "Warsaw", "metropolis",
                               "CambridgeUS", "Boadilla", "Pittsburgh"])
        self.f_theme.currentTextChanged.connect(self._apply_deck)
        self.f_color = QComboBox(); self.f_color.setEditable(True)
        self.f_color.addItems(["", "default", "beaver", "crane", "dolphin",
                               "seagull", "wolverine", "orchid", "whale"])
        self.f_color.currentTextChanged.connect(self._apply_deck)
        self.f_aspect = QComboBox()
        self.f_aspect.addItems(["169", "1610", "43", "32", "54", "141"])
        self.f_aspect.currentTextChanged.connect(self._apply_aspect)
        deck_form.addRow("Title", self.f_title)
        deck_form.addRow("Author", self.f_author)
        deck_form.addRow("Theme", self.f_theme)
        deck_form.addRow("Colours", self.f_color)
        deck_form.addRow("Aspect", self.f_aspect)
        v.addLayout(deck_form)

        # Slide-level
        v.addWidget(QLabel("<b>Slide</b>"))
        slide_form = QFormLayout()
        self.f_slide_title = QLineEdit()
        self.f_slide_title.editingFinished.connect(self._apply_slide)
        self.b_slide_bg = QPushButton("Background…")
        self.b_slide_bg.clicked.connect(self._pick_slide_bg)
        slide_form.addRow("Frame title", self.f_slide_title)
        slide_form.addRow("", self.b_slide_bg)
        v.addLayout(slide_form)

        # Object-level
        v.addWidget(QLabel("<b>Selected object</b>"))
        self.obj_form = QFormLayout()
        self.f_text = QPlainTextEdit(); self.f_text.setMaximumHeight(90)
        self.f_text.textChanged.connect(self._apply_obj_text)
        self.f_font = QSpinBox(); self.f_font.setRange(6, 160)
        self.f_font.valueChanged.connect(self._apply_obj)
        self.b_color = QPushButton("Text colour…")
        self.b_color.clicked.connect(lambda: self._pick_obj_color("color"))
        self.b_fill = QPushButton("Fill…")
        self.b_fill.clicked.connect(lambda: self._pick_obj_color("fill"))
        self.f_align = QComboBox(); self.f_align.addItems(["left", "center", "right"])
        self.f_align.currentTextChanged.connect(self._apply_obj)
        self.c_bold = QCheckBox("Bold"); self.c_bold.toggled.connect(self._apply_obj)
        self.c_italic = QCheckBox("Italic"); self.c_italic.toggled.connect(self._apply_obj)
        self.b_img = QPushButton("Image file…")
        self.b_img.clicked.connect(self._pick_image)
        self.c_aspect = QCheckBox("Keep aspect")
        self.c_aspect.toggled.connect(self._apply_obj)
        self.f_x = self._pct_spin(); self.f_y = self._pct_spin()
        self.f_w = self._pct_spin(); self.f_h = self._pct_spin()
        for s in (self.f_x, self.f_y, self.f_w, self.f_h):
            s.valueChanged.connect(self._apply_obj_geometry)
        self.obj_form.addRow("Text", self.f_text)
        self.obj_form.addRow("Font pt", self.f_font)
        self.obj_form.addRow("", self.b_color)
        self.obj_form.addRow("", self.b_fill)
        self.obj_form.addRow("Align", self.f_align)
        self.obj_form.addRow(self.c_bold, self.c_italic)
        self.obj_form.addRow("", self.b_img)
        self.obj_form.addRow("", self.c_aspect)
        self.obj_form.addRow("X %", self.f_x)
        self.obj_form.addRow("Y %", self.f_y)
        self.obj_form.addRow("W %", self.f_w)
        self.obj_form.addRow("H %", self.f_h)
        v.addLayout(self.obj_form)
        v.addStretch(1)
        self._set_obj_enabled(False)
        return w

    def _pct_spin(self):
        s = QDoubleSpinBox(); s.setRange(0, 100); s.setSuffix(" %")
        s.setDecimals(1); s.setSingleStep(1.0)
        return s

    # ---------------- slide management ----------------
    @property
    def slide(self) -> Slide:
        return self.deck.slides[self.current]

    def _reload_slide_list(self):
        self._loading = True
        self.slide_list.clear()
        for i, _ in enumerate(self.deck.slides, 1):
            self.slide_list.addItem(f"Slide {i}")
        self.slide_list.setCurrentRow(self.current)
        self._loading = False

    def _reload_scene(self):
        # Drop Python wrappers *before* clearing the scene: scene.clear()
        # deletes the C++ items and emits selectionChanged, and a stale
        # self._items would then dereference deleted objects.
        self._loading = True
        self._items = []
        self.scene.set_aspect(self.deck.aspect)
        self.scene.clear()
        sw = scene_width(self.deck.aspect)
        for obj in self.slide.objects:
            item = (TextBoxItem(obj, sw) if isinstance(obj, SlideText)
                    else PictureBoxItem(obj, sw))
            item.geometryChanged.connect(self._on_item_geometry)
            self.scene.addItem(item)
            self._items.append(item)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self._load_deck_fields()
        self._load_slide_fields()
        self._set_obj_enabled(False)
        self._loading = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def _on_slide_changed(self, row):
        if self._loading or row < 0 or row >= len(self.deck.slides):
            return
        self.current = row
        self._reload_scene()

    def _add_slide(self):
        self.deck.slides.insert(self.current + 1, Slide())
        self.current += 1
        self._reload_slide_list()
        self._reload_scene()

    def _del_slide(self):
        if len(self.deck.slides) <= 1:
            return
        del self.deck.slides[self.current]
        self.current = max(0, self.current - 1)
        self._reload_slide_list()
        self._reload_scene()

    def _move_slide(self, delta):
        j = self.current + delta
        if 0 <= j < len(self.deck.slides):
            s = self.deck.slides
            s[self.current], s[j] = s[j], s[self.current]
            self.current = j
            self._reload_slide_list()
            self._reload_scene()

    # ---------------- object management ----------------
    def _add_text(self):
        self.slide.objects.append(SlideText())
        self._reload_scene()
        self._select_last()

    def _add_picture(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose image", "",
            "Images (*.png *.jpg *.jpeg *.pdf *.gif *.bmp)")
        self.slide.objects.append(SlidePicture(path=path or ""))
        self._reload_scene()
        self._select_last()

    def _select_last(self):
        if self._items:
            self._items[-1].setSelected(True)

    def _delete_selected(self):
        item = self._selected_item()
        if item is None:
            return
        self.slide.objects.remove(item.obj)
        self._reload_scene()

    def _zorder(self, how):
        item = self._selected_item()
        if item is None:
            return
        idx = self.slide.objects.index(item.obj)
        fn = {"raise": raise_object, "lower": lower_object,
              "front": to_front, "back": to_back}[how]
        new_idx = fn(self.slide, idx)
        self._reload_scene()
        if 0 <= new_idx < len(self._items):
            self._items[new_idx].setSelected(True)

    def _selected_item(self) -> BoxItem | None:
        for it in self._items:
            if it.isSelected():
                return it
        return None

    # ---------------- property syncing ----------------
    def _on_selection(self):
        if self._loading:
            return
        item = self._selected_item()
        if item is None:
            self._set_obj_enabled(False)
            return
        self._load_obj_fields(item.obj)

    def _on_item_geometry(self):
        item = self._selected_item()
        if item is not None:
            self._load_obj_geometry(item.obj)

    def _set_obj_enabled(self, on, is_text=True, is_pic=False):
        for wdg in (self.f_text, self.f_font, self.b_color, self.b_fill,
                    self.f_align, self.c_bold, self.c_italic):
            wdg.setEnabled(on and is_text)
        for wdg in (self.b_img, self.c_aspect):
            wdg.setEnabled(on and is_pic)
        for wdg in (self.f_x, self.f_y, self.f_w, self.f_h):
            wdg.setEnabled(on)

    def _load_obj_geometry(self, obj):
        self._loading = True
        self.f_x.setValue(obj.x * 100); self.f_y.setValue(obj.y * 100)
        self.f_w.setValue(obj.w * 100); self.f_h.setValue(obj.h * 100)
        self._loading = False

    def _load_obj_fields(self, obj):
        self._loading = True
        is_text = isinstance(obj, SlideText)
        self._set_obj_enabled(True, is_text=is_text, is_pic=not is_text)
        if is_text:
            self.f_text.setPlainText(obj.text)
            self.f_font.setValue(obj.font_pt)
            self.f_align.setCurrentText(obj.align)
            self.c_bold.setChecked(obj.bold)
            self.c_italic.setChecked(obj.italic)
        else:
            self.c_aspect.setChecked(obj.keep_aspect)
        self._load_obj_geometry(obj)
        self._loading = False

    def _apply_obj(self):
        if self._loading:
            return
        item = self._selected_item()
        if item is None:
            return
        obj = item.obj
        if isinstance(obj, SlideText):
            obj.font_pt = self.f_font.value()
            obj.align = self.f_align.currentText()
            obj.bold = self.c_bold.isChecked()
            obj.italic = self.c_italic.isChecked()
        else:
            obj.keep_aspect = self.c_aspect.isChecked()
        item.update()

    def _apply_obj_text(self):
        if self._loading:
            return
        item = self._selected_item()
        if item is None or not isinstance(item.obj, SlideText):
            return
        item.obj.text = self.f_text.toPlainText()
        item.update()

    def _apply_obj_geometry(self):
        if self._loading:
            return
        item = self._selected_item()
        if item is None:
            return
        obj = item.obj
        obj.x = self.f_x.value() / 100; obj.y = self.f_y.value() / 100
        obj.w = self.f_w.value() / 100; obj.h = self.f_h.value() / 100
        item.sync_from_model()

    def _pick_obj_color(self, which):
        item = self._selected_item()
        if item is None or not isinstance(item.obj, SlideText):
            return
        cur = getattr(item.obj, which) or "#000000"
        col = QColorDialog.getColor(QColor(cur), self)
        if col.isValid():
            setattr(item.obj, which, col.name())
            item.update()

    def _pick_image(self):
        item = self._selected_item()
        if item is None or not isinstance(item.obj, SlidePicture):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose image", "",
            "Images (*.png *.jpg *.jpeg *.pdf *.gif *.bmp)")
        if path:
            item.obj.path = path
            item.update()

    # ---------------- deck/slide fields ----------------
    def _load_deck_fields(self):
        self._loading = True
        self.f_title.setText(self.deck.title)
        self.f_author.setText(self.deck.author)
        self.f_theme.setCurrentText(self.deck.theme)
        self.f_color.setCurrentText(self.deck.color_theme)
        self.f_aspect.setCurrentText(self.deck.aspect)
        self._loading = False

    def _load_slide_fields(self):
        self._loading = True
        self.f_slide_title.setText(self.slide.title)
        self._loading = False

    def _apply_deck(self):
        if self._loading:
            return
        self.deck.title = self.f_title.text()
        self.deck.author = self.f_author.text()
        self.deck.theme = self.f_theme.currentText()
        self.deck.color_theme = self.f_color.currentText()

    def _apply_aspect(self, aspect):
        if self._loading:
            return
        self.deck.aspect = aspect
        self._reload_scene()

    def _apply_slide(self):
        if self._loading:
            return
        self.slide.title = self.f_slide_title.text()

    def _pick_slide_bg(self):
        cur = self.slide.bg or "#FFFFFF"
        col = QColorDialog.getColor(QColor(cur), self, "Slide background")
        if col.isValid():
            self.slide.bg = col.name()

    # ---------------- templates ----------------
    def _templates_menu(self):
        choices = (["New from: " + n for n in self.store.all_names()]
                   + ["— Save current deck as template…",
                      "— Rename a template…",
                      "— Delete a template…"])
        choice, ok = QInputDialog.getItem(
            self, "Templates", "Choose an action:", choices, 0, False)
        if not ok:
            return
        if choice.startswith("New from: "):
            name = choice[len("New from: "):]
            self.deck = self.store.instantiate(name)
            self.current = 0
            self._reload_slide_list(); self._reload_scene()
        elif "Save current" in choice:
            self._save_as_template()
        elif "Rename" in choice:
            self._rename_template()
        elif "Delete" in choice:
            self._delete_template()

    def _save_as_template(self):
        name, ok = QInputDialog.getText(self, "Save template",
                                        "New template name:")
        if not ok or not name.strip():
            return
        try:
            self.store.save_deck_as(name.strip(), self.deck)
            self.statusBar().showMessage(f"Saved template '{name.strip()}'")
        except ValueError as e:
            QMessageBox.warning(self, "Template", str(e))

    def _rename_template(self):
        names = self.store.names()
        if not names:
            QMessageBox.information(self, "Rename", "No user templates yet.")
            return
        old, ok = QInputDialog.getItem(self, "Rename template",
                                       "Template:", names, 0, False)
        if not ok:
            return
        new, ok = QInputDialog.getText(self, "Rename template",
                                       "New name:", text=old)
        if not ok:
            return
        try:
            self.store.rename(old, new.strip())
        except (ValueError, KeyError) as e:
            QMessageBox.warning(self, "Rename", str(e))

    def _delete_template(self):
        names = self.store.names()
        if not names:
            QMessageBox.information(self, "Delete", "No user templates yet.")
            return
        name, ok = QInputDialog.getItem(self, "Delete template",
                                        "Template:", names, 0, False)
        if ok:
            self.store.delete(name)

    # ---------------- compile / IO ----------------
    def _compile(self):
        if not tectonic_available():
            QMessageBox.warning(self, "Compile",
                                "tectonic is not available.")
            return
        self.statusBar().showMessage("Compiling…")
        QWidget.setCursor(self, Qt.WaitCursor)
        try:
            tex = serialize_deck(self.deck)
            workdir = Path(tempfile.gettempdir()) / "khervetex_beamer"
            src_dir = self.path.parent if self.path else None
            result = compile_tex(tex, workdir, "slides", source_dir=src_dir)
        finally:
            self.unsetCursor()
        if result.ok and result.pdf_path:
            self._show_pdf(result.pdf_path)
            self.statusBar().showMessage("Compiled OK")
        else:
            QMessageBox.warning(self, "Compile failed",
                                (result.error or "Unknown error") + "\n\n"
                                + (result.log or "")[-1500:])
            self.statusBar().showMessage("Compile failed")

    def _show_pdf(self, pdf_path):
        if not hasattr(self, "_pdf_win") or self._pdf_win is None:
            self._pdf_win = QMainWindow(self)
            self._pdf_win.setWindowTitle("Beamer preview")
            self._pdf_win.resize(900, 600)
            self._pdf_view = PdfPreview(self._pdf_win)
            self._pdf_win.setCentralWidget(self._pdf_view)
        self._pdf_view.show_pdf(Path(pdf_path))
        self._pdf_win.show()
        self._pdf_win.raise_()

    def _save_deck(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save deck", "", "Beamer deck (*.ktex.json)")
        if not path:
            return
        Path(path).write_text(deck_to_json(self.deck), encoding="utf-8")
        self.path = Path(path)
        self.statusBar().showMessage(f"Saved {path}")

    def _open_deck(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open deck", "", "Beamer deck (*.ktex.json *.json)")
        if not path:
            return
        try:
            self.deck = deck_from_json(Path(path).read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "Open", str(e))
            return
        self.path = Path(path)
        self.current = 0
        if not self.deck.slides:
            self.deck.slides = [Slide()]
        self._reload_slide_list(); self._reload_scene()

    def _export_tex(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export LaTeX", "", "LaTeX (*.tex)")
        if not path:
            return
        Path(path).write_text(serialize_deck(self.deck), encoding="utf-8")
        self.statusBar().showMessage(f"Exported {path}")
