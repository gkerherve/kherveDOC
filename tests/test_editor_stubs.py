"""In-editor stub format for Figure / Table blocks.

The editor keeps each Figure / Table inside a single QTextBlock and
encodes the model's fields into the block's text. The text was
previously a single line like

    [TABLE] r1c1\\tr1c2\\u2028r2c1\\tr2c2||caption|label|alignment

which leaked developer noise (the prefix) and `|` separators into the
on-screen view. The new format puts metadata on its own visible lines
and drops the prefix entirely — the block's userState already
identifies the type.

These tests pin down the new format and verify that the old format
still parses (so any in-flight editor session migrates cleanly)."""

import importlib

import pytest


def _editor_module():
    """Import khervedoc.editor without booting Qt — we only need the
    pure helpers. Importing the module triggers a PySide6 import; skip
    the test if it isn't available."""
    pyside = pytest.importorskip("PySide6")
    return importlib.import_module("khervedoc.editor")


def test_table_stub_emits_meta_lines_not_pipe_separated(tmp_path):
    ed = _editor_module()
    from khervedoc.model import Table
    t = Table(rows=[["A", "B"], ["C", "D"]],
              caption="Cap", label="tab:x", alignment="lr")
    stub = ed._table_stub(t)
    lines = stub.split(ed._LINE_SEP)
    # Rows come first, then one labelled line per metadata field.
    assert lines[0] == "A\tB"
    assert lines[1] == "C\tD"
    assert lines[2] == "Caption: Cap"
    assert lines[3] == "Label: tab:x"
    assert lines[4] == "Alignment: lr"
    # No developer prefix leaked into the visible text.
    assert "[TABLE]" not in stub
    # No |-separator footer leaked in either.
    assert "||" not in stub


def test_figure_stub_emits_meta_lines_not_pipe_separated():
    ed = _editor_module()
    from khervedoc.model import Figure
    f = Figure(path="img/foo.png", caption="A photo",
               label="fig:1", width="0.5\\textwidth")
    stub = ed._figure_stub(f)
    lines = stub.split(ed._LINE_SEP)
    assert lines[0] == "img/foo.png"
    assert lines[1] == "Caption: A photo"
    assert lines[2] == "Label: fig:1"
    assert lines[3] == r"Width: 0.5\textwidth"
    assert "[FIGURE]" not in stub


def test_split_stub_meta_pulls_labels_off_the_end():
    ed = _editor_module()
    body = ed._LINE_SEP.join([
        "row1\tcell",
        "row2\tcell",
        "Caption: hello",
        "Label: tab:foo",
        "Alignment: lr",
    ])
    lines, meta = ed._split_stub_meta(body)
    assert lines == ["row1\tcell", "row2\tcell"]
    assert meta == {"Caption": "hello", "Label": "tab:foo",
                    "Alignment": "lr"}


def test_split_stub_meta_stops_at_first_non_meta_line():
    """A content line that happens to be followed by meta lines is
    fine, but a meta-looking line buried inside content must not be
    accidentally peeled off — only the trailing block of meta lines
    counts."""
    ed = _editor_module()
    body = ed._LINE_SEP.join([
        "Caption: this is a row that contains the word Caption",
        "row two",
        "Caption: real",
    ])
    lines, meta = ed._split_stub_meta(body)
    assert meta == {"Caption": "real"}
    assert lines[-1] == "row two"
    assert len(lines) == 2
