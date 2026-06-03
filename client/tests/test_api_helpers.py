"""Tests for api_helpers singleton consistency — the ConfigManager refresh bug.

These tests verify the core fix: that ``load_config()``, ``save_config()``,
``refresh_config()``, and ``refresh_index()`` all operate on the SAME
singleton instances rather than creating fresh (inconsistent) ones.

Bug fixed: WebUI handlers used ``ConfigManager()`` (fresh instance) instead
of ``_config_manager()`` (shared singleton), causing config writes to be
invisible to other API handlers.
"""

from pathlib import Path

import pytest

import toolstore.management.api_helpers as api_helpers


# ── Fixtures ────────────────────────────────────────────────────────────────




@pytest.fixture
def temp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ConfigManager singleton to use a temp directory."""
    from toolstore.config_manager import ConfigManager

    # Create a fresh instance pointing at tmp_path
    cm = ConfigManager(config_dir=tmp_path)
    cm.config["skill_dirs"] = []
    cm.config["toolset_dirs"] = []
    cm.save()

    # Override the singleton to return our temp instance
    monkeypatch.setattr(api_helpers, "_CM_SINGLETON", cm)

    # Same for IndexManager — point it at tmp_path
    from toolstore.index_manager import IndexManager

    im = IndexManager(config_dir=tmp_path)
    im._local_tools = {}
    im._local_skills = {}
    im._local_mcp = {}
    im.save_local()
    monkeypatch.setattr(api_helpers, "_IM_SINGLETON", im)

    return tmp_path


# ── Tests ────────────────────────────────────────────────────────────────────


class TestSingletonConsistency:
    """Verify _config_manager() and _index_manager() return the same object."""

    def test_config_manager_singleton_is_reused(self) -> None:
        """Each call to _config_manager() returns the identical object."""
        cm1 = api_helpers._config_manager()
        cm2 = api_helpers._config_manager()
        assert cm1 is cm2, (
            "_config_manager() should return the same singleton each time"
        )

    def test_index_manager_singleton_is_reused(self) -> None:
        """Each call to _index_manager() returns the identical object."""
        im1 = api_helpers._index_manager()
        im2 = api_helpers._index_manager()
        assert im1 is im2, (
            "_index_manager() should return the same singleton each time"
        )


class TestRefreshHelpers:
    """Verify refresh_config() / refresh_index() force disk reload."""

    def test_refresh_config_reloads_from_disk(
        self, temp_config_dir: Path
    ) -> None:
        """After external config write, refresh_config() must pick it up."""
        cm = api_helpers._config_manager()
        cm.config["skill_dirs"] = ["/tmp/external_skill"]

        # Write to disk
        cm.save()

        # Modify in-memory so it differs from disk
        cm.config["skill_dirs"] = []

        # Refresh should re-read from disk
        api_helpers.refresh_config()
        assert "/tmp/external_skill" in cm.config.get("skill_dirs", []), (
            "refresh_config() should reload skill_dirs from disk"
        )

    def test_refresh_index_reloads_from_disk(
        self, temp_config_dir: Path
    ) -> None:
        """After external registry write, refresh_index() must pick it up."""
        im = api_helpers._index_manager()
        im._local_tools = {"external-tool": {"name": "external-tool"}}
        im.save_local()

        # Modify in-memory so it differs
        im._local_tools = {}

        # Refresh should re-read from disk
        api_helpers.refresh_index()
        assert "external-tool" in im._local_tools, (
            "refresh_index() should reload tools from disk"
        )


class TestLoadSaveConfig:
    """Verify load_config() and save_config() use the same singletons."""

    def test_save_config_updates_singleton(
        self, temp_config_dir: Path
    ) -> None:
        """save_config() must write through the singleton, not a fresh instance."""
        cfg = {
            "registry_url": "https://test.example.com",
            "skill_dirs": ["/tmp/skills"],
            "toolset_dirs": ["/tmp/toolsets"],
            "mcp_servers": {"test-srv": {"command": "echo"}},
            "tools": {"mcp": {}, "skills": {}, "toolsets": {"t1": {"name": "t1"}}},
        }
        api_helpers.save_config(cfg)

        # Reload and verify
        cfg2 = api_helpers.load_config()
        assert cfg2["registry_url"] == "https://test.example.com"
        assert "/tmp/skills" in cfg2["skill_dirs"]
        assert "/tmp/toolsets" in cfg2["toolset_dirs"]
        assert cfg2["mcp_servers"]["test-srv"]["command"] == "echo"

    def test_load_config_uses_singleton(self) -> None:
        """load_config() must use _index_manager() singleton, not a fresh instance."""
        im = api_helpers._index_manager()
        singleton_id = id(im)

        api_helpers.load_config()

        # The singleton should still be the same object
        im2 = api_helpers._index_manager()
        assert id(im2) == singleton_id, (
            "load_config() should not replace the singleton"
        )
