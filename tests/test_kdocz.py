"""Round-trip tests for the .kdocz ZIP container format."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from khervedoc.kdocz import (
    DOC_BASENAME, MANIFEST_BASENAME, is_kdocz_path, load_kdocz, save_kdocz,
)
from khervedoc.model import (
    Document, DocMeta, Figure, Paragraph, Section, Text, Title,
)


def _make_doc(image_path: str = "") -> Document:
    children = [
        Title(children=[Text(text="My doc")]),
        Section(level=1, children=[Text(text="Intro")]),
        Paragraph(children=[Text(text="hello")]),
    ]
    if image_path:
        children.append(Figure(path=image_path, caption="Fig", label="fig:1"))
    return Document(meta=DocMeta(title="My doc"), children=children)


def test_is_kdocz_path():
    assert is_kdocz_path("/x/foo.kdocz")
    assert is_kdocz_path("foo.KDOCZ")
    assert not is_kdocz_path("foo.kdoc.json")
    assert not is_kdocz_path("foo.tex")


def test_roundtrip_without_images(tmp_path: Path):
    doc = _make_doc()
    out = tmp_path / "doc.kdocz"
    save_kdocz(doc, out)
    assert out.exists()

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert MANIFEST_BASENAME in names
    assert DOC_BASENAME in names

    loaded, extract_dir = load_kdocz(out, extract_to=tmp_path / "extracted")
    assert loaded == doc


def test_roundtrip_bundles_referenced_image(tmp_path: Path):
    # Plant a fake image alongside the soon-to-be-saved .kdocz.
    img_src = tmp_path / "photo.png"
    img_src.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")

    doc = _make_doc(image_path=str(img_src))
    out = tmp_path / "with-image.kdocz"
    save_kdocz(doc, out)

    # Archive should now contain the image under images/figure_001.png.
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    image_entries = [n for n in names if n.startswith("images/")]
    assert len(image_entries) == 1
    assert image_entries[0].endswith(".png")

    # Loading rewrites the Figure path to point at the extracted file.
    loaded, extract_dir = load_kdocz(out, extract_to=tmp_path / "extracted")
    figs = [c for c in loaded.children if isinstance(c, Figure)]
    assert len(figs) == 1
    assert Path(figs[0].path).exists()
    assert Path(figs[0].path).read_bytes().startswith(b"\x89PNG")


def test_missing_image_keeps_original_path(tmp_path: Path):
    # Path points at a non-existent file; saving should still succeed and
    # keep the original path so the user can re-link later.
    doc = _make_doc(image_path="not-on-disk.png")
    out = tmp_path / "missing.kdocz"
    save_kdocz(doc, out)
    with zipfile.ZipFile(out) as zf:
        assert not any(n.startswith("images/") for n in zf.namelist())
    loaded, _ = load_kdocz(out, extract_to=tmp_path / "extract2")
    figs = [c for c in loaded.children if isinstance(c, Figure)]
    assert figs[0].path == "not-on-disk.png"


def test_duplicate_image_paths_bundled_once(tmp_path: Path):
    img = tmp_path / "shared.jpg"
    img.write_bytes(b"\xff\xd8\xff JPEG_FAKE")
    doc = Document(
        meta=DocMeta(),
        children=[
            Figure(path=str(img), caption="A"),
            Figure(path=str(img), caption="B"),
        ],
    )
    out = tmp_path / "dedupe.kdocz"
    save_kdocz(doc, out)
    with zipfile.ZipFile(out) as zf:
        image_entries = [n for n in zf.namelist() if n.startswith("images/")]
    assert len(image_entries) == 1


def test_schema_version_too_new_rejected(tmp_path: Path):
    out = tmp_path / "future.kdocz"
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr(
            MANIFEST_BASENAME,
            '{"format":"kdocz","schema_version":99,"app":"kherveDOC"}')
        zf.writestr(DOC_BASENAME, '{"type":"Document","meta":{},"children":[]}')
    with pytest.raises(ValueError, match="newer kherveDOC"):
        load_kdocz(out, extract_to=tmp_path / "extract3")
