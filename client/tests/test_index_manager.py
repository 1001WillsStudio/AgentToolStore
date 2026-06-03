"""Tests for IndexManager public reload API — the fix for caching bugs.

These tests verify that :meth:`IndexManager.reload` correctly refreshes
in-memory state from disk after external modifications.

Before Option B, code called the private ``_load_local()`` throughout
the codebase.  Now ``reload()`` is the public entry point.
"""

import json
from pathlib import Path

import pytest

from toolstore.index_manager import IndexManager


class TestIndexManagerReload:
    """Verify reload() picks up external disk changes."""

    @pytest.fixture
    def empty_manager(self, tmp_path: Path) -> IndexManager:
        """Return an IndexManager pointed at a temp directory."""
        im = IndexManager()
        im._local_registry_file = tmp_path / "local_registry.json"
        im._local_tools = {}
        im._local_skills = {}
        im._local_mcp = {}
        im.save_local()
        return im

    def test_reload_picks_up_external_write(
        self, empty_manager: IndexManager
    ) -> None:
        """Write to the registry file externally, then reload — state must update."""
        im = empty_manager
        assert im._local_tools == {}

        # Simulate external write (e.g. WebUI) to local_registry.json
        new_data = {
            "mcp_servers": {},
            "skills": {"test-skill": {"name": "test-skill"}},
            "toolsets": {"test-toolset": {"name": "test-toolset"}},
        }
        Path(im._local_registry_file).write_text(json.dumps(new_data))

        # After reload, state is refreshed from disk
        im.reload()
        assert im._local_tools == {"test-toolset": {"name": "test-toolset"}}
        assert im._local_skills == {"test-skill": {"name": "test-skill"}}

    def test_reload_all_delegates_to_load(
        self, empty_manager: IndexManager
    ) -> None:
        """reload_all() must call load() without crashing."""
        im = empty_manager
        im.save_local()
        im.reload_all()  # should not crash
        assert isinstance(im._local_tools, dict)

    def test_multiple_reloads_are_idempotent(
        self, empty_manager: IndexManager
    ) -> None:
        """Calling reload() multiple times with no changes is safe."""
        im = empty_manager
        im.reload()
        state_before = dict(im._local_tools)
        im.reload()
        assert im._local_tools == state_before
        im.reload()
        assert im._local_tools == state_before
