"""Pytest configuration: inject stub modules for optional SDK dependencies."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Stub out the openai and anthropic packages so tests run without them
# installed. The stubs just need to be importable; actual client behaviour
# is patched per-test.
for _mod in ("openai", "anthropic"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
