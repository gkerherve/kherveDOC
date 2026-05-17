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
_LINE_W = 2.0

# Mutable theme state — call set_dark() to switch.
_dark = False

def _fg() -> QColor:
    return QColor("#ddd") if _dark else QColor("#222")

def _accent() -> QColor:
    return QColor("#6cb4ff") if _dark else QColor("#1a6dd8")

def _accent2() -> QColor:
    return QColor("#f0a050") if _dark else QColor("#d96b00")

def set_dark(dark: bool) -> None:
    global _dark
    _dark = dark


def _new_canvas() -> tuple[QPixmap, QPainter]:
    px = QPixmap(_SIZE, _SIZE)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    return px, p


def _glyph_icon(letter: str, *, bold=False, italic=False, underline=False,
                strike=False, color: QColor | None = None) -> QIcon:
    px, p = _new_canvas()
    f = QFont("Georgia")
    f.setPointSize(15)
    f.setBold(bold)
    f.setItalic(italic)
    f.setUnderline(underline)
    f.setStrikeOut(strike)
    p.setFont(f)
    p.setPen(color if color is not None else _fg())
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
    p.setPen(QPen(_fg(), _LINE_W, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPointF(9, 6), QPointF(4, 12), QPointF(9, 18)])
    p.drawPolyline([QPointF(15, 6), QPointF(20, 12), QPointF(15, 18)])
    p.end()
    return QIcon(px)
def smallcaps() -> QIcon:
    px, p = _new_canvas()
    f1 = QFont("Georgia"); f1.setPointSize(15); f1.setBold(True)
    f2 = QFont("Georgia"); f2.setPointSize(11); f2.setBold(True)
    p.setPen(_fg())
    p.setFont(f1)
    p.drawText(QRect(2, 0, 12, _SIZE), Qt.AlignCenter, "A")
    p.setFont(f2)
    p.drawText(QRect(12, 0, 12, _SIZE), Qt.AlignCenter, "A")
    p.end()
    return QIcon(px)
def superscript() -> QIcon:
    px, p = _new_canvas()
    p.setPen(_fg())
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
    p.setPen(_fg())
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
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, f"H{level}")
    p.end()
    return QIcon(px)


# ----- math -----

def math_inline() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(15); f.setItalic(True)
    p.setFont(f); p.setPen(_accent())
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "ƒx")
    p.end()
    return QIcon(px)


def math_block() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(13); f.setItalic(True)
    p.setFont(f); p.setPen(_accent())
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "Σxᵢ")
    p.end()
    return QIcon(px)


# ----- structure -----

def bullet_list() -> QIcon:
    px, p = _new_canvas()
    p.setBrush(QBrush(_fg())); p.setPen(Qt.NoPen)
    for y in (6, 12, 18):
        p.drawEllipse(QRect(4, y - 2, 4, 4))
    p.setPen(QPen(_fg(), _LINE_W, Qt.SolidLine, Qt.RoundCap))
    for y in (6, 12, 18):
        p.drawLine(11, y, 21, y)
    p.end()
    return QIcon(px)


def numbered_list() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Arial"); f.setPointSize(7); f.setBold(True)
    p.setFont(f); p.setPen(_fg())
    for i, y in enumerate((6, 12, 18), start=1):
        p.drawText(QRect(2, y - 6, 8, 12), Qt.AlignCenter, f"{i}.")
    p.setPen(QPen(_fg(), _LINE_W, Qt.SolidLine, Qt.RoundCap))
    for y in (6, 12, 18):
        p.drawLine(11, y, 21, y)
    p.end()
    return QIcon(px)


def link() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_accent(), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawArc(3, 8, 10, 10, 90 * 16, 180 * 16)
    p.drawArc(11, 6, 10, 10, -90 * 16, 180 * 16)
    p.drawLine(9, 12, 15, 12)
    p.end()
    return QIcon(px)


def footnote() -> QIcon:
    px, p = _new_canvas()
    f1 = QFont("Georgia"); f1.setPointSize(14)
    f2 = QFont("Georgia"); f2.setPointSize(9); f2.setBold(True)
    p.setPen(_fg())
    p.setFont(f1); p.drawText(QRect(0, 4, 14, _SIZE), Qt.AlignLeft | Qt.AlignVCenter, "T")
    p.setFont(f2); p.drawText(QRect(12, 0, 10, _SIZE), Qt.AlignLeft | Qt.AlignTop, "1")
    p.end()
    return QIcon(px)


def citation() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Arial"); f.setPointSize(11); f.setBold(True)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "[1]")
    p.end()
    return QIcon(px)


def cross_ref() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_accent2(), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(5, 14, 19, 14)
    p.drawPolyline([QPointF(15, 10), QPointF(19, 14), QPointF(15, 18)])
    f = QFont("Georgia"); f.setPointSize(8); f.setBold(True)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(0, 0, _SIZE, 10), Qt.AlignCenter, "ref")
    p.end()
    return QIcon(px)


def figure() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 1.6))
    p.setBrush(QBrush(QColor("#3a3a3a") if _dark else QColor("#f4f4f4")))
    p.drawRect(3, 5, 18, 14)
    p.setBrush(QBrush(_accent2())); p.setPen(Qt.NoPen)
    p.drawEllipse(QRect(15, 8, 4, 4))
    p.setBrush(QBrush(_accent())); p.setPen(Qt.NoPen)
    p.drawPolygon([QPointF(4, 18), QPointF(10, 11), QPointF(14, 15), QPointF(20, 18)])
    p.end()
    return QIcon(px)


def table() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 1.4))
    p.setBrush(Qt.NoBrush)
    rect = QRect(3, 5, 18, 14)
    p.drawRect(rect)
    p.drawLine(3, 10, 21, 10)
    p.drawLine(3, 14, 21, 14)
    p.drawLine(9, 5, 9, 19)
    p.drawLine(15, 5, 15, 19)
    header_bg = QColor("#2a3a5a") if _dark else QColor("#e8efff")
    p.setBrush(QBrush(header_bg)); p.setPen(Qt.NoPen)
    p.drawRect(QRect(4, 6, 16, 3))
    p.end()
    return QIcon(px)


# ----- file ops + history -----

def file_new() -> QIcon:
    px, p = _new_canvas()
    page_bg = QColor("#2d2d2d") if _dark else Qt.white
    p.setPen(QPen(_fg(), 1.6)); p.setBrush(QBrush(page_bg))
    p.drawPolygon([QPointF(5, 3), QPointF(15, 3), QPointF(19, 7),
                   QPointF(19, 21), QPointF(5, 21)])
    p.drawPolyline([QPointF(15, 3), QPointF(15, 7), QPointF(19, 7)])
    p.setPen(QPen(_accent(), 2)); p.drawLine(12, 11, 12, 17); p.drawLine(9, 14, 15, 14)
    p.end()
    return QIcon(px)


def file_open() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 1.6)); p.setBrush(QBrush(QColor("#ffd073")))
    p.drawPolygon([QPointF(3, 8), QPointF(9, 8), QPointF(11, 6),
                   QPointF(20, 6), QPointF(20, 19), QPointF(3, 19)])
    p.end()
    return QIcon(px)


def file_save() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 1.6)); p.setBrush(QBrush(_accent()))
    p.drawPolygon([QPointF(4, 4), QPointF(17, 4), QPointF(20, 7),
                   QPointF(20, 20), QPointF(4, 20)])
    p.setBrush(QBrush(Qt.white)); p.setPen(Qt.NoPen)
    p.drawRect(QRect(7, 4, 8, 5))
    p.drawRect(QRect(7, 13, 10, 7))
    p.end()
    return QIcon(px)


def undo() -> QIcon:
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(_fg(), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(5, 13)
    path.lineTo(14, 13)
    path.cubicTo(20, 13, 20, 5, 14, 5)
    p.drawPath(path)
    p.setBrush(QBrush(_fg())); p.setPen(Qt.NoPen)
    p.drawPolygon([QPointF(2, 13), QPointF(8, 9), QPointF(8, 17)])
    p.end()
    return QIcon(px)


def redo() -> QIcon:
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(_fg(), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(19, 13)
    path.lineTo(10, 13)
    path.cubicTo(4, 13, 4, 5, 10, 5)
    p.drawPath(path)
    p.setBrush(QBrush(_fg())); p.setPen(Qt.NoPen)
    p.drawPolygon([QPointF(22, 13), QPointF(16, 9), QPointF(16, 17)])
    p.end()
    return QIcon(px)


def export_pdf() -> QIcon:
    px, p = _new_canvas()
    page_bg = QColor("#2d2d2d") if _dark else Qt.white
    p.setPen(QPen(_fg(), 1.6)); p.setBrush(QBrush(page_bg))
    p.drawPolygon([QPointF(5, 3), QPointF(15, 3), QPointF(19, 7),
                   QPointF(19, 21), QPointF(5, 21)])
    f = QFont("Arial"); f.setPointSize(7); f.setBold(True)
    p.setFont(f); p.setPen(QColor("#ff5555") if _dark else QColor("#c00"))
    p.drawText(QRect(5, 10, 14, 10), Qt.AlignCenter, "PDF")
    p.end()
    return QIcon(px)


def history() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 2, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRect(4, 4, 16, 16))
    p.drawLine(12, 8, 12, 12)
    p.drawLine(12, 12, 16, 14)
    p.end()
    return QIcon(px)


def commit() -> QIcon:
    px, p = _new_canvas()
    dot_bg = QColor("#2d2d2d") if _dark else Qt.white
    p.setPen(QPen(_fg(), 2)); p.setBrush(QBrush(dot_bg))
    p.drawLine(12, 3, 12, 8); p.drawLine(12, 16, 12, 21)
    p.drawEllipse(QRect(7, 8, 10, 10))
    p.end()
    return QIcon(px)


def spell_check() -> QIcon:
    """ABC with a red wavy underline — the universal "spell check"
    toolbar glyph. Renders cleanly at 24×24 in both light and dark
    themes; the underline is the same red the highlighter uses."""
    px, p = _new_canvas()
    f = QFont("Arial"); f.setPointSize(11); f.setBold(True)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(0, 0, _SIZE, 18), Qt.AlignCenter, "ABC")
    # Wavy red underline: a three-bump zigzag, hand-drawn so it
    # reads as the same squiggle Qt's SpellCheckUnderline produces.
    p.setPen(QPen(QColor("#d8000c"), 1.4, Qt.SolidLine, Qt.RoundCap,
                  Qt.RoundJoin))
    y_top = 18
    y_bot = 21
    xs = [4, 7, 10, 13, 16, 19]
    pts: list[QPointF] = []
    for i, x in enumerate(xs):
        pts.append(QPointF(x, y_bot if i % 2 == 0 else y_top))
    p.drawPolyline(pts)
    p.end()
    return QIcon(px)


def page_break() -> QIcon:
    px, p = _new_canvas()
    page_bg = QColor("#2d2d2d") if _dark else Qt.white
    p.setPen(QPen(_fg(), 1.6)); p.setBrush(QBrush(page_bg))
    p.drawRect(QRect(4, 3, 16, 7))
    p.drawRect(QRect(4, 14, 16, 7))
    p.setPen(QPen(_accent(), 2, Qt.DashLine))
    p.drawLine(2, 12, 22, 12)
    p.end()
    return QIcon(px)


def horizontal_rule() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 2.5, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(3, 12, 21, 12)
    p.end()
    return QIcon(px)


# ----- alignment -----

def _alignment_icon(lines: list[tuple[int, int, int]]) -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 2.0, Qt.SolidLine, Qt.RoundCap))
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


def _columns_icon(n: int) -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    outer = QRect(3, 3, 18, 18)
    p.drawRect(outer)
    if n >= 2:
        col_w = outer.width() / n
        p.setPen(QPen(_accent(), 1.4, Qt.SolidLine, Qt.RoundCap))
        for c in range(n):
            x0 = outer.left() + int(col_w * c) + 2
            x1 = outer.left() + int(col_w * (c + 1)) - 2
            for dy in (7, 11, 15, 19):
                p.drawLine(x0, dy - 1, x1, dy - 1)
        p.setPen(QPen(_fg(), 1.2, Qt.DashLine))
        for c in range(1, n):
            x = outer.left() + int(col_w * c)
            p.drawLine(x, outer.top() + 2, x, outer.bottom() - 2)
    else:
        p.setPen(QPen(_accent(), 1.4, Qt.SolidLine, Qt.RoundCap))
        for dy in (7, 11, 15, 19):
            p.drawLine(outer.left() + 2, dy - 1, outer.right() - 2, dy - 1)
    p.end()
    return QIcon(px)


def one_column() -> QIcon:   return _columns_icon(1)
def two_columns() -> QIcon:  return _columns_icon(2)
def three_columns() -> QIcon: return _columns_icon(3)


def zoom_in() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRect(4, 4, 12, 12))
    p.drawLine(15, 15, 20, 20)
    p.drawLine(7, 10, 13, 10); p.drawLine(10, 7, 10, 13)
    p.end()
    return QIcon(px)


def symbol() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math")
    f.setPointSize(17); f.setItalic(True)
    p.setFont(f); p.setPen(_accent())
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "\u03b1")
    p.end()
    return QIcon(px)


def equation_builder() -> QIcon:
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(_accent(), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(4, 5, 4, 19); p.drawLine(4, 5, 6, 5); p.drawLine(4, 19, 6, 19)
    p.drawLine(20, 5, 20, 19); p.drawLine(20, 5, 18, 5); p.drawLine(20, 19, 18, 19)
    f = QFont("Cambria Math"); f.setPointSize(8); f.setItalic(True)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(6, 3, 12, 10), Qt.AlignCenter, "x")
    p.drawText(QRect(6, 13, 12, 10), Qt.AlignCenter, "y")
    p.setPen(QPen(_fg(), 1.4)); p.drawLine(7, 12, 17, 12)
    p.end()
    return QIcon(px)


def zoom_out() -> QIcon:
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRect(4, 4, 12, 12))
    p.drawLine(15, 15, 20, 20)
    p.drawLine(7, 10, 13, 10)
    p.end()
    return QIcon(px)
