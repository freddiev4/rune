"""Tests for the AGENTS.md discovery and loading system."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from rune.harness.agents_md import (
    DEFAULT_FILENAME,
    MAX_TOTAL_BYTES,
    _find_git_root,
    discover_project_doc_paths,
    read_project_docs,
)
from rune.harness.session import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary directory that looks like a git repo."""
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def nested_git_repo(git_repo):
    """Git repo with nested subdirectories."""
    sub = git_repo / "packages" / "app"
    sub.mkdir(parents=True)
    return git_repo, sub


# ---------------------------------------------------------------------------
# _find_git_root
# ---------------------------------------------------------------------------

class TestFindGitRoot:

    def test_finds_git_dir(self, git_repo):
        """Direct .git directory is found."""
        root = _find_git_root(git_repo)
        assert root == git_repo.resolve()

    def test_finds_git_from_subdirectory(self, nested_git_repo):
        """Walking up from a subdirectory finds the repo root."""
        repo, sub = nested_git_repo
        root = _find_git_root(sub)
        assert root == repo.resolve()

    def test_no_git_returns_none(self, tmp_path):
        """Returns None when there is no .git anywhere."""
        # Use a nested path far from any real .git to avoid finding
        # the host machine's repo.
        isolated = tmp_path / "a" / "b" / "c"
        isolated.mkdir(parents=True)
        with patch("rune.harness.agents_md.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            root = _find_git_root(isolated)
        assert root is None


# ---------------------------------------------------------------------------
# discover_project_doc_paths
# ---------------------------------------------------------------------------

class TestDiscoverPaths:

    def test_no_agents_md(self, git_repo):
        """Returns empty list when no AGENTS.md exists."""
        paths = discover_project_doc_paths(git_repo)
        assert paths == []

    def test_single_at_root(self, git_repo):
        """Discovers AGENTS.md at the repo root."""
        (git_repo / DEFAULT_FILENAME).write_text("root instructions")
        paths = discover_project_doc_paths(git_repo)
        assert len(paths) == 1
        assert paths[0] == (git_repo / DEFAULT_FILENAME).resolve()

    def test_single_at_subdirectory(self, nested_git_repo):
        """Discovers AGENTS.md only in a subdirectory."""
        repo, sub = nested_git_repo
        (sub / DEFAULT_FILENAME).write_text("sub instructions")
        paths = discover_project_doc_paths(sub)
        assert len(paths) == 1
        assert paths[0] == (sub / DEFAULT_FILENAME).resolve()

    def test_root_and_subdirectory(self, nested_git_repo):
        """Discovers both root and subdirectory files, root-first."""
        repo, sub = nested_git_repo
        (repo / DEFAULT_FILENAME).write_text("root")
        (sub / DEFAULT_FILENAME).write_text("sub")
        paths = discover_project_doc_paths(sub)
        assert len(paths) == 2
        assert paths[0] == (repo / DEFAULT_FILENAME).resolve()
        assert paths[1] == (sub / DEFAULT_FILENAME).resolve()

    def test_intermediate_directory(self, git_repo):
        """Discovers files in intermediate directories too."""
        mid = git_repo / "packages"
        deep = mid / "app"
        deep.mkdir(parents=True)
        (git_repo / DEFAULT_FILENAME).write_text("root")
        (mid / DEFAULT_FILENAME).write_text("mid")
        (deep / DEFAULT_FILENAME).write_text("deep")
        paths = discover_project_doc_paths(deep)
        assert len(paths) == 3
        assert paths[0] == (git_repo / DEFAULT_FILENAME).resolve()
        assert paths[1] == (mid / DEFAULT_FILENAME).resolve()
        assert paths[2] == (deep / DEFAULT_FILENAME).resolve()

    def test_custom_filename(self, git_repo):
        """Supports a custom filename instead of AGENTS.md."""
        (git_repo / "CUSTOM.md").write_text("custom")
        paths = discover_project_doc_paths(git_repo, filename="CUSTOM.md")
        assert len(paths) == 1

    def test_no_git_repo_only_cwd(self, tmp_path):
        """Without a git repo, only checks the cwd."""
        isolated = tmp_path / "no_git"
        isolated.mkdir()
        (isolated / DEFAULT_FILENAME).write_text("here")
        with patch("rune.harness.agents_md._find_git_root", return_value=None):
            paths = discover_project_doc_paths(isolated)
        # Should still find the file in the cwd itself
        assert len(paths) == 1


# ---------------------------------------------------------------------------
# read_project_docs
# ---------------------------------------------------------------------------

class TestReadProjectDocs:

    def test_no_files_returns_none(self, git_repo):
        """Returns None when nothing is found."""
        result = read_project_docs(git_repo)
        assert result is None

    def test_single_file_with_header(self, git_repo):
        """Single file gets the 'Instructions from:' header."""
        (git_repo / DEFAULT_FILENAME).write_text("# Root Instructions\nDo stuff.")
        result = read_project_docs(git_repo)
        assert result is not None
        assert result.startswith("Instructions from: ")
        assert "# Root Instructions" in result
        assert "Do stuff." in result

    def test_multiple_files_concatenated(self, nested_git_repo):
        """Multiple files are concatenated with headers."""
        repo, sub = nested_git_repo
        (repo / DEFAULT_FILENAME).write_text("root content")
        (sub / DEFAULT_FILENAME).write_text("sub content")
        result = read_project_docs(sub)
        assert result is not None
        lines = result.split("\n\n")
        # First block: root
        assert "root content" in lines[0]
        assert str(repo.resolve()) in lines[0]
        # Second block: sub
        joined_rest = "\n\n".join(lines[1:])
        assert "sub content" in joined_rest
        assert str(sub.resolve()) in joined_rest

    def test_byte_budget_truncation(self, git_repo):
        """Files beyond the byte budget are truncated."""
        content = "x" * 100
        (git_repo / DEFAULT_FILENAME).write_text(content)
        result = read_project_docs(git_repo, max_bytes=50)
        assert result is not None
        # The raw content should be at most 50 bytes (before the header)
        # Find the actual content after the header line
        header_end = result.index("\n")
        body = result[header_end + 1:]
        assert len(body.encode("utf-8")) <= 50

    def test_zero_budget_returns_none(self, git_repo):
        """A zero byte budget returns None."""
        (git_repo / DEFAULT_FILENAME).write_text("content")
        result = read_project_docs(git_repo, max_bytes=0)
        assert result is None

    def test_empty_file_skipped(self, git_repo):
        """Empty AGENTS.md files are skipped."""
        (git_repo / DEFAULT_FILENAME).write_text("")
        result = read_project_docs(git_repo)
        assert result is None

    def test_whitespace_only_file_skipped(self, git_repo):
        """Whitespace-only files are skipped."""
        (git_repo / DEFAULT_FILENAME).write_text("   \n\n  ")
        result = read_project_docs(git_repo)
        assert result is None

    @pytest.mark.skipif(
        os.getuid() == 0, reason="Root ignores file permissions"
    )
    def test_unreadable_file_skipped(self, git_repo):
        """Unreadable files are skipped without error."""
        agents = git_repo / DEFAULT_FILENAME
        agents.write_text("content")
        agents.chmod(0o000)
        try:
            result = read_project_docs(git_repo)
            # Should either return None or skip the unreadable file gracefully
            assert result is None
        finally:
            agents.chmod(0o644)

    def test_budget_spans_multiple_files(self, nested_git_repo):
        """Byte budget is shared across all files."""
        repo, sub = nested_git_repo
        (repo / DEFAULT_FILENAME).write_text("a" * 100)
        (sub / DEFAULT_FILENAME).write_text("b" * 100)
        # Budget only allows ~120 bytes total
        result = read_project_docs(sub, max_bytes=120)
        assert result is not None
        # Root file should be fully included, sub file truncated
        assert "a" * 100 in result
        # Sub file should have at most 20 bytes of content
        parts = result.split("Instructions from: ")
        assert len(parts) >= 2  # At least one header split


# ---------------------------------------------------------------------------
# Session compaction stripping
# ---------------------------------------------------------------------------

class TestCompactionStripping:

    def test_strips_project_doc_from_system_prompt(self):
        """Compaction removes AGENTS.md blocks from the system prompt."""
        system = (
            "You are a coding assistant.\n"
            "\nWorking Directory: /home/user/proj\n"
            "\nInstructions from: /home/user/proj/AGENTS.md\n"
            "# Project rules\nUse tabs."
        )
        session = Session(working_dir="/tmp", system_prompt=system)
        session.add_user_message("hello")
        session.add_assistant_message("hi")

        session.compact("Summary of conversation.")

        # System message should no longer contain the AGENTS.md block
        system_content = session.messages[0].content
        assert "Instructions from:" not in system_content
        assert "Use tabs" not in system_content
        # But should still have the base prompt
        assert "You are a coding assistant." in system_content

    def test_preserves_prompt_without_project_doc(self):
        """Compaction is a no-op for system prompts without AGENTS.md."""
        system = "You are a coding assistant.\n\nWorking Directory: /tmp\n"
        session = Session(working_dir="/tmp", system_prompt=system)
        session.add_user_message("hello")
        session.add_assistant_message("hi")

        session.compact("Summary.")

        system_content = session.messages[0].content
        assert "You are a coding assistant." in system_content
