"""Entry point: `python -m khervedoc` opens the main window."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from . import icons, themes
from .mainwindow import MainWindow


def _configure_matplotlib_for_frozen() -> None:
    """Ensure matplotlib works correctly in a PyInstaller bundle.

    Two things are needed:
    1. A writable MPLCONFIGDIR for the font cache.
    2. The non-interactive Agg backend so Figure.savefig() never tries
       to open a display window or clash with the running Qt event loop.
    """
    if not getattr(sys, "frozen", False):
        return
    cfg = os.environ.get("MPLCONFIGDIR")
    if not cfg or not os.path.isdir(cfg):
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="khervedoc-mpl-")
    os.environ.setdefault("MPLBACKEND", "Agg")


def main() -> int:
    _configure_matplotlib_for_frozen()
    app = QApplication(sys.argv)
    app.setApplicationName("KherveTeX")
    app.setWindowIcon(icons.app_icon())
    settings = QSettings("kherveDOC", "kherveDOC")
    # Migrate legacy boolean → named theme on first run after upgrade.
    theme_name = settings.value("theme_name", "")
    if not theme_name:
        dark = settings.value("theme_dark", False, type=bool)
        theme_name = "Dark" if dark else "Light"
    theme = themes.apply_theme(app, theme_name)
    win = MainWindow(theme_name=theme_name)
    win.show()
    # Open a file passed on the command line (e.g. double-click association).
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        path = Path(args[0])
        if path.exists():
            win._open_path(path)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
