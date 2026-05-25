# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for KherveTeX.

Builds a one-folder distribution (--onedir) so the .exe launches
instantly without extracting to a temp directory.  The layout is:

    KherveTeX/
        KherveTeX.exe          <- launcher (small, fast)
        _internal/             <- Python runtime, DLLs, packages
            khervedoc/
                styles/        <- bundled .cls/.sty/.bst files
            PySide6/
            ...

Build command:
    pyinstaller KherveTeX.spec --noconfirm

Prerequisites:
    pip install pyinstaller
    pip install -r requirements.txt
"""

import os
import sys
import sysconfig
from pathlib import Path

block_cipher = None

# Project root is the directory containing this spec file.
ROOT = Path(SPECPATH)

# ---- Analysis: discover all imports ------------------------------------

a = Analysis(
    [str(ROOT / "kherveDOC.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Bundled LaTeX style files — available to the compiler via TEXINPUTS.
        (str(ROOT / "khervedoc" / "styles"), "khervedoc/styles"),
        # pyspellchecker dictionary files (en.json.gz etc.) — not collected automatically.
        (os.path.join(sysconfig.get_path("purelib"), "spellchecker", "resources"),
         "spellchecker/resources"),
    ],
    hiddenimports=[
        # Lazy imports that Analysis can't see statically.
        "pygit2",
        "pymupdf",
        "docx",
        "spellchecker",
        "matplotlib",
        "matplotlib.figure",
        "matplotlib.backends.backend_agg",
        "matplotlib.mathtext",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Conflicting Qt bindings — we use PySide6, not PyQt5/PyQt6.
        "PyQt5",
        "PyQt6",
        # Large packages we don't use — shaves ~100 MB off the bundle.
        "tkinter",
        "unittest",
        "test",
        "pip",
        "setuptools",
        "numpy.testing",
        # Heavy transitive dependencies pulled in by the global env.
        "scipy",
        "pandas",
        "IPython",
        "jedi",
        "parso",
        "pyarrow",
        "zmq",
        "tornado",
        "notebook",
        "jupyter",
        "docutils",
        "babel",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ---- PYZ: compressed Python bytecode archive ---------------------------

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---- EXE: the launcher stub -------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    [],                 # empty = --onedir (not --onefile)
    exclude_binaries=True,
    name="KherveTeX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,      # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "khervedoc" / "icon.ico"),
)

# ---- COLLECT: gather everything into the output folder -----------------

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KherveTeX",
)
