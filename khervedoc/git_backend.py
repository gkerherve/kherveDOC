"""Per-document Git repo with auto-commit on save.

Each document lives in a directory that is also its own git repo. The committed
artifacts are the human-readable files (`document.tex`, `document.kdoc.json`),
not the internal Python model — so `git diff` is meaningful.

Falls back gracefully if pygit2 is unavailable: every function becomes a no-op
and returns False, so the editor still works.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

try:
    import pygit2
    _PYGIT2_OK = True
except Exception:  # pragma: no cover — environment without pygit2
    pygit2 = None  # type: ignore
    _PYGIT2_OK = False


def is_available() -> bool:
    return _PYGIT2_OK


def _find_enclosing_repo(repo_dir: Path) -> Path | None:
    """Walk up the directory tree; if any ancestor has a .git, return that
    ancestor. Used to detect when a save would create a nested repo inside
    an existing one (which was the source of the rogue "master"-branch
    auto-commit history)."""
    cur = repo_dir.resolve()
    while cur != cur.parent:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    return None


def init_repo(repo_dir: Path) -> bool:
    """Initialise a git repo in `repo_dir` if one doesn't already exist.

    - If `repo_dir` is already a repo, return True (no-op).
    - If `repo_dir` is INSIDE another git repo, use that parent repo
      instead of nesting — saves there should commit to the enclosing
      repo's current branch, not a new "master" branch under a hidden
      `.git` directory.
    - Otherwise initialise a fresh repo with HEAD pointing to
      `refs/heads/dev`, matching the project's branching convention.
    """
    if not _PYGIT2_OK:
        return False
    repo_dir.mkdir(parents=True, exist_ok=True)
    if (repo_dir / ".git").exists():
        return True
    if _find_enclosing_repo(repo_dir) is not None:
        # Don't create a nested repo. Caller's commit_all will still work
        # because it walks up from repo_dir to find the enclosing .git.
        return True
    pygit2.init_repository(str(repo_dir), bare=False)
    # libgit2 defaults the unborn HEAD to refs/heads/master; rewrite it
    # so the very first commit lands on `dev` instead.
    head_file = repo_dir / ".git" / "HEAD"
    head_file.write_text("ref: refs/heads/dev\n", encoding="utf-8")
    return True


def _repo_for(repo_dir: Path) -> "pygit2.Repository | None":
    """Return the pygit2.Repository governing `repo_dir`, walking up to
    find an enclosing one if `repo_dir` itself isn't a repo root."""
    if (repo_dir / ".git").exists():
        return pygit2.Repository(str(repo_dir))
    enclosing = _find_enclosing_repo(repo_dir)
    return pygit2.Repository(str(enclosing)) if enclosing else None


def _signature(repo: "pygit2.Repository | None" = None) -> "pygit2.Signature":
    """Build a commit signature, preferring the user's real git identity.

    Order:
      1. repo.default_signature — reads user.name/user.email from .git/config,
         the user's global config, or the system config (the same chain plain
         `git commit` uses, so auto-commits look identical to CLI commits).
      2. Hard-coded fallback only if no git identity is configured anywhere.
    """
    if repo is not None:
        try:
            return repo.default_signature
        except (KeyError, pygit2.GitError):
            pass
    return pygit2.Signature(
        "kherveDOC", "khervedoc@local", int(datetime.now().timestamp()), 0)


def commit_all(repo_dir: Path, message: str | None = None) -> str | None:
    """Stage every tracked + new file in `repo_dir` and create a commit.

    Returns the new commit's hex OID, or None if nothing changed / git unavailable.
    """
    if not _PYGIT2_OK:
        return None
    init_repo(repo_dir)

    repo = _repo_for(repo_dir)
    if repo is None:
        return None
    index = repo.index
    index.add_all()
    index.write()

    # Detect "no changes" by comparing the new tree against HEAD's tree.
    new_tree_oid = index.write_tree()
    parents: list[str] = []
    if not repo.head_is_unborn:
        head_commit = repo.head.peel(pygit2.Commit)
        if head_commit.tree_id == new_tree_oid:
            return None
        parents = [head_commit.id]

    sig = _signature(repo)
    msg = message or f"Edit at {datetime.now().isoformat(timespec='seconds')}"
    commit_oid = repo.create_commit(
        "HEAD" if repo.head_is_unborn else repo.head.name,
        sig, sig, msg, new_tree_oid, parents,
    )
    return str(commit_oid)


def push(repo_dir: Path, remote_name: str = "origin", branch: str = "main") -> bool:
    """Push the current branch to the given remote. Returns True on success.

    Uses libgit2 credentials helpers when available (SSH agent, Windows
    credential manager). If no remote is configured or the push fails (auth,
    network, etc.) returns False — the caller continues without raising.
    """
    if not _PYGIT2_OK:
        return False
    if not (repo_dir / ".git").exists():
        return False
    try:
        repo = pygit2.Repository(str(repo_dir))
        if remote_name not in [r.name for r in repo.remotes]:
            return False
        remote = repo.remotes[remote_name]
        # Pick a refspec that pushes the current branch.
        if repo.head_is_unborn:
            return False
        head_ref = repo.head.name  # e.g. "refs/heads/main"
        refspec = f"{head_ref}:{head_ref}"
        callbacks = pygit2.RemoteCallbacks(credentials=pygit2.KeypairFromAgent("git"))
        try:
            remote.push([refspec], callbacks=callbacks)
            return True
        except Exception:
            # Retry without explicit credentials — libgit2 may resolve via
            # the system's git credential helper on Windows.
            try:
                remote.push([refspec])
                return True
            except Exception:
                return False
    except Exception:
        return False


def history(repo_dir: Path, limit: int = 50) -> list[tuple[str, str, str]]:
    """Return [(short_oid, iso_time, message_first_line), ...] newest first."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return []
    repo = _repo_for(repo_dir)
    if repo is None or repo.head_is_unborn:
        return []
    out: list[tuple[str, str, str]] = []
    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TIME):
        out.append((
            str(commit.id)[:8],
            datetime.fromtimestamp(commit.commit_time).isoformat(timespec="seconds"),
            commit.message.splitlines()[0] if commit.message else "",
        ))
        if len(out) >= limit:
            break
    return out


def history_detailed(repo_dir: Path,
                     limit: int = 200) -> list[dict]:
    """Richer version of `history` for the GUI commit-browser.

    Each entry is a dict with the keys the history dialog needs:
      - oid:        full hex OID (str)
      - short_oid:  first 8 chars
      - timestamp:  ISO-8601 local time (str)
      - epoch:      Unix epoch (int) — for sorting if a caller needs it
      - author:     "Name <email>"
      - subject:    first line of the commit message
      - body:       lines 2+ of the commit message (may be empty)

    Empty list if pygit2 is missing or the repo has no commits."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return []
    repo = _repo_for(repo_dir)
    if repo is None or repo.head_is_unborn:
        return []
    out: list[dict] = []
    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TIME):
        msg = (commit.message or "").rstrip()
        lines = msg.splitlines()
        subject = lines[0] if lines else ""
        body = "\n".join(lines[1:]).strip("\n") if len(lines) > 1 else ""
        author = commit.author
        out.append({
            "oid": str(commit.id),
            "short_oid": str(commit.id)[:8],
            "timestamp": datetime.fromtimestamp(commit.commit_time).isoformat(
                timespec="seconds"),
            "epoch": int(commit.commit_time),
            "author": f"{author.name} <{author.email}>",
            "subject": subject,
            "body": body,
        })
        if len(out) >= limit:
            break
    return out


def diff_for_commit(repo_dir: Path, oid: str) -> str:
    """Return the unified diff produced by the given commit, as a single
    str. For a root commit (no parents) the diff is against an empty
    tree, so the whole initial state shows up as additions. Empty
    string if pygit2 is missing or the oid can't be resolved."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return ""
    repo = _repo_for(repo_dir)
    if repo is None:
        return ""
    try:
        commit = repo.get(oid)
        if commit is None:
            return ""
        # Resolve through tags / annotated tags etc. to the actual commit.
        commit = commit.peel(pygit2.Commit)
    except Exception:
        return ""
    parents = list(commit.parents)
    try:
        if parents:
            # Compare against the first parent — same as `git show` does
            # for non-merge commits. Merges show diff vs first parent
            # which is the conventional "what landed" view.
            diff = repo.diff(parents[0], commit, context_lines=3)
        else:
            # Root commit: diff against an empty tree so the initial
            # file contents appear as additions instead of an empty diff.
            diff = commit.tree.diff_to_tree(swap=True, context_lines=3)
    except Exception:
        return ""
    return diff.patch or ""
