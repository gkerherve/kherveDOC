"""kherveDOC — WYSIWYG LaTeX editor with Git history."""
from __future__ import annotations

from pathlib import Path

__version__ = "0.2.0"


def _git_build_info() -> tuple[int, str] | None:
    """Return (commit_count, short_sha) for the kherveDOC source repo, or
    None if we can't read it (not a git checkout, pygit2 missing, etc.)."""
    repo_root = Path(__file__).resolve().parent.parent
    try:
        import pygit2
        if not (repo_root / ".git").exists():
            return None
        repo = pygit2.Repository(str(repo_root))
        if repo.head_is_unborn:
            return None
        head_oid = repo.head.target
        count = sum(1 for _ in repo.walk(head_oid, pygit2.GIT_SORT_NONE))
        return count, str(head_oid)[:8]
    except Exception:
        return None


def version_string() -> str:
    """Human-readable version with commit count and short SHA when available."""
    info = _git_build_info()
    if info is None:
        return f"v{__version__}"
    count, sha = info
    return f"v{__version__} · {count} commits · {sha}"
