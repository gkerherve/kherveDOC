"""LaTeX/Typst compilation and PDF page rendering.

`compile_tex` shells out to `tectonic`, `compile_typst` shells out to `typst`.
`render_pdf_pages` uses PyMuPDF to rasterize the resulting PDF into
QImage-ready pixel buffers.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# \includegraphics[opts]{path} — capture the opts (optional, balanced
# brackets at depth 1) and the path (no nested braces). Tectonic resolves
# the path relative to the .tex file's directory, not via TEXINPUTS or
# cwd, so we rewrite relative paths to absolute against source_dir before
# writing the .tex into the temp build dir.
_INCLUDEGRAPHICS_RE = re.compile(
    r"\\includegraphics(\*?)(\[[^\]]*\])?\{([^}]+)\}")


def _rewrite_includegraphics(tex_source: str, source_dir: Path | None) -> str:
    r"""Resolve every `\includegraphics{path}` so the .tex compiles from a
    temp build dir. Three cases:

    - absolute existing path:   left untouched (works as-is)
    - relative path that exists under `source_dir`: rewritten to the
      absolute resolved path (forward slashes for LaTeX)
    - path that doesn't exist:  replaced with a framed placeholder
      box so the compile keeps going and the PDF shows the user where
      the missing image WOULD have been. Without this, tectonic's
      xdvipdfmx stage halts with "Image inclusion failed" — `-Z
      continue-on-errors` only catches TeX-level errors.
    """
    def _placeholder(path: str) -> str:
        # \fbox of a small note. Wrap in \texttt so it's clearly a
        # diagnostic message rather than typeset content.
        # Escape LaTeX special chars in the path so it renders.
        safe = (path.replace("\\", "/")
                    .replace("_", r"\_")
                    .replace("#", r"\#")
                    .replace("%", r"\%")
                    .replace("&", r"\&"))
        return (r"\fbox{\texttt{\small [missing image: " + safe + r"]}}")

    def _sub(m: re.Match) -> str:
        star, opts, path = m.group(1), m.group(2) or "", m.group(3)
        p = Path(path)
        if p.is_absolute():
            if p.exists():
                return m.group(0)
            return _placeholder(path)
        if source_dir is None:
            return _placeholder(path)
        resolved = (source_dir / path).resolve()
        if not resolved.exists():
            return _placeholder(path)
        abs_path = str(resolved).replace("\\", "/")
        return f"\\includegraphics{star}{opts}{{{abs_path}}}"

    return _INCLUDEGRAPHICS_RE.sub(_sub, tex_source)


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


def _strip_images(tex_source: str) -> str:
    r"""Replace every \includegraphics with a lightweight placeholder box
    so tectonic skips image embedding entirely — much faster for drafts."""
    def _sub(m: re.Match) -> str:
        path = m.group(3).replace("\\", "/").replace("_", r"\_")
        return r"\fbox{\texttt{\footnotesize " + path + r"}}"
    return _INCLUDEGRAPHICS_RE.sub(_sub, tex_source)


_COMPILE_START     = "% ===== KHERVETEX COMPILE START ====="
_COMPILE_END       = "% ===== KHERVETEX COMPILE END ====="
_NOT_COMPILE_START = "% ===== KHERVETEX NOT COMPILE START ====="
_NOT_COMPILE_END   = "% ===== KHERVETEX NOT COMPILE END ====="


def _apply_compile_range(tex_source: str) -> str:
    r"""Keep only the body between compile-range markers.

    Everything in the preamble and \begin/\end{document} is preserved.
    Body lines outside the marked range are wrapped in \iffalse...\fi
    so LaTeX skips them entirely.  If no markers are found the source
    is returned unchanged.
    """
    lines = tex_source.split("\n")
    begin_doc = end_doc = -1
    start_marker = end_marker = -1
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.startswith(r"\begin{document}"):
            begin_doc = i
        elif stripped.startswith(r"\end{document}"):
            end_doc = i
        elif stripped == _COMPILE_START:
            start_marker = i
        elif stripped == _COMPILE_END:
            end_marker = i

    if start_marker == -1 and end_marker == -1:
        return tex_source
    if begin_doc == -1 or end_doc == -1:
        return tex_source

    body_start = begin_doc + 1
    body_end = end_doc  # exclusive

    # Determine the kept range within the body
    keep_from = start_marker + 1 if start_marker >= body_start else body_start
    keep_to = end_marker if end_marker > body_start else body_end

    result: list[str] = []
    # Preamble + \begin{document}
    result.extend(lines[:body_start])
    # Before the kept range → hide
    before = lines[body_start:keep_from]
    if any(ln.strip() for ln in before):
        result.append(r"\iffalse")
        result.extend(before)
        result.append(r"\fi")
    # Kept range
    result.extend(lines[keep_from:keep_to])
    # After the kept range → hide
    after = lines[keep_to:body_end]
    if any(ln.strip() for ln in after):
        result.append(r"\iffalse")
        result.extend(after)
        result.append(r"\fi")
    # \end{document} and anything after
    result.extend(lines[end_doc:])
    return "\n".join(result)


def _apply_not_compile_ranges(tex_source: str) -> str:
    r"""Hide content between each NOT COMPILE START/END marker pair.

    Multiple pairs are supported. Content between each pair is wrapped
    in \iffalse...\fi. Unpaired markers are ignored.
    """
    lines = tex_source.split("\n")
    # Collect all paired ranges
    starts: list[int] = []
    ends: list[int] = []
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped == _NOT_COMPILE_START:
            starts.append(i)
        elif stripped == _NOT_COMPILE_END:
            ends.append(i)
    if not starts or not ends:
        return tex_source
    # Match each start with the nearest following end
    pairs: list[tuple[int, int]] = []
    used_ends: set[int] = set()
    for s in starts:
        for e in ends:
            if e > s and e not in used_ends:
                pairs.append((s, e))
                used_ends.add(e)
                break
    if not pairs:
        return tex_source
    # Build result, wrapping each pair in \iffalse..\fi
    result: list[str] = []
    prev = 0
    for s, e in sorted(pairs):
        result.extend(lines[prev:s])
        result.append(r"\iffalse")
        result.extend(lines[s:e + 1])
        result.append(r"\fi")
        prev = e + 1
    result.extend(lines[prev:])
    return "\n".join(result)


def compile_tex(
    tex_source: str,
    workdir: Path,
    basename: str = "document",
    source_dir: Path | None = None,
    skip_images: bool = False,
    use_compile_range: bool = False,
) -> CompileResult:
    """Write `tex_source` to `workdir/basename.tex` and compile with tectonic.

    `workdir` is created if missing. Returns a CompileResult; on failure the
    `log` field contains tectonic's full output for diagnosis.

    `source_dir`, when supplied, is the directory of the user's original
    document. It's added to TEXINPUTS so relative \\includegraphics paths
    (e.g. `Images/foo.png` next to the .tex) resolve even though we
    compile in a temp `workdir`. We also pass `-Z continue-on-errors`
    so a single missing image doesn't halt the whole preview — tectonic
    still emits the PDF with a "?" placeholder where the image would go.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    # Copy auxiliary TeX files (.cls, .sty, .bst, .bib) from source_dir
    # into workdir so tectonic can find them — tectonic's bundle system
    # doesn't always honour TEXINPUTS for custom class files.
    if source_dir is not None and Path(source_dir).is_dir():
        for ext in ("*.cls", "*.sty", "*.bst", "*.bib"):
            for f in Path(source_dir).glob(ext):
                dest = workdir / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)
        # Copy subdirectories (Fonts/, Images/, etc.) so relative paths
        # inside .cls files (e.g. ./Fonts/Lato/Lato-Regular) resolve.
        for child in Path(source_dir).iterdir():
            if child.is_dir() and not child.name.startswith("."):
                dest = workdir / child.name
                if not dest.exists():
                    shutil.copytree(child, dest)
    if skip_images:
        tex_source = _strip_images(tex_source)
    else:
        tex_source = _rewrite_includegraphics(tex_source, source_dir)
    if use_compile_range:
        tex_source = _apply_compile_range(tex_source)
        tex_source = _apply_not_compile_ranges(tex_source)
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

    env = os.environ.copy()
    # Build TEXINPUTS: source_dir (document's folder), then user styles,
    # then bundled styles, then tectonic's defaults.
    sep = ";" if os.name == "nt" else ":"
    texinputs_parts: list[str] = []
    if source_dir is not None and Path(source_dir).is_dir():
        texinputs_parts.append(str(Path(source_dir)))
    from . import style_manager
    for sd in style_manager.all_style_dirs():
        texinputs_parts.append(str(sd))
    if texinputs_parts:
        existing = env.get("TEXINPUTS", "")
        env["TEXINPUTS"] = sep.join(texinputs_parts) + sep + existing

    try:
        kw: dict = dict(capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=120, env=env)
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(
            [
                tectonic_path,
                "-Z", "continue-on-errors",
                "--keep-logs",
                "--synctex",
                "--outdir", str(workdir),
                str(tex_path),
            ],
            **kw,
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


# ======================= Typst compiler =======================

_TYPST_IMAGE_RE = re.compile(r'image\("([^"]+)"')


def _find_typst() -> str | None:
    """Locate the typst binary, falling back to common install locations
    that may not be on PATH yet (winget, cargo, scoop)."""
    found = shutil.which("typst")
    if found:
        return found
    candidates = [
        Path.home() / "bin" / "typst.exe",
        Path.home() / "bin" / "typst",
        Path.home() / ".cargo" / "bin" / "typst.exe",
        Path.home() / ".cargo" / "bin" / "typst",
        Path.home() / "scoop" / "shims" / "typst.exe",
    ]
    # winget installs into a versioned package dir
    winget_base = (Path.home() / "AppData" / "Local" / "Microsoft"
                   / "WinGet" / "Packages")
    if winget_base.is_dir():
        for pkg_dir in winget_base.glob("Typst.Typst_*"):
            for exe in pkg_dir.rglob("typst.exe"):
                candidates.append(exe)
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def typst_available() -> bool:
    return _find_typst() is not None


def _rewrite_typst_images(typ_source: str, source_dir: Path | None) -> str:
    """Resolve relative image paths in Typst source to absolute."""
    def _sub(m: re.Match) -> str:
        path = m.group(1)
        p = Path(path)
        if p.is_absolute():
            if p.exists():
                return m.group(0)
            return f'rect(width: 100%, height: 2cm, stroke: 1pt, inset: 4pt)[missing: {path}]'
        if source_dir is None:
            return f'rect(width: 100%, height: 2cm, stroke: 1pt, inset: 4pt)[missing: {path}]'
        resolved = (source_dir / path).resolve()
        if not resolved.exists():
            return f'rect(width: 100%, height: 2cm, stroke: 1pt, inset: 4pt)[missing: {path}]'
        abs_path = str(resolved).replace("\\", "/")
        return f'image("{abs_path}"'
    return _TYPST_IMAGE_RE.sub(_sub, typ_source)


def _strip_typst_images(typ_source: str) -> str:
    """Replace image() calls with placeholder rects for fast drafts."""
    def _sub(m: re.Match) -> str:
        path = m.group(1).replace("\\", "/")
        return f'rect(width: 100%, height: 2cm, stroke: 0.5pt, inset: 4pt)[{path}]'
    return _TYPST_IMAGE_RE.sub(_sub, typ_source)


_TYPST_COMPILE_START     = "// ===== KHERVETEX COMPILE START ====="
_TYPST_COMPILE_END       = "// ===== KHERVETEX COMPILE END ====="
_TYPST_NOT_COMPILE_START = "// ===== KHERVETEX NOT COMPILE START ====="
_TYPST_NOT_COMPILE_END   = "// ===== KHERVETEX NOT COMPILE END ====="


def _apply_typst_compile_range(typ_source: str) -> str:
    """Keep only content between compile-range markers in Typst source.

    Uses /* ... */ block comments to hide excluded content.
    Typst has no preamble/document boundary like LaTeX, so markers
    apply to the whole file — #set rules before the first marker are
    always kept.
    """
    lines = typ_source.split("\n")
    start_marker = end_marker = -1
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped == _TYPST_COMPILE_START:
            start_marker = i
        elif stripped == _TYPST_COMPILE_END:
            end_marker = i
    if start_marker == -1 and end_marker == -1:
        return typ_source

    # Find where #set rules end (preamble-equivalent)
    preamble_end = 0
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.startswith("#set ") or stripped.startswith("#show ") or stripped == "":
            preamble_end = i + 1
        else:
            break

    keep_from = start_marker + 1 if start_marker >= preamble_end else preamble_end
    keep_to = end_marker if end_marker > preamble_end else len(lines)

    result: list[str] = []
    result.extend(lines[:preamble_end])
    before = lines[preamble_end:keep_from]
    if any(ln.strip() for ln in before):
        result.append("/*")
        result.extend(before)
        result.append("*/")
    result.extend(lines[keep_from:keep_to])
    after = lines[keep_to:]
    if any(ln.strip() for ln in after):
        result.append("/*")
        result.extend(after)
        result.append("*/")
    return "\n".join(result)


def _apply_typst_not_compile_ranges(typ_source: str) -> str:
    """Hide content between NOT COMPILE marker pairs using /* ... */."""
    lines = typ_source.split("\n")
    starts: list[int] = []
    ends: list[int] = []
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped == _TYPST_NOT_COMPILE_START:
            starts.append(i)
        elif stripped == _TYPST_NOT_COMPILE_END:
            ends.append(i)
    if not starts or not ends:
        return typ_source
    pairs: list[tuple[int, int]] = []
    used_ends: set[int] = set()
    for s in starts:
        for e in ends:
            if e > s and e not in used_ends:
                pairs.append((s, e))
                used_ends.add(e)
                break
    if not pairs:
        return typ_source
    result: list[str] = []
    prev = 0
    for s, e in sorted(pairs):
        result.extend(lines[prev:s])
        result.append("/*")
        result.extend(lines[s:e + 1])
        result.append("*/")
        prev = e + 1
    result.extend(lines[prev:])
    return "\n".join(result)


def compile_typst(
    typ_source: str,
    workdir: Path,
    basename: str = "document",
    source_dir: Path | None = None,
    skip_images: bool = False,
    use_compile_range: bool = False,
) -> CompileResult:
    """Write Typst source to workdir and compile with typst CLI."""
    workdir.mkdir(parents=True, exist_ok=True)
    if skip_images:
        typ_source = _strip_typst_images(typ_source)
    else:
        typ_source = _rewrite_typst_images(typ_source, source_dir)
    if use_compile_range:
        typ_source = _apply_typst_compile_range(typ_source)
        typ_source = _apply_typst_not_compile_ranges(typ_source)
    typ_path = workdir / f"{basename}.typ"
    typ_path.write_text(typ_source, encoding="utf-8")

    typst_path = _find_typst()
    if typst_path is None:
        return CompileResult(
            ok=False,
            pdf_path=None,
            log="",
            error="typst is not installed or not on PATH. "
                  "Install it from https://typst.app/",
        )

    pdf_path = workdir / f"{basename}.pdf"
    try:
        cmd = [typst_path, "compile", str(typ_path), str(pdf_path)]
        kw: dict = dict(capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=120)
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(cmd, **kw)
    except subprocess.TimeoutExpired:
        return CompileResult(False, None, "", "typst timed out after 120s")

    log = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0 and pdf_path.exists():
        return CompileResult(True, pdf_path, log, None)

    return CompileResult(
        ok=False,
        pdf_path=pdf_path if pdf_path.exists() else None,
        log=log,
        error=f"typst exited with code {proc.returncode}",
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
