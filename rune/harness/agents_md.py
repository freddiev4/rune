"""AGENTS.md project documentation discovery and loading.

Discovers AGENTS.md files by walking from the current working directory up to
the git repository root.  Files are collected root-first so that deeper
(more-specific) instructions come after broader repo-level ones.

Inspired by the Codex (codex-rs) approach with the addition of per-file path
metadata in the concatenated output (like OpenCode).

Key design decisions:
  - Walk upward from cwd to git root; collect one file per directory.
  - 32 KiB byte budget across all files (truncates later files if exceeded).
  - Each file is prefixed with its path so the model knows the scope.
  - Graceful fallback: returns None when no files exist.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Default filename checked at each directory level.
DEFAULT_FILENAME = "AGENTS.md"

# Maximum total bytes that will be read across all discovered files.
MAX_TOTAL_BYTES = 32 * 1024  # 32 KiB


def _find_git_root(start: Path) -> Path | None:
    """Find the git repository root by walking upward from *start*.

    Uses ``git rev-parse --show-toplevel`` when available, falling back to a
    manual walk looking for a ``.git`` directory/file.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: manual walk
    cursor = start.resolve()
    while True:
        if (cursor / ".git").exists():
            return cursor
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent
    return None


def discover_project_doc_paths(
    working_dir: str | Path,
    filename: str = DEFAULT_FILENAME,
) -> list[Path]:
    """Discover AGENTS.md files from git root down to *working_dir*.

    The returned list is ordered root-first (shallowest to deepest) so that
    when concatenated the most-specific instructions appear last.

    Args:
        working_dir: The current working directory to start from.
        filename: The filename to look for (default ``AGENTS.md``).

    Returns:
        List of resolved ``Path`` objects for each discovered file.
    """
    cwd = Path(working_dir).resolve()
    git_root = _find_git_root(cwd)

    # Build the chain of directories from cwd upward to (and including) the
    # git root.  If there is no git root we only check the cwd itself.
    chain: list[Path] = []
    cursor = cwd
    while True:
        chain.append(cursor)
        if git_root and cursor == git_root:
            break
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent

    # Reverse so the order is root → cwd (shallowest first).
    chain.reverse()

    paths: list[Path] = []
    for directory in chain:
        candidate = directory / filename
        if candidate.is_file():
            paths.append(candidate.resolve())

    return paths


def read_project_docs(
    working_dir: str | Path,
    filename: str = DEFAULT_FILENAME,
    max_bytes: int = MAX_TOTAL_BYTES,
) -> str | None:
    """Read and concatenate all discovered AGENTS.md files.

    Each file is prefixed with a ``Instructions from: <path>`` header so the
    model knows which directory each block of instructions comes from.

    Args:
        working_dir: The current working directory.
        filename: Filename to search for.
        max_bytes: Maximum total bytes to read across all files.

    Returns:
        Concatenated string with per-file headers, or ``None`` if no files
        were found.
    """
    if max_bytes <= 0:
        return None

    paths = discover_project_doc_paths(working_dir, filename=filename)
    if not paths:
        return None

    remaining = max_bytes
    parts: list[str] = []

    for path in paths:
        if remaining <= 0:
            break
        try:
            raw = path.read_bytes()
        except OSError:
            continue

        # Enforce byte budget.
        if len(raw) > remaining:
            raw = raw[:remaining]

        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            continue

        parts.append(f"Instructions from: {path}\n{text}")
        remaining -= len(raw)

    if not parts:
        return None

    return "\n\n".join(parts)
