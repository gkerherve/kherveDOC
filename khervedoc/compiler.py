"""LaTeX compilation and PDF page rendering.

`compile_tex` shells out to `tectonic`. `render_pdf_pages` uses PyMuPDF to
rasterize the resulting PDF into QImage-ready pixel buffers.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _find_tectonic() -> str | None:
    """Locate the tectonic binary, falling back to common install locations
    that may not be on PATH yet (e.g. ~/bin on Windows after a fresh PATH
    update that hasn't propagated to the current process)."""
    found = shutil.which("tectonic")
    if found:
        return found
    candidates = [
        Path.home() / "bin" / "tectonic.exe",
        Path.home() / "bin" / "tectonic",
        Path.home() / ".cargo" / "bin" / "tectonic.exe",
        Path.home() / "scoop" / "shims" / "tectonic.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


@dataclass
class CompileResult:
    ok: bool
    pdf_path: Path | None
    log: str           # stdout + stderr combined
    error: str | None  # short human-readable error, or None on success


def tectonic_available() -> bool:
    return _find_tectonic() is not None


def compile_tex(tex_source: str, workdir: Path, basename: str = "document") -> CompileResult:
    """Write `tex_source` to `workdir/basename.tex` and compile with tectonic.

    `workdir` is created if missing. Returns a CompileResult; on failure the
    `log` field contains tectonic's full output for diagnosis.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    tex_path = workdir / f"{basename}.tex"
    tex_path.write_text(tex_source, encoding="utf-8")

    tectonic_path = _find_tectonic()
    if tectonic_path is None:
        return CompileResult(
            ok=False,
            pdf_path=None,
            log="",
            error="tectonic is not installed or not on PATH. "
                  "Install it from https://tectonic-typesetting.github.io/",
        )

    try:
        proc = subprocess.run(
            [
                tectonic_path,
                "--keep-logs",
                "--synctex",
                "--outdir", str(workdir),
                str(tex_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, "", "tectonic timed out after 120s")

    log = (proc.stdout or "") + (proc.stderr or "")
    pdf_path = workdir / f"{basename}.pdf"
    if proc.returncode == 0 and pdf_path.exists():
        return CompileResult(True, pdf_path, log, None)

    return CompileResult(
        ok=False,
        pdf_path=pdf_path if pdf_path.exists() else None,
        log=log,
        error=f"tectonic exited with code {proc.returncode}",
    )


@dataclass
class RenderedPage:
    width: int
    height: int
    stride: int      # bytes per row
    rgb: bytes       # raw RGB888 samples


def render_pdf_pages(pdf_path: Path, dpi: int = 144) -> list[RenderedPage]:
    """Rasterize a PDF into RGB pixel buffers (one per page).

    Uses PyMuPDF (`pymupdf`). Caller wraps each buffer with QImage using
    Format_RGB888 and the supplied stride.
    """
    import pymupdf  # lazy import — non-GUI code paths skip the dependency

    pages: list[RenderedPage] = []
    with pymupdf.open(pdf_path) as pdf:
        zoom = dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)
        for page in pdf:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pages.append(RenderedPage(
                width=pix.width,
                height=pix.height,
                stride=pix.stride,
                rgb=bytes(pix.samples),
            ))
    return pages
