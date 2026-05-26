"""KherveTeX — WYSIWYG LaTeX editor with Git history."""
from __future__ import annotations

from pathlib import Path

# Bumped by hand only for meaningful feature/behaviour shifts. The patch
# component is the total commit count and is appended automatically.
__version__ = "0.147"


def _git_build_info() -> tuple[int, str] | None:
    """Return (commit_count, short_sha) for the KherveTeX source repo, or
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
        return count, str(head_oid)[:7]
    except Exception:
        return None


def version_string() -> str:
    """Format: "v<major>.<minor>.<commit_count>+<sha7>".

    Falls back to "v<major>.<minor>" if git info isn't available.
    """
    info = _git_build_info()
    if info is None:
        return f"v{__version__}"
    count, sha = info
    return f"v{__version__}.{count}+{sha}"
