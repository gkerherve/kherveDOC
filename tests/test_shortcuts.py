"""Every QAction shortcut must be unique.

Qt resolves an ambiguous shortcut by firing neither action, so a clash is
silent: the menu entry still shows the key, it just never works. Ctrl+Shift+S
was bound to both Save As (via QKeySequence.SaveAs) and the Symbol picker
until v0.152.
"""

import collections
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QAction, QKeySequence  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def window():
    app = QApplication.instance() or QApplication([])
    from khervedoc.mainwindow import MainWindow

    win = MainWindow()
    yield win
    win.close()
    app.processEvents()


def _shortcut_map(win) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = collections.defaultdict(list)
    for act in win.findChildren(QAction):
        for ks in act.shortcuts():
            key = ks.toString(QKeySequence.PortableText)
            if key:
                seen[key].append(act.text())
    return seen


def test_no_duplicate_shortcuts(window):
    dupes = {k: v for k, v in _shortcut_map(window).items() if len(v) > 1}
    assert not dupes, f"ambiguous shortcuts: {dupes}"


def test_save_as_keeps_the_standard_binding(window):
    smap = _shortcut_map(window)
    save_as = QKeySequence(QKeySequence.SaveAs).toString(QKeySequence.PortableText)
    assert smap.get(save_as) == ["Save &As..."]


def test_symbol_picker_moved_off_save_as(window):
    assert _shortcut_map(window).get("Ctrl+Shift+G") == ["&Symbol..."]
