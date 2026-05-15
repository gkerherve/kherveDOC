"""Entry point: `python -m khervedoc` opens the main window."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .mainwindow import MainWindow


def _apply_light_palette(app: QApplication) -> None:
    """Force a light Fusion theme so the app is identical regardless of the
    user's Windows colour scheme (the dark Windows theme made the toolbar
    icons invisible by default)."""
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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("kherveDOC")
    _apply_light_palette(app)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
