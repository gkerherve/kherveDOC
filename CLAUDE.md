# CLAUDE.md — working conventions for kherveDOC

Project: WYSIWYG editor that produces LaTeX and tracks changes in Git.
Stack: Python 3.12+, PySide6, tectonic (LaTeX engine), PyMuPDF, pygit2.
Remote: https://github.com/gkerherve/kherveDOC

## Branching: `dev` is the working branch

**All my work goes on `dev` in the main repo checkout.** I do not commit
to `main` directly. `main` is the stable mainline that lags behind `dev`
until the user explicitly asks for a merge.

**Never work in a git worktree (e.g. `.claude/worktrees/...`) or on a
throwaway branch like `claude/<name>`.** The user watches commits land
on `dev` in PyCharm's Git Log; commits made on worktree branches do not
show up there. If I find myself in a worktree or on a non-`dev` branch,
switch to the main repo path
(`C:\Users\gwilh\OneDrive - Imperial College London\Documents\MEGAsync\Programs\Python\kherveDOC`)
and `git checkout dev` before editing anything.

Workflow:
1. Confirm I am in the main repo (not a worktree) and on `dev`
   (`git rev-parse --abbrev-ref HEAD` → `dev`,
   `git rev-parse --show-toplevel` → the main repo path above). If not,
   `cd` to the main repo and `git checkout dev`.
2. If `dev` doesn't exist locally, create it from `main`:
   `git checkout -b dev origin/dev` (or branch from `origin/main` and
   push with `-u origin dev`).
3. Make the edits.
4. Run `py -m pytest tests/ -q` and verify all tests pass.
5. `git add` the specific files I changed (avoid bare `git add -A` —
   it has already once swept in `.idea/` IDE configs).
6. `git commit` with a HEREDOC-formatted message explaining the **why**,
   not the what — the diff already shows what changed.
7. `git push` — **never skip this step**. If the push fails (no network,
   auth), report it but do not retry destructively.

If the user explicitly asks for a merge into `main`, do it as a single
fast-forward or merge commit on `main`, push, then return to `dev`.

## Always commit and push after any change

After every code change, commit and push to `origin/dev` without being
asked. Never leave changes uncommitted at the end of a turn. This rule
holds even for small edits — README updates, comment fixes, one-line
bug fixes.

## Bump the version when behaviour changes

`khervedoc/__init__.py` defines `__version__` as `"<major>.<minor>"` only
(e.g. `"0.5"`). The window title renders it as

> `kherveDOC v<major>.<minor>.<commit_count>+<sha7> — <filename>`

The patch component is the total commit count and the `+<sha7>` build
tag are appended automatically from `pygit2` at startup — they update
every commit on their own. **Never put a third number in `__version__`.**

Bump the **minor** (`"0.5" → "0.6"`) when there is a meaningful
user-visible feature shift: new toolbar group, new model node type, new
menu, new tab, etc. Bump the **major** (`"0.x" → "1.0"`) only at the
user's explicit request. Routine bug fixes, refactors, and documentation
edits get no bump — the commit count moves on its own.

Bump `__version__` in the **same commit** as the change that justifies
it.

## Architectural invariants

- Comments only when the *why* is non-obvious; never narrate the *what*.
- The **document model** (`khervedoc/model.py`) is the single source of
  truth. The editor, serializer, importers and git layer all read/write
  through it. Never edit LaTeX strings directly outside `serializer.py`.
- Tests in `tests/` cover model + serializer + importer. Any change to
  those modules must come with matching tests in the **same commit**.
- Toolbar icons are drawn at runtime in `icons.py` with QPainter — do
  not ship PNG/SVG files.
- The light Fusion palette in `__main__.py` is intentional; do not
  remove it (the Windows dark theme made the icons invisible).
- Auto-commits from the app (`git_backend.py`) read the user's git
  identity from their git config so they look identical to CLI commits
  — do not regress that.
