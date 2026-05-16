"""Entry point: `python -m khervedoc` opens the main window."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .mainwindow import MainWindow


def _apply_light_palette(app: QApplication) -> None:
    """Force a light Fusion theme so the app is identical regardless of the
    user's Windows colour scheme."""
    app.setStyle("Fusion")

    pal = QPalette()
    white = QColor("#ffffff")
    near_white = QColor("#f7f7f7")
    base_text = QColor("#1c1c1c")
    accent = QColor("#1a6dd8")
    disabled = QColor("#9a9a9a")

    pal.setColor(QPalette.Window, near_white)
    pal.setColor(QPalette.WindowText, base_text)
    pal.setColor(QPalette.Base, white)
    pal.setColor(QPalette.AlternateBase, QColor("#eef1f5"))
    pal.setColor(QPalette.ToolTipBase, white)
    pal.setColor(QPalette.ToolTipText, base_text)
    pal.setColor(QPalette.Text, base_text)
    pal.setColor(QPalette.Button, near_white)
    pal.setColor(QPalette.ButtonText, base_text)
    pal.setColor(QPalette.BrightText, QColor("#ff3333"))
    pal.setColor(QPalette.Link, accent)
    pal.setColor(QPalette.Highlight, accent)
    pal.setColor(QPalette.HighlightedText, white)
    pal.setColor(QPalette.PlaceholderText, QColor("#888"))

    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
                 QPalette.Highlight):
        pal.setColor(QPalette.Disabled, role, disabled)

    app.setPalette(pal)


def _apply_dark_palette(app: QApplication) -> None:
    """Dark Fusion theme."""
    app.setStyle("Fusion")

    pal = QPalette()
    dark_bg = QColor("#1e1e1e")
    dark_surface = QColor("#2d2d2d")
    dark_text = QColor("#d4d4d4")
    accent = QColor("#4da6ff")
    disabled = QColor("#606060")

    pal.setColor(QPalette.Window, dark_surface)
    pal.setColor(QPalette.WindowText, dark_text)
    pal.setColor(QPalette.Base, dark_bg)
    pal.setColor(QPalette.AlternateBase, QColor("#3a3a3a"))
    pal.setColor(QPalette.ToolTipBase, dark_surface)
    pal.setColor(QPalette.ToolTipText, dark_text)
    pal.setColor(QPalette.Text, dark_text)
    pal.setColor(QPalette.Button, dark_surface)
    pal.setColor(QPalette.ButtonText, dark_text)
    pal.setColor(QPalette.BrightText, QColor("#ff5555"))
    pal.setColor(QPalette.Link, accent)
    pal.setColor(QPalette.Highlight, accent)
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.PlaceholderText, QColor("#777"))

    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText,
                 QPalette.Highlight):
        pal.setColor(QPalette.Disabled, role, disabled)

    app.setPalette(pal)


def apply_theme(app: QApplication, dark: bool) -> None:
    """Apply light or dark palette. Callable from mainwindow at runtime."""
    if dark:
        _apply_dark_palette(app)
    else:
        _apply_light_palette(app)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("kherveDOC")
    settings = QSettings("kherveDOC", "kherveDOC")
    dark = settings.value("theme_dark", False, type=bool)
    apply_theme(app, dark)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
