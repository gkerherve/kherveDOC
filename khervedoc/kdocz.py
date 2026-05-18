"""Single-file `.kdocz` container — a ZIP holding the document JSON plus
every image the document references.

Layout inside the archive:

    manifest.json   - schema version + producing app
    document.json   - the KherveTeX document model, image paths rewritten
                      to point at the bundled files (e.g. "images/figure_001.png")
    images/         - the bundled image files referenced by Figure nodes

Saving: copies every Figure-referenced file into the archive and rewrites
the in-archive document's paths to those bundled locations, so reopening
the file on another machine still finds the images.

Loading: extracts the archive into a directory (a temp dir by default)
and rewrites the Figure paths to absolute paths under that directory, so
the LaTeX compiler can pick them up via the existing \\includegraphics
machinery.
"""
from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path

from .model import Document, Figure, from_json, to_json


SCHEMA_VERSION = 1
MANIFEST_BASENAME = "manifest.json"
DOC_BASENAME = "document.json"
IMAGES_DIR = "images"


def is_kdocz_path(path: Path | str) -> bool:
    return str(path).lower().endswith(".kdocz")


def save_kdocz(doc: Document, out_path: Path) -> None:
    """Write `doc` and all its referenced images to `out_path`.

    Figure nodes whose `path` resolves to a real file on disk are copied
    into the archive and have their stored path rewritten to point inside
    the archive. Missing files are kept as-is so the user can re-link them
    later without losing the rest of the document.
    """
    out_path = Path(out_path)
    rewritten_children: list = []
    images_to_bundle: list[tuple[Path, str]] = []  # (source, arcname)
    by_source: dict[str, str] = {}                 # de-dupe identical paths
    counter = 1

    for block in doc.children:
        if isinstance(block, Figure) and block.path:
            src = block.path
            if src in by_source:
                arc_name = by_source[src]
            else:
                src_path = Path(src)
                # Fall back to looking next to the saved .kdocz for relative
                # references — this is the common case for .docx-imported
                # documents that haven't been saved yet.
                if not src_path.is_absolute() and not src_path.exists():
                    candidate = out_path.parent / src
                    if candidate.exists():
                        src_path = candidate
                if src_path.exists():
                    ext = src_path.suffix or ".png"
                    arc_name = f"{IMAGES_DIR}/figure_{counter:03d}{ext}"
                    counter += 1
                    images_to_bundle.append((src_path, arc_name))
                    by_source[src] = arc_name
                else:
                    arc_name = src
                    by_source[src] = arc_name
            rewritten_children.append(replace(block, path=arc_name))
        else:
            rewritten_children.append(block)

    archive_doc = Document(meta=doc.meta, children=rewritten_children)

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_BASENAME, json.dumps(
            {"format": "kdocz", "schema_version": SCHEMA_VERSION,
             "app": "KherveTeX"},
            indent=2))
        zf.writestr(DOC_BASENAME, to_json(archive_doc))
        for src_path, arc_name in images_to_bundle:
            zf.write(src_path, arcname=arc_name)


def load_kdocz(path: Path, extract_to: Path | None = None) -> tuple[Document, Path]:
    """Open a `.kdocz` archive.

    `extract_to` controls where the bundled files are unpacked; pass a
    persistent directory (e.g. next to the .kdocz) if you want the unpacked
    images to survive across runs. The default is a fresh temp dir per call.

    Returns `(document, extract_dir)`. Figure paths in the returned document
    are absolute paths under `extract_dir`, so the LaTeX compiler will find
    every image without any further setup.
    """
    if extract_to is None:
        extract_to = Path(tempfile.mkdtemp(prefix="kdocz-"))
    extract_to = Path(extract_to)
    extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "r") as zf:
        # Read the manifest if present (currently we only validate the
        # schema_version, but this is also where we'll branch on future
        # format revisions).
        if MANIFEST_BASENAME in zf.namelist():
            manifest = json.loads(zf.read(MANIFEST_BASENAME))
            if manifest.get("schema_version", 0) > SCHEMA_VERSION:
                raise ValueError(
                    f"{path.name} was produced by a newer KherveTeX "
                    f"(schema {manifest['schema_version']} > {SCHEMA_VERSION}).")
        zf.extractall(extract_to)

    doc_json = (extract_to / DOC_BASENAME).read_text(encoding="utf-8")
    doc = from_json(doc_json)

    # Rewrite Figure paths so they point at the just-extracted files. Forward
    # slashes keep LaTeX happy on Windows; absolute paths sidestep CWD issues
    # when tectonic runs in its own build directory.
    for block in doc.children:
        if isinstance(block, Figure) and block.path:
            candidate = extract_to / block.path
            if candidate.exists():
                block.path = str(candidate.resolve()).replace("\\", "/")

    return doc, extract_to
