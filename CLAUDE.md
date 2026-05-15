# CLAUDE.md — working conventions for kherveDOC

Project: WYSIWYG editor that produces LaTeX and tracks changes in Git.
Stack: Python 3.12+, PySide6, tectonic (LaTeX engine), PyMuPDF, pygit2.
Remote: https://github.com/gkerherve/kherveDOC

## Always commit and push after any change

After every code change, **commit and push to `origin/main`** without being
asked. Never leave changes uncommitted at the end of a turn.

Workflow each turn:
1. Make the edits.
2. Run `py -m pytest tests/ -q` and verify all tests pass.
3. `git add -A` (the `.gitignore` excludes build artefacts, so this is safe).
4. `git commit` with a HEREDOC-formatted message that explains the **why**,
   not the what — the diff already shows what changed.
5. `git push` — do not skip this step.

If a push fails (no network, auth), report it but do not retry destructively.

## Bump the version when behaviour changes

`khervedoc/__init__.py` defines `__version__`. The window title displays it as

> `kherveDOC v<X.Y.Z> · <N> commits · <sha8> — <filename>`

The commit count and short SHA are read from the repo at startup — they
update on their own. The `__version__` itself must be updated **by hand**:

- **Patch bump** (e.g. `0.2.0 → 0.2.1`): bug fixes only, no new features.
- **Minor bump** (e.g. `0.2.1 → 0.3.0`): new user-visible features, new
  toolbar buttons, new model node types, new menus.
- **Major bump** (e.g. `0.x.y → 1.0.0`): only at user's explicit request.

Bump `__version__` in the **same commit** as the change that justifies it.
Do not batch version bumps separately.

## House style for this project

- Comments only when the *why* is non-obvious; never narrate the *what*.
- Tests live in `tests/`; serializer and model changes must come with
  matching tests in the same commit.
- Document model is the single source of truth — the editor, serializer
  and Git layer all read/write through it. Never edit LaTeX strings
  directly outside `serializer.py`.
- Icons are drawn at runtime in `icons.py` with QPainter — do not ship
  PNG/SVG files.
- The light Fusion palette in `__main__.py` is intentional; do not
  remove it (the Windows dark theme made the toolbar icons invisible).
