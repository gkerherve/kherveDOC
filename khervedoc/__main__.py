"""Entry point: `python -m khervedoc` opens the main window."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .mainwindow import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("kherveDOC")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
