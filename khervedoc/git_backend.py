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


def init_repo(repo_dir: Path) -> bool:
    """Initialise a git repo in `repo_dir` if one doesn't already exist."""
    if not _PYGIT2_OK:
        return False
    repo_dir.mkdir(parents=True, exist_ok=True)
    if (repo_dir / ".git").exists():
        return True
    pygit2.init_repository(str(repo_dir), bare=False)
    return True


def _signature() -> "pygit2.Signature":
    return pygit2.Signature("kherveDOC", "khervedoc@local", int(datetime.now().timestamp()), 0)


def commit_all(repo_dir: Path, message: str | None = None) -> str | None:
    """Stage every tracked + new file in `repo_dir` and create a commit.

    Returns the new commit's hex OID, or None if nothing changed / git unavailable.
    """
    if not _PYGIT2_OK:
        return None
    if not (repo_dir / ".git").exists():
        init_repo(repo_dir)

    repo = pygit2.Repository(str(repo_dir))
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

    sig = _signature()
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
    repo = pygit2.Repository(str(repo_dir))
    if repo.head_is_unborn:
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
