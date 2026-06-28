"""Entry point: ``python -m kherveslide`` opens the slide designer."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from khervedoc import icons, themes

from .window import SlideWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("kherveSlide")
    app.setWindowIcon(icons.app_icon())
    settings = QSettings("kherveDOC", "kherveSlide")
    theme_name = settings.value("theme_name", "Light")
    themes.apply_theme(app, theme_name)
    icons.set_dark(themes.is_dark(theme_name))
    win = SlideWindow()
    win.show()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and Path(args[0]).exists():
        win._open_path_arg = Path(args[0])
        try:
            from .model import deck_from_json
            win.deck = deck_from_json(Path(args[0]).read_text(encoding="utf-8"))
            win.path = Path(args[0])
            win.current = 0
            win._reload_all()
        except Exception:
            pass
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
