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

`khervedoc/__init__.py` defines `__version__` as `"<major>.<minor>"` only
(e.g. `"0.2"`). The window title renders it as

> `kherveDOC v<major>.<minor>.<commit_count>+<sha7> — <filename>`

The patch component is the total commit count and the `+<sha7>` build tag
are appended automatically from `pygit2` at startup — they update every
commit on their own. **Never put a third number in `__version__`.**

Bump the **minor** (`"0.2" → "0.3"`) when there is a meaningful
user-visible feature shift: new toolbar group, new model node type,
new menu, new tab, etc. Bump the **major** (`"0.x" → "1.0"`) only at
the user's explicit request. Routine bug fixes, refactors, and
documentation edits get no bump — the commit count moves on its own.

Bump `__version__` in the **same commit** as the change that justifies it.

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
