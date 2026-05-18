"""Entry point: `python -m khervedoc` opens the main window."""
from __future__ import annotations

import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from . import themes
from .mainwindow import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("kherveDOC")
    settings = QSettings("kherveDOC", "kherveDOC")
    # Migrate legacy boolean → named theme on first run after upgrade.
    theme_name = settings.value("theme_name", "")
    if not theme_name:
        dark = settings.value("theme_dark", False, type=bool)
        theme_name = "Dark" if dark else "Light"
    theme = themes.apply_theme(app, theme_name)
    win = MainWindow(theme_name=theme_name)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
