"""Tests for the git_backend helpers behind the HistoryDialog.

Builds a throwaway git repo in tmp_path, makes a couple of commits,
and asserts that history_detailed + diff_for_commit produce what the
GUI expects. Skipped if pygit2 isn't installed so a stripped-down
checkout still passes CI."""

from pathlib import Path

import pytest

from khervedoc import git_backend


pytestmark = pytest.mark.skipif(
    not git_backend.is_available(),
    reason="pygit2 not installed — skipping git_backend tests",
)


def _make_repo_with_two_commits(tmp_path: Path) -> Path:
    """Return a repo dir with two commits: first creates hello.txt
    with one line, second appends a second line."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "hello.txt").write_text("hello world\n", encoding="utf-8")
    git_backend.commit_all(repo_dir, message="initial commit")
    (repo_dir / "hello.txt").write_text(
        "hello world\nsecond line\n", encoding="utf-8")
    git_backend.commit_all(repo_dir, message="add a second line\n\nbody text")
    return repo_dir


def test_history_detailed_returns_newest_first(tmp_path: Path):
    repo = _make_repo_with_two_commits(tmp_path)
    commits = git_backend.history_detailed(repo)
    assert len(commits) == 2
    # Newest is "add a second line"; initial is older.
    assert commits[0]["subject"] == "add a second line"
    assert commits[0]["body"] == "body text"
    assert commits[1]["subject"] == "initial commit"
    # Required keys for the dialog:
    for c in commits:
        for key in ("oid", "short_oid", "timestamp", "author",
                    "subject", "body", "epoch"):
            assert key in c, f"missing {key!r} in {c!r}"
        assert len(c["short_oid"]) == 8


def test_diff_for_commit_shows_addition_for_second_commit(tmp_path: Path):
    repo = _make_repo_with_two_commits(tmp_path)
    second = git_backend.history_detailed(repo)[0]
    diff = git_backend.diff_for_commit(repo, second["oid"])
    # The added line shows up as a `+` line in the unified diff.
    assert "+second line" in diff
    # The previous line was context, so it appears with a leading space.
    assert " hello world" in diff


def test_diff_for_root_commit_shows_initial_content(tmp_path: Path):
    """The first commit has no parent — we still want a meaningful
    diff that shows the initial file contents as additions, otherwise
    the history dialog would show an empty pane for the root commit."""
    repo = _make_repo_with_two_commits(tmp_path)
    root = git_backend.history_detailed(repo)[-1]
    diff = git_backend.diff_for_commit(repo, root["oid"])
    assert "+hello world" in diff
    # New file marker should be present.
    assert "new file" in diff or "+++ b/hello.txt" in diff


def test_diff_for_unknown_oid_returns_empty_string(tmp_path: Path):
    repo = _make_repo_with_two_commits(tmp_path)
    assert git_backend.diff_for_commit(repo, "0" * 40) == ""


def test_history_detailed_on_empty_repo_returns_empty_list(tmp_path: Path):
    empty = tmp_path / "empty_repo"
    empty.mkdir()
    git_backend.init_repo(empty)
    # Unborn HEAD — no commits yet.
    assert git_backend.history_detailed(empty) == []
