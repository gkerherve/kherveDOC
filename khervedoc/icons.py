"""Programmatically-drawn toolbar icons.

QPainter draws each icon onto a transparent QPixmap so we never ship binary
image files. Every icon function returns a QIcon.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QIcon, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF,
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


# The classic "LaTeX" logo drawn on the page: L, a raised small A, T, a
# lowered E, X. Each entry is (char, scale, baseline-shift, kern-after),
# all but the char in units of the cap size F, so the pieces kern like
# the real logo.
_LATEX_SERIF = "Times New Roman"
_LATEX_PIECES = (
    ("L", 1.00, 0.00, -0.28),
    ("A", 0.72, -0.32, -0.06),
    ("T", 1.00, 0.00, -0.13),
    ("E", 1.00, 0.24, -0.05),
    ("X", 1.00, 0.00, 0.00),
)


def _latex_advance(ch: str, px: float) -> float:
    f = QFont(_LATEX_SERIF)
    f.setPixelSize(max(1, int(px)))
    return QFontMetricsF(f).horizontalAdvance(ch)


def _latex_width(F: float) -> float:
    return sum(_latex_advance(ch, sc * F) + kern * F
               for ch, sc, _dy, kern in _LATEX_PIECES)


def _draw_latex(p: QPainter, cx: float, cy: float, avail: float,
                color: str) -> None:
    """Draw the classic LaTeX logo centred at (cx, cy), fit to *avail* wide."""
    F = 100.0
    F = avail / (_latex_width(F) / F)
    x = cx - _latex_width(F) / 2.0
    base = cy + 0.34 * F
    p.setPen(QColor(color))
    for ch, sc, dy, kern in _LATEX_PIECES:
        f = QFont(_LATEX_SERIF)
        f.setPixelSize(max(1, int(sc * F)))
        p.setFont(f)
        p.drawText(QPointF(x, base + dy * F), ch)
        x += _latex_advance(ch, sc * F) + kern * F


def _draw_ktex(p: QPainter, rect: QRectF, color: str) -> None:
    """Draw 'KTeX' centred in *rect* with a normal bold font, fit to width."""
    text = "KTeX"
    avail = rect.width() * 0.86
    font = QFont("Segoe UI")
    font.setBold(True)
    size = 4
    while size < rect.height():
        font.setPixelSize(size + 1)
        fm = QFontMetricsF(font)
        if fm.horizontalAdvance(text) > avail or fm.height() > rect.height():
            break
        size += 1
    font.setPixelSize(max(4, size))
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(rect, Qt.AlignCenter, text)


def _draw_page(p: QPainter, box: QRectF) -> None:
    """A white document page with a folded corner, bearing the LaTeX logo."""
    x, y, w, h = box.x(), box.y(), box.width(), box.height()
    fold = w * 0.22
    page = QPainterPath()
    page.moveTo(x, y)
    page.lineTo(x + w - fold, y)
    page.lineTo(x + w, y + fold)
    page.lineTo(x + w, y + h)
    page.lineTo(x, y + h)
    page.closeSubpath()
    p.setPen(QPen(QColor("#cfd6e0"), max(1.0, w * 0.02)))
    p.setBrush(QColor("#ffffff"))
    p.drawPath(page)
    ear = QPainterPath()                       # the dog-ear fold
    ear.moveTo(x + w - fold, y)
    ear.lineTo(x + w - fold, y + fold)
    ear.lineTo(x + w, y + fold)
    p.setBrush(Qt.NoBrush)
    p.drawPath(ear)
    _draw_latex(p, x + w / 2, y + h * 0.58, w * 0.70, "#1a1a1a")


def app_pixmap(sz: int) -> QPixmap:
    """One size of the app icon: 'KTeX' above a page bearing the LaTeX
    logo, on a rounded blue tile."""
    px = QPixmap(sz, sz)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    m = sz * 0.06
    radius = sz * 0.22
    rect = QRectF(m, m, sz - 2 * m, sz - 2 * m)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1a6dd8"))              # the blue tile
    p.drawRoundedRect(rect, radius, radius)
    pen = QPen(QColor("#155bb5"))
    pen.setWidthF(max(1.0, sz * 0.02))
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect, radius, radius)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    _draw_ktex(p, QRectF(x, y + h * 0.05, w, h * 0.33), "#ffffff")
    pw, ph = w * 0.54, h * 0.48
    _draw_page(p, QRectF(x + (w - pw) / 2.0, y + h * 0.45, pw, ph))
    p.end()
    return px


def app_icon() -> QIcon:
    """Application icon: the 'KTeX' wordmark above a page bearing the
    LaTeX logo, on a rounded blue tile.

    Rendered at several sizes so the taskbar, title bar, and Alt-Tab all
    get a sharp copy.
    """
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(sz))
    return icon


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


def drawing() -> QIcon:
    """Pencil over a small wavy line — "freehand drawing"."""
    px, p = _new_canvas()
    # Wavy line below to suggest a sketch.
    p.setPen(QPen(_accent(), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    path = QPainterPath()
    path.moveTo(3, 18)
    path.cubicTo(QPointF(7, 14), QPointF(11, 22), QPointF(15, 18))
    path.cubicTo(QPointF(18, 16), QPointF(20, 20), QPointF(22, 18))
    p.drawPath(path)
    # Pencil — angled rectangle + triangular tip.
    p.setPen(QPen(_fg(), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QBrush(_accent2()))
    pencil = QPolygonF([
        QPointF(15, 3), QPointF(19, 7), QPointF(9, 17),
        QPointF(5, 13),
    ])
    p.drawPolygon(pencil)
    # Pencil tip
    p.setBrush(QBrush(_fg()))
    p.drawPolygon(QPolygonF([
        QPointF(5, 13), QPointF(9, 17), QPointF(4, 18),
    ]))
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


def project_open() -> QIcon:
    """Folder with stacked pages — represents a multi-chapter project."""
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(_fg(), 1.4)
    p.setPen(pen)
    # Back page
    p.setBrush(QBrush(QColor("#c8daf0") if not _dark else QColor("#3a4a60")))
    p.drawRect(QRect(7, 4, 13, 16))
    # Front page
    p.setBrush(QBrush(QColor("#e8f0fe") if not _dark else QColor("#4a5a70")))
    p.drawRect(QRect(4, 6, 13, 16))
    # Lines on front page
    p.setPen(QPen(_fg(), 0.8))
    for y in (10, 13, 16, 19):
        p.drawLine(6, y, 15, y)
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


def branch() -> QIcon:
    """Git branch icon — a forking line with two dots."""
    px, p = _new_canvas()
    col = _accent()
    p.setPen(QPen(col, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    # Main trunk
    p.drawLine(8, 4, 8, 20)
    # Fork line
    p.drawLine(8, 12, 16, 6)
    # Dots
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(col))
    p.drawEllipse(QRect(5, 17, 6, 6))  # trunk tip
    p.drawEllipse(QRect(13, 3, 6, 6))  # fork tip
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


def chemistry() -> QIcon:
    """Erlenmeyer flask with an accent-coloured liquid."""
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)

    body = QPainterPath()
    body.moveTo(9.5, 4)
    body.lineTo(9.5, 9.5)
    body.lineTo(4, 19.5)
    body.lineTo(20, 19.5)
    body.lineTo(14.5, 9.5)
    body.lineTo(14.5, 4)

    liquid = QPainterPath()
    liquid.moveTo(6.9, 14.5)
    liquid.lineTo(4, 19.5)
    liquid.lineTo(20, 19.5)
    liquid.lineTo(17.1, 14.5)
    liquid.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(_accent())
    p.drawPath(liquid)

    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(_fg(), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(body)
    p.drawLine(8, 4, 16, 4)  # lip
    p.end()
    return QIcon(px)


def chemfig_structure() -> QIcon:
    """A benzene hexagon with the accent-coloured aromatic ring inside —
    the chemical-structure editor."""
    import math as _math
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    cx, cy, r = 12.0, 12.0, 8.0
    pts = [QPointF(cx + r * _math.cos(_math.radians(60 * i - 90)),
                   cy + r * _math.sin(_math.radians(60 * i - 90)))
           for i in range(6)]
    hexagon = QPolygonF(pts)
    p.setPen(QPen(_fg(), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(hexagon)
    # inner aromatic ring
    p.setPen(QPen(_accent(), 1.4))
    p.drawEllipse(QPointF(cx, cy), r * 0.5, r * 0.5)
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


def fit_width() -> QIcon:
    """Double-headed horizontal arrow between two vertical bars."""
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(_fg(), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    # Left bar
    p.drawLine(4, 5, 4, 19)
    # Right bar
    p.drawLine(20, 5, 20, 19)
    # Horizontal arrow shaft
    p.drawLine(6, 12, 18, 12)
    # Left arrowhead
    p.drawLine(6, 12, 9, 9); p.drawLine(6, 12, 9, 15)
    # Right arrowhead
    p.drawLine(18, 12, 15, 9); p.drawLine(18, 12, 15, 15)
    p.end()
    return QIcon(px)


# ---- equation builder category icons ----

def eq_fractions() -> QIcon:
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    f = QFont("Cambria Math"); f.setPointSize(7); f.setItalic(True)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(4, 2, 16, 10), Qt.AlignCenter, "a+b")
    p.setPen(QPen(_fg(), 1.4)); p.drawLine(5, 12, 19, 12)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(4, 12, 16, 10), Qt.AlignCenter, "c")
    p.end()
    return QIcon(px)


def eq_sums() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(16)
    p.setFont(f); p.setPen(_accent())
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "\u03a3")
    p.end()
    return QIcon(px)


def eq_integrals() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(18)
    p.setFont(f); p.setPen(_accent())
    p.drawText(QRect(0, -1, _SIZE, _SIZE), Qt.AlignCenter, "\u222b")
    p.end()
    return QIcon(px)


def eq_scripts() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(12); f.setItalic(True)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(2, 4, 14, 16), Qt.AlignCenter, "x")
    f2 = QFont("Cambria Math"); f2.setPointSize(7); f2.setItalic(True)
    p.setFont(f2); p.setPen(_accent())
    p.drawText(QRect(13, 2, 10, 10), Qt.AlignLeft | Qt.AlignTop, "2")
    p.drawText(QRect(13, 12, 10, 10), Qt.AlignLeft | Qt.AlignTop, "i")
    p.end()
    return QIcon(px)


def eq_derivatives() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(8); f.setItalic(True)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(2, 2, 20, 10), Qt.AlignCenter, "dy")
    p.setPen(QPen(_fg(), 1.2)); p.drawLine(5, 12, 19, 12)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(2, 12, 20, 10), Qt.AlignCenter, "dx")
    p.end()
    return QIcon(px)


def eq_greek() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(11); f.setItalic(True)
    p.setFont(f); p.setPen(_accent())
    p.drawText(QRect(-2, 0, _SIZE, _SIZE), Qt.AlignCenter, "\u03b1\u03b2")
    p.end()
    return QIcon(px)


def eq_vectors() -> QIcon:
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    # Arrow over x
    p.setPen(QPen(_accent(), 1.4, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(6, 7, 18, 7)
    p.drawLine(15, 4, 18, 7); p.drawLine(15, 10, 18, 7)
    f = QFont("Cambria Math"); f.setPointSize(11); f.setItalic(True)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(0, 6, _SIZE, 16), Qt.AlignCenter, "x")
    p.end()
    return QIcon(px)


def eq_brackets() -> QIcon:
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(_accent(), 1.6, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    # Left parenthesis arc
    p.drawArc(4, 3, 8, 18, 110 * 16, 140 * 16)
    # Right parenthesis arc
    p.drawArc(12, 3, 8, 18, -70 * 16, 140 * 16)
    p.end()
    return QIcon(px)


def eq_relations() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(12)
    p.setFont(f); p.setPen(_fg())
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "\u2264\u2265")
    p.end()
    return QIcon(px)


def eq_functions() -> QIcon:
    px, p = _new_canvas()
    f = QFont("Cambria Math"); f.setPointSize(10)
    p.setFont(f); p.setPen(_accent())
    p.drawText(QRect(0, 0, _SIZE, _SIZE), Qt.AlignCenter, "sin")
    p.end()
    return QIcon(px)


def eq_environments() -> QIcon:
    px, p = _new_canvas()
    p.setRenderHint(QPainter.Antialiasing, True)
    # Left brace
    p.setPen(QPen(_accent(), 1.6, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(8, 4, 6, 4); p.drawLine(6, 4, 6, 10)
    p.drawLine(6, 10, 4, 12); p.drawLine(4, 12, 6, 14)
    p.drawLine(6, 14, 6, 20); p.drawLine(6, 20, 8, 20)
    # Lines representing equation rows
    p.setPen(QPen(_fg(), 1.2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(10, 8, 20, 8)
    p.drawLine(10, 12, 18, 12)
    p.drawLine(10, 16, 20, 16)
    p.end()
    return QIcon(px)


# ----- review -----

def highlight(color: str = "#FFFF00") -> QIcon:
    """Marker pen icon filled with the given highlight colour."""
    px, p = _new_canvas()
    # Marker pen body (tilted rectangle)
    pen_path = QPainterPath()
    pen_path.moveTo(6, 18)
    pen_path.lineTo(10, 4)
    pen_path.lineTo(18, 6)
    pen_path.lineTo(14, 20)
    pen_path.closeSubpath()
    p.setBrush(QBrush(QColor(color)))
    p.setPen(QPen(_fg(), 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(pen_path)
    # Tip
    p.setPen(QPen(_fg(), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(6, 18), QPointF(4, 22))
    p.end()
    return QIcon(px)


def comment() -> QIcon:
    """Speech bubble icon for reviewer comments."""
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QBrush(QColor("#e0ecff") if not _dark else QColor("#2a4060")))
    # Bubble body
    bubble = QPainterPath()
    bubble.addRoundedRect(QRectF(2, 3, 20, 14), 3, 3)
    p.drawPath(bubble)
    # Tail
    tail = QPolygonF([QPointF(6, 17), QPointF(10, 17), QPointF(5, 22)])
    p.drawPolygon(tail)
    # Lines inside bubble
    p.setPen(QPen(_fg(), 1.0, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(6, 8, 18, 8)
    p.drawLine(6, 12, 15, 12)
    p.end()
    return QIcon(px)


def accept_change() -> QIcon:
    """Green checkmark for accepting a comment/change."""
    px, p = _new_canvas()
    p.setPen(QPen(QColor("#2e7d32"), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPointF(5, 13), QPointF(10, 18), QPointF(19, 6)])
    p.end()
    return QIcon(px)


def reject_change() -> QIcon:
    """Red X for rejecting a comment/change."""
    px, p = _new_canvas()
    p.setPen(QPen(QColor("#c62828"), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(QPointF(6, 6), QPointF(18, 18))
    p.drawLine(QPointF(18, 6), QPointF(6, 18))
    p.end()
    return QIcon(px)


def prev_comment() -> QIcon:
    """Left arrow for navigating to previous comment."""
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPointF(14, 6), QPointF(7, 12), QPointF(14, 18)])
    p.drawLine(QPointF(7, 12), QPointF(20, 12))
    p.end()
    return QIcon(px)


def next_comment() -> QIcon:
    """Right arrow for navigating to next comment."""
    px, p = _new_canvas()
    p.setPen(QPen(_fg(), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPointF(10, 6), QPointF(17, 12), QPointF(10, 18)])
    p.drawLine(QPointF(4, 12), QPointF(17, 12))
    p.end()
    return QIcon(px)


# ----- compile / auto-compile -----

def compile_pdf() -> QIcon:
    """Play-triangle over a small PDF page — "compile now" button."""
    px, p = _new_canvas()
    page_bg = QColor("#2d2d2d") if _dark else Qt.white
    p.setPen(QPen(_fg(), 1.2)); p.setBrush(QBrush(page_bg))
    p.drawPolygon([QPointF(3, 2), QPointF(13, 2), QPointF(16, 5),
                   QPointF(16, 18), QPointF(3, 18)])
    green = QColor("#5fba7d") if _dark else QColor("#2a8c4a")
    p.setPen(Qt.NoPen); p.setBrush(QBrush(green))
    p.drawPolygon([QPointF(13, 8), QPointF(13, 20), QPointF(22, 14)])
    p.end()
    return QIcon(px)


def auto_compile_on() -> QIcon:
    """Circular arrow (sync) — auto-compile is ON."""
    px, p = _new_canvas()
    green = QColor("#5fba7d") if _dark else QColor("#2a8c4a")
    p.setPen(QPen(green, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.arcMoveTo(QRectF(4, 4, 16, 16), 60)
    path.arcTo(QRectF(4, 4, 16, 16), 60, -300)
    p.drawPath(path)
    tip = path.currentPosition()
    p.setPen(Qt.NoPen); p.setBrush(QBrush(green))
    p.drawPolygon([QPointF(tip.x() - 4, tip.y() - 1),
                   QPointF(tip.x() + 1, tip.y() - 5),
                   QPointF(tip.x() + 1, tip.y() + 3)])
    p.end()
    return QIcon(px)


def auto_compile_off() -> QIcon:
    """Circular arrow (sync) with a diagonal strike — auto-compile is OFF."""
    px, p = _new_canvas()
    grey = QColor("#888") if _dark else QColor("#999")
    p.setPen(QPen(grey, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.arcMoveTo(QRectF(4, 4, 16, 16), 60)
    path.arcTo(QRectF(4, 4, 16, 16), 60, -300)
    p.drawPath(path)
    tip = path.currentPosition()
    p.setPen(Qt.NoPen); p.setBrush(QBrush(grey))
    p.drawPolygon([QPointF(tip.x() - 4, tip.y() - 1),
                   QPointF(tip.x() + 1, tip.y() - 5),
                   QPointF(tip.x() + 1, tip.y() + 3)])
    red = QColor("#ff5555") if _dark else QColor("#c00")
    p.setPen(QPen(red, 2.4, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(5, 5), QPointF(19, 19))
    p.end()
    return QIcon(px)


def compile_no_images() -> QIcon:
    """Page with a crossed-out image icon — compile without images."""
    px, p = _new_canvas()
    page_bg = QColor("#2d2d2d") if _dark else Qt.white
    p.setPen(QPen(_fg(), 1.2)); p.setBrush(QBrush(page_bg))
    p.drawPolygon([QPointF(3, 2), QPointF(13, 2), QPointF(16, 5),
                   QPointF(16, 18), QPointF(3, 18)])
    # Small "mountain + sun" image icon on the page
    grey = QColor("#999") if _dark else QColor("#888")
    p.setPen(QPen(grey, 1.0)); p.setBrush(Qt.NoBrush)
    p.drawRect(5, 7, 8, 6)
    # Diagonal cross-out
    red = QColor("#ff5555") if _dark else QColor("#c00")
    p.setPen(QPen(red, 2.0, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(4, 6), QPointF(14, 14))
    p.end()
    return QIcon(px)


def compile_range() -> QIcon:
    """Page with two horizontal bracket lines — compile-range toggle."""
    px, p = _new_canvas()
    page_bg = QColor("#2d2d2d") if _dark else Qt.white
    p.setPen(QPen(_fg(), 1.2)); p.setBrush(QBrush(page_bg))
    p.drawPolygon([QPointF(3, 2), QPointF(13, 2), QPointF(16, 5),
                   QPointF(16, 18), QPointF(3, 18)])
    green = QColor("#5fba7d") if _dark else QColor("#2a8c4a")
    p.setPen(QPen(green, 1.8, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(5, 8), QPointF(14, 8))
    red = QColor("#ff5555") if _dark else QColor("#c00")
    p.setPen(QPen(red, 1.8, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(5, 14), QPointF(14, 14))
    p.end()
    return QIcon(px)
