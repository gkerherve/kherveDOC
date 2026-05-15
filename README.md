# kherveDOC

A WYSIWYG document editor that produces beautiful PDFs via LaTeX, with Git-based version history.

This is the **MVP foundation** — a working skeleton you can extend.

## What works today

- Document model (typed Python dataclasses): Document, Section, Paragraph, Text + bold/italic marks, MathInline, MathBlock, RawLatex.
- JSON load/save of the model.
- LaTeX serializer (model -> `.tex`) with unit tests.
- `tectonic` subprocess wrapper to compile `.tex` -> `.pdf`.
- PySide6 GUI: editor pane (left) + live PDF preview pane (right), debounced recompile on edit.
- Toolbar: heading level, bold, italic, inline math, math block.
- Save/load `.kdoc.json`, export `.tex` and `.pdf`.
- Per-document Git repo with auto-commit on save (via `pygit2`).

## What is NOT yet implemented

- Tables, figures, lists, footnotes, citations, bibliography
- A visual math equation editor (you type LaTeX in a dialog)
- GitHub remote push UI, diff viewer, branch UI
- SyncTeX click-to-jump
- Packaging / installer
- Mapping LaTeX errors back to editor positions

## Setup

1. **Install Python deps:**
   ```
   pip install -r requirements.txt
   ```

2. **Install tectonic** (the LaTeX engine):
   - Windows: `winget install TectonicTypesetting.Tectonic` or download from https://tectonic-typesetting.github.io/
   - The first compile will download required TeX packages automatically.

3. **Run:**
   ```
   python -m khervedoc
   ```

4. **Run tests:**
   ```
   python -m pytest tests/
   ```

## Project layout

```
khervedoc/
  model.py        # typed document tree (dataclasses)
  serializer.py   # model -> LaTeX string
  compiler.py     # tectonic subprocess + PDF page rendering via PyMuPDF
  git_backend.py  # pygit2 auto-commit
  editor.py       # PySide6 editor widget (QTextEdit + toolbar)
  preview.py      # PySide6 PDF preview widget
  mainwindow.py   # the app shell
  __main__.py     # entry point
tests/
  test_model.py
  test_serializer.py
examples/
  demo.kdoc.json
```

## Architecture in one paragraph

The **document model** is the single source of truth. The **editor** (QTextEdit + custom char formats) reads and writes the model. On every edit, the model is re-serialized to `.tex` and `tectonic` compiles it to PDF; **PyMuPDF** renders pages into the preview pane. **pygit2** auto-commits the `.tex` (the human-readable artifact) on save. No component edits LaTeX strings directly — they all go through the model.
