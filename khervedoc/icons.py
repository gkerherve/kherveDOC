"""Programmatically-drawn toolbar icons.

QPainter draws each icon onto a transparent QPixmap so we never ship binary
image files. Every icon function returns a QIcon.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
    QPolygonF,
)

_SIZE = 24
_FG = QColor("#222")
_ACCENT = QColor("#1a6dd8")
_ACCENT2 = QColor("#d96b00")
_LINE_W = 2.0


def _new_canvas() -> tuple[QPixmap, QPainter]:
    px = QPixmap(_SIZE, _SIZE)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    return px, p


def _glyph_icon(letter: str, *, bold=False, italic=False, underline=False,
                strike=False, color: QColor = _FG) -> QIcon:
    px, p = _new_canvas()
    f = QFont("Georgia")
    f.setPointSize(15)
    f.setBold(bold)
    f.setItalic(italic)
    f.setUnderline(underline)
    f.setStrikeOut(strike)
    p.setFont(f)
    p.setPen(color)
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, letter)
    p.end()
    return QIcon(px)


# ----- text formatting -----

def bold() -> QIcon:       return _glyph_icon("B", bold=True)
def italic() -> QIcon:     return _glyph_icon("I", italic=True)
def underline() -> QIcon:  return _glyph_icon("U", underline=True)
def strike() -> QIcon:     return _glyph_icon("S", strike=True)
def code() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, _LINE_W, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPointF(9, 6), QPointF(4, 12), QPointF(9, 18)])
    p.drawPolyline([QPointF(15, 6), QPointF(20, 12), QPointF(15, 18)])
    p.end()
    return QIcon(px)
def smallcaps() -> QIcon:
    px, p = _new_canvas()
    f1 = QFont("Georgia"); f1.setPointSize(15); f1.setBold(True)
    f2 = QFont("Georgia"); f2.setPointSize(11); f2.setBold(True)
    p.setPen(_FG)
    p.setFont(f1)
    p.drawText(QRect(2, 0, 12, _SIZE), Qt.AlignCenter, "A")
    p.setFont(f2)
    p.drawText(QRect(12, 0, 12, _SIZE), Qt.AlignCenter, "A")
    p.end()
    return QIcon(px)
def superscript() -> QIcon:
    px, p = _new_canvas()
    p.setPen(_FG)
    # Big X anchored in the lower-left so the small 2 fits clearly above-right.
    f1 = QFont("Georgia"); f1.setPointSize(13); f1.setBold(True)
    p.setFont(f1)
    p.drawText(QRect(0, 4, 16, 20), Qt.AlignCenter, "X")
    f2 = QFont("Georgia"); f2.setPointSize(10); f2.setBold(True)
    p.setFont(f2)
    p.drawText(QRect(12, 0, 12, 12), Qt.AlignLeft | Qt.AlignTop, "2")
    p.end()
    return QIcon(px)


def subscript() -> QIcon:
    px, p = _new_canvas()
    p.setPen(_FG)
    # Big X anchored in the upper-left; small 2 sits in the lower-right
    # tucked below the baseline.
    f1 = QFont("Georgia"); f1.setPointSize(13); f1.setBold(True)
    p.setFont(f1)
    p.drawText(QRect(0, 0, 16, 20), Qt.AlignCenter, "X")
    f2 = QFont("Georgia"); f2.setPointSize(10); f2.setBold(True)
    p.setFont(f2)
    p.drawText(QRect(12, 12, 12, 12), Qt.AlignLeft | Qt.AlignTop, "2")
    p.end()
    return QIcon(px)


# ----- headings -----

def heading(level: int) -> QIcon:
    px, p = _new_canvas()
    f = QFont("Georgia"); f.setBold(True)
    f.setPointSize({1: 14, 2: 13, 3: 12, 4: 11, 5: 10}.get(level, 12))
    p.setFont(f); p.setPen(_FG)
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, f"H{level}")
    p.end()
    return QIcon(px)


# ----- math -----

def math_inline() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(15); f.setItalic(True)
    p.setFont(f); p.setPen(_ACCENT)
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "ƒx")
    p.end()
    return QIcon(px)


def math_block() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(13); f.setItalic(True)
    p.setFont(f); p.setPen(_ACCENT)
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "Σxᵢ")
    p.end()
    return QIcon(px)


# ----- structure -----

def bullet_list() -> QIcon:
    px, p = _new_canvas()
    p.setBrush(QBrush(_FG)); p.setPen(Qt.NoPen)
    for y in (6, 12, 18):
        p.drawEllipse(QRect(4, y - 2, 4, 4))
    p.setPen(QPen(_FG, _LINE_W, Qt.SolidLine, Qt.RoundCap))
    for y in (6, 12, 18):
        p.drawLine(11, y, 21, y)
    p.end()
    return QIcon(px)


def numbered_list() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Arial"); f.setPointSize(7); f.setBold(True)
    p.setFont(f); p.setPen(_FG)
    for i, y in enumerate((6, 12, 18), start=1):
        p.drawText(QRect(2, y - 6, 8, 12), Qt.AlignCenter, f"{i}.")
    p.setPen(QPen(_FG, _LINE_W, Qt.SolidLine, Qt.RoundCap))
    for y in (6, 12, 18):
        p.drawLine(11, y, 21, y)
    p.end()
    return QIcon(px)


def link() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_ACCENT, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    # Two interlocking chain links.
    p.drawArc(3, 8, 10, 10, 90 * 16, 180 * 16)
    p.drawArc(11, 6, 10, 10, -90 * 16, 180 * 16)
    p.drawLine(9, 12, 15, 12)
    p.end()
    return QIcon(px)


def footnote() -> QIcon:
    px, p = _new_canvas()
    f1 = QFont("Georgia"); f1.setPointSize(14)
    f2 = QFont("Georgia"); f2.setPointSize(9); f2.setBold(True)
    p.setPen(_FG)
    p.setFont(f1); p.drawText(QRect(0, 4, 14, _SIZE), Qt.AlignLeft | Qt.AlignVCenter, "T")
    p.setFont(f2); p.drawText(QRect(12, 0, 10, _SIZE), Qt.AlignLeft | Qt.AlignTop, "1")
    p.end()
    return QIcon(px)


def citation() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Arial"); f.setPointSize(11); f.setBold(True)
    p.setFont(f); p.setPen(_FG)
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "[1]")
    p.end()
    return QIcon(px)


def cross_ref() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_ACCENT2, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(5, 14, 19, 14)
    # Arrow head
    p.drawPolyline([QPointF(15, 10), QPointF(19, 14), QPointF(15, 18)])
    f = QFont("Georgia"); f.setPointSize(8); f.setBold(True)
    p.setFont(f); p.setPen(_FG)
    p.drawText(QRect(0, 0, _SIZE, 10), Qt.AlignCenter, "ref")
    p.end()
    return QIcon(px)


def figure() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.6))
    p.setBrush(QBrush(QColor("#f4f4f4")))
    p.drawRect(3, 5, 18, 14)
    p.setBrush(QBrush(_ACCENT2)); p.setPen(Qt.NoPen)
    # Sun + mountain.
    p.drawEllipse(QRect(15, 8, 4, 4))
    p.setBrush(QBrush(_ACCENT)); p.setPen(Qt.NoPen)
    p.drawPolygon([QPointF(4, 18), QPointF(10, 11), QPointF(14, 15), QPointF(20, 18)])
    p.end()
    return QIcon(px)


def table() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.4))
    p.setBrush(Qt.NoBrush)
    rect = QRect(3, 5, 18, 14)
    p.drawRect(rect)
    # Inner grid.
    p.drawLine(3, 10, 21, 10)
    p.drawLine(3, 14, 21, 14)
    p.drawLine(9, 5, 9, 19)
    p.drawLine(15, 5, 15, 19)
    # Header band.
    p.setBrush(QBrush(QColor("#e8efff"))); p.setPen(Qt.NoPen)
    p.drawRect(QRect(4, 6, 16, 3))
    p.end()
    return QIcon(px)


# ----- file ops + history -----

def file_new() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.6)); p.setBrush(QBrush(Qt.white))
    p.drawPolygon([QPointF(5, 3), QPointF(15, 3), QPointF(19, 7),
                   QPointF(19, 21), QPointF(5, 21)])
    p.drawPolyline([QPointF(15, 3), QPointF(15, 7), QPointF(19, 7)])
    p.setPen(QPen(_ACCENT, 2)); p.drawLine(12, 11, 12, 17); p.drawLine(9, 14, 15, 14)
    p.end()
    return QIcon(px)


def file_open() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.6)); p.setBrush(QBrush(QColor("#ffd073")))
    p.drawPolygon([QPointF(3, 8), QPointF(9, 8), QPointF(11, 6),
                   QPointF(20, 6), QPointF(20, 19), QPointF(3, 19)])
    p.end()
    return QIcon(px)


def file_save() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.6)); p.setBrush(QBrush(_ACCENT))
    p.drawPolygon([QPointF(4, 4), QPointF(17, 4), QPointF(20, 7),
                   QPointF(20, 20), QPointF(4, 20)])
    p.setBrush(QBrush(Qt.white)); p.setPen(Qt.NoPen)
    p.drawRect(QRect(7, 4, 8, 5))
    p.drawRect(QRect(7, 13, 10, 7))
    p.end()
    return QIcon(px)


def undo() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawArc(4, 7, 16, 12, 30 * 16, 200 * 16)
    p.drawPolyline([QPointF(4, 6), QPointF(4, 12), QPointF(10, 12)])
    p.end()
    return QIcon(px)


def redo() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawArc(4, 7, 16, 12, -50 * 16, 200 * 16)
    p.drawPolyline([QPointF(20, 6), QPointF(20, 12), QPointF(14, 12)])
    p.end()
    return QIcon(px)


def export_pdf() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.6)); p.setBrush(QBrush(Qt.white))
    p.drawPolygon([QPointF(5, 3), QPointF(15, 3), QPointF(19, 7),
                   QPointF(19, 21), QPointF(5, 21)])
    f = QFont("Arial"); f.setPointSize(7); f.setBold(True)
    p.setFont(f); p.setPen(QColor("#c00"))
    p.drawText(QRect(5, 10, 14, 10), Qt.AlignCenter, "PDF")
    p.end()
    return QIcon(px)


def history() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 2, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRect(4, 4, 16, 16))
    p.drawLine(12, 8, 12, 12)
    p.drawLine(12, 12, 16, 14)
    p.end()
    return QIcon(px)


def commit() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 2)); p.setBrush(QBrush(Qt.white))
    p.drawLine(12, 3, 12, 8); p.drawLine(12, 16, 12, 21)
    p.drawEllipse(QRect(7, 8, 10, 10))
    p.end()
    return QIcon(px)


def page_break() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.6)); p.setBrush(QBrush(Qt.white))
    p.drawRect(QRect(4, 3, 16, 7))
    p.drawRect(QRect(4, 14, 16, 7))
    p.setPen(QPen(_ACCENT, 2, Qt.DashLine))
    p.drawLine(2, 12, 22, 12)
    p.end()
    return QIcon(px)


def horizontal_rule() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 2.5, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(3, 12, 21, 12)
    p.end()
    return QIcon(px)


# ----- alignment -----

def _alignment_icon(lines: list[tuple[int, int, int]]) -> QIcon:
    """lines: list of (y, x1, x2) for each horizontal stroke."""
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 2.0, Qt.SolidLine, Qt.RoundCap))
    for y, x1, x2 in lines:
        p.drawLine(x1, y, x2, y)
    p.end()
    return QIcon(px)


def align_left() -> QIcon:
    return _alignment_icon([(6, 3, 21), (11, 3, 16), (16, 3, 19), (21, 3, 14)])


def align_center() -> QIcon:
    return _alignment_icon([(6, 3, 21), (11, 7, 17), (16, 5, 19), (21, 6, 18)])


def align_right() -> QIcon:
    return _alignment_icon([(6, 3, 21), (11, 8, 21), (16, 5, 21), (21, 10, 21)])


def align_justify() -> QIcon:
    return _alignment_icon([(6, 3, 21), (11, 3, 21), (16, 3, 21), (21, 3, 21)])


def zoom_in() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRect(4, 4, 12, 12))
    p.drawLine(15, 15, 20, 20)
    p.drawLine(7, 10, 13, 10); p.drawLine(10, 7, 10, 13)
    p.end()
    return QIcon(px)


def symbol() -> QIcon:
    """Greek alpha glyph — toolbar marker for the symbol palette."""
    px, p = _new_canvas()
    f = QFont("Cambria Math")
    f.setPointSize(17); f.setItalic(True)
    p.setFont(f); p.setPen(_ACCENT)
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "α")  # α
    p.end()
    return QIcon(px)


def zoom_out() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_FG, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRect(4, 4, 12, 12))
    p.drawLine(15, 15, 20, 20)
    p.drawLine(7, 10, 13, 10)
    p.end()
    return QIcon(px)
