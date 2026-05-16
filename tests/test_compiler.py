"""Tests for the compile-side helpers — no tectonic invocation, just the
.tex source rewrites that happen before tectonic is called."""

from pathlib import Path

from khervedoc.compiler import _rewrite_includegraphics


def test_relative_path_resolves_against_source_dir(tmp_path: Path):
    img = tmp_path / "Images" / "foo.png"
    img.parent.mkdir()
    img.write_bytes(b"")
    src = r"\includegraphics[width=0.5\textwidth]{Images/foo.png}"
    out = _rewrite_includegraphics(src, tmp_path)
    # Absolute path with forward slashes, options preserved.
    assert "Images/foo.png" in out
    assert str(tmp_path).replace("\\", "/") in out
    assert "width=0.5" in out
    # No placeholder leaked in.
    assert "missing image" not in out


def test_missing_relative_path_becomes_placeholder(tmp_path: Path):
    src = r"\includegraphics{Images/does_not_exist.png}"
    out = _rewrite_includegraphics(src, tmp_path)
    assert "\\includegraphics" not in out
    assert "missing image" in out
    # Underscore is escaped because the placeholder is typeset by LaTeX.
    assert "does\\_not\\_exist.png" in out


def test_absolute_existing_path_left_alone(tmp_path: Path):
    img = tmp_path / "a.png"
    img.write_bytes(b"")
    abs_path = str(img).replace("\\", "/")
    src = f"\\includegraphics{{{abs_path}}}"
    out = _rewrite_includegraphics(src, tmp_path)
    assert out == src


def test_no_source_dir_missing_image_still_placeholder():
    src = r"\includegraphics{Images/foo.png}"
    out = _rewrite_includegraphics(src, None)
    assert "missing image" in out


def test_multiple_includegraphics_each_handled(tmp_path: Path):
    (tmp_path / "ok.png").write_bytes(b"")
    src = (r"\includegraphics{ok.png}"
           "\n"
           r"\includegraphics{missing.png}")
    out = _rewrite_includegraphics(src, tmp_path)
    # First survives as an \includegraphics (absolute), second is a
    # placeholder.
    assert out.count("\\includegraphics") == 1
    assert "missing image" in out
    assert "missing.png" in out


def test_underscore_in_missing_path_escaped_in_placeholder(tmp_path: Path):
    """The placeholder is typeset by LaTeX, so underscores in the path
    have to be escaped or compilation fails on the placeholder itself."""
    src = r"\includegraphics{QuickStart_Preference.png}"
    out = _rewrite_includegraphics(src, tmp_path)
    assert r"\_" in out
