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

    Three things are needed:
    1. A writable MPLCONFIGDIR for the font cache.
    2. The non-interactive Agg backend so Figure.savefig() never tries
       to open a display window or clash with the running Qt event loop.
    3. Pre-import matplotlib.figure to catch errors early and log them.
    """
    if not getattr(sys, "frozen", False):
        return
    cfg = os.environ.get("MPLCONFIGDIR")
    if not cfg or not os.path.isdir(cfg):
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="khervedoc-mpl-")
    os.environ.setdefault("MPLBACKEND", "Agg")
    # Eagerly test matplotlib so we can log the real error.
    _log = Path(tempfile.gettempdir()) / "khervedoc-mpl-diag.log"
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        from matplotlib.figure import Figure
        fig = Figure(figsize=(2, 0.4), dpi=100)
        fig.text(0.5, 0.5, r"$\frac{1}{2}$", fontsize=12,
                 ha="center", va="center", math_fontfamily="cm")
        from io import BytesIO
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        with open(_log, "w") as fh:
            fh.write(f"OK — rendered {buf.tell()} bytes\n")
            fh.write(f"matplotlib {matplotlib.__version__}\n")
            fh.write(f"backend: {matplotlib.get_backend()}\n")
            fh.write(f"MPLCONFIGDIR: {os.environ.get('MPLCONFIGDIR')}\n")
            fh.write(f"data path: {matplotlib.get_data_path()}\n")
    except Exception:
        import traceback
        with open(_log, "w") as fh:
            fh.write("FAILED\n")
            traceback.print_exc(file=fh)


def _seed_tectonic_cache() -> None:
    """Copy bundled tectonic TeX packages to the user's cache on first run.

    The PyInstaller bundle ships a pre-populated tectonic cache so that
    all document classes work offline out of the box.  We copy any files
    the user doesn't already have into tectonic's standard cache location.
    """
    if not getattr(sys, "frozen", False):
        return
    import shutil
    bundled = Path(sys._MEIPASS) / "khervedoc" / "tectonic_cache"
    if not bundled.is_dir():
        return
    # Tectonic's cache on Windows: %LOCALAPPDATA%/TectonicProject/Tectonic/bundles
    dest = (Path.home() / "AppData" / "Local"
            / "TectonicProject" / "Tectonic" / "bundles")
    dest.mkdir(parents=True, exist_ok=True)
    # Copy everything that doesn't already exist at the destination.
    for src_path in bundled.rglob("*"):
        rel = src_path.relative_to(bundled)
        dst_path = dest / rel
        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
        elif not dst_path.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)


def main() -> int:
    _configure_matplotlib_for_frozen()
    _seed_tectonic_cache()
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
