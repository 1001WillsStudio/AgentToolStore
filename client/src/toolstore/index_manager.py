import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from toolstore.config_manager import ConfigManager
from toolstore.toolset_manager import ToolsetDefinition

import logging
logger = logging.getLogger(__name__)


class IndexManager:
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir:
            self.config_dir = config_dir
        else:
            # Use same resolution as ConfigManager — respects TOOLSTORE_HOME
            self.config_dir = ConfigManager().config_dir

        self.registry_file = self.config_dir / "online_registry.json"
        self._local_registry_file = self.config_dir / "local_registry.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.index_data: Dict[str, Any] = {"meta": {}, "tools": {}}
        self._local_mcp: Dict[str, Dict[str, Any]] = {}
        self._local_skills: Dict[str, Dict[str, Any]] = {}
        self._local_tools: Dict[str, Dict[str, Any]] = {}

    # ----------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------

    def load(self):
        """Load remote registry AND local registry from disk into memory."""

        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    self.index_data = json.load(f)
            except json.JSONDecodeError:
                self.index_data = {"meta": {}, "tools": {}}

        self._load_local()

    def reload(self) -> None:
        """Re-read local state from disk (skills, toolsets, MCP servers).

        Call this after external modifications (e.g. WebUI) to ensure the
        in-memory cache reflects the latest disk state.
        """
        self._load_local()

    def reload_all(self) -> None:
        """Re-read remote registry AND local state from disk."""
        self.load()

    def save(self):
        """Save current in-memory registry to disk."""
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.index_data, f, indent=2)

    # ----------------------------------------------------------------
    # Tool management
    # ----------------------------------------------------------------

    def update_from_remote(self, remote_data: List[Dict[str, Any]]):
        """Replace the online registry with freshly fetched remote data.

        This is the **only** place that writes to ``online_registry.json``.
        """
        self.index_data["tools"].clear()
        for tool in remote_data:
            name = tool.get("name")
            if name:
                tool.setdefault("source", "public")
                self.index_data["tools"][name] = tool

        self.index_data["meta"]["last_updated"] = datetime.now(
            timezone.utc).isoformat()
        self.index_data["meta"]["count"] = len(self.index_data["tools"])
        self.save()

    # ── Local registry (all 3 types: MCP / Skill / Toolset) ──

    _migration_done: bool = False

    def _load_local(self) -> None:
        """Load all local state from ``local_registry.json``."""
        if self._local_registry_file.exists():
            try:
                data = json.loads(self._local_registry_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        else:
            data = {}

        self._local_mcp = data.get("mcp_servers", {})
        self._local_skills = data.get("skills", {})
        self._local_tools = data.get("toolsets", {})
        # Backward compat: old flat format — any toolset-type entries
        legacy = {k: v for k, v in data.items()
                  if k not in ("mcp_servers", "skills", "toolsets")
                  and isinstance(v, dict) and v.get("type") == "toolset"}
        if legacy:
            self._local_tools.update(legacy)

        # One-shot: migrate from settings.json → local_registry.json
        if not self._migration_done:
            self._migrate_from_settings()
            self.__class__._migration_done = True

    def _migrate_from_settings(self) -> None:
        """Pull legacy MCP servers & skills from settings.json into local_registry.json."""
        try:
            cm = ConfigManager()
            cm.load()
            mcp = cm.config.pop("mcpServers", {})
            if mcp and not self._local_mcp:
                self._local_mcp = mcp
            skills = cm.config.pop("skills", {})
            if skills and not self._local_skills:
                self._local_skills.update(skills)
            cm.config.pop("tools", None)
            toolsets = cm.config.pop("toolsets", {})
            if toolsets:
                for ts_name, ts_info in toolsets.items():
                    if ts_name not in self._local_tools:
                        self._local_tools[ts_name] = ts_info
            if mcp or skills or toolsets:
                cm.save()
                self._save_local()
        except Exception:
            logger.debug("Suppressed exception in index_manager.py", exc_info=True)
            pass

    def _save_local(self) -> None:
        """Write all local state to ``local_registry.json``."""
        self._local_registry_file.write_text(
            json.dumps({
                "mcp_servers": self._local_mcp,
                "skills": self._local_skills,
                "toolsets": self._local_tools,
            }, indent=2), encoding="utf-8")


    def discover_local_toolsets(self, toolset_dirs: List[str]) -> None:
        """Scan local toolset directories and persist to ``local_registry.json``.

        These are *never* written to ``online_registry.json`` — the two indices stay
        completely separate.  Queries transparently merge both sources.
        """

        # Only clear toolset-type entries — never wipe skills or MCP
        for name in list(self._local_tools):
            if self._local_tools[name].get("type") == "toolset":
                del self._local_tools[name]
        for dir_path in toolset_dirs:
            ts_dir = Path(dir_path)
            if not ts_dir.is_dir():
                continue
            ts_file = ts_dir / "toolset.py"
            if not ts_file.is_file():
                continue

            td = ToolsetDefinition(ts_dir)
            if not td.load():
                continue

            name = td.name
            self._local_tools[name] = {
                "name": name,
                "type": "toolset",
                "source": "local",
                "toolset_dir": str(ts_dir),
                "description": td.doc.split("\n")[0] if td.doc else name,
                "doc": td.doc,
                "bindings": td.functions,
            }

        self._save_local()

    def register_local_tool(self, tool_def: Dict[str, Any]) -> None:
        """Register a single tool in the LOCAL registry.

        Never touches ``online_registry.json``.
        """
        name = tool_def.get("name")
        if not name:
            raise ValueError("Tool definition must have a 'name'")
        tool_def.setdefault("source", "local")
        self._local_tools[name] = tool_def
        self._save_local()

    def update_local_skills(self, skill_defs: List[Dict[str, Any]]) -> None:
        """Merge skill definitions into the local registry."""
        for tool in skill_defs:
            name = tool.get("name")
            if name:
                tool.setdefault("source", "local")
                self._local_tools[name] = tool
        self._save_local()

    # ── Combined helpers (merge remote + local) ──

    def _all_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return the merged dict of remote and local tools."""
        merged = dict(self.index_data.get("tools", {}))
        merged.update(self._local_tools)
        return merged

    # ── Query methods (search both sources transparently) ──

    def search(self, query: str,
               tool_type: str = None,
               source: str = None) -> List[Dict[str, Any]]:
        """Search for tools matching query across name, description, and keywords.

        Args:
            query: Search string (case-insensitive substring match)
            tool_type: Optional filter by tool type ('mcp', 'skill', 'toolset')
            source: Optional filter by source ('public', 'local', 'mcp:name', 'skill')
        """
        results = []
        query = query.lower()

        for name, tool in self._all_tools().items():
            if tool_type and tool.get("type") != tool_type:
                continue
            if source and tool.get("source") != source:
                continue

            description = tool.get("description", "").lower()
            keywords = tool.get("keywords", [])
            if (query in name.lower()
                    or query in description
                    or any(query in str(k).lower() for k in keywords)):
                results.append(tool)

        return results

    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific tool definition by name (remote first, then local)."""
        return self._all_tools().get(tool_name)

    def list_by_type(self, tool_type: str) -> List[Dict[str, Any]]:
        """Return all tools of a given type (merged)."""
        return [
            t for t in self._all_tools().values()
            if t.get("type") == tool_type
        ]

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Return the full merged tools dict."""
        return dict(self._all_tools())

    def count(self) -> int:
        return len(self._all_tools())
