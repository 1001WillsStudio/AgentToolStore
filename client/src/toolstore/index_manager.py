import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional


class IndexManager:
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir:
            self.config_dir = config_dir
        else:
            # Use same resolution as ConfigManager — respects TOOLSTORE_HOME
            from toolstore.config_manager import ConfigManager as _CM
            self.config_dir = _CM().config_dir

        self.registry_file = self.config_dir / "registry.json"
        self._legacy_file = self.config_dir / "index.json"  # pre-rename
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.index_data: Dict[str, Any] = {"meta": {}, "tools": {}}

    # ----------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------

    def load(self):
        """Load registry from disk into memory.
        Auto-migrates from old 'index.json' name on first access."""
        # Migration: if registry.json doesn't exist but index.json does, rename it
        if not self.registry_file.exists() and self._legacy_file.exists():
            self._legacy_file.rename(self.registry_file)

        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    self.index_data = json.load(f)
            except json.JSONDecodeError:
                self.index_data = {"meta": {}, "tools": {}}

    def save(self):
        """Save current in-memory registry to disk."""
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.index_data, f, indent=2)

    # ----------------------------------------------------------------
    # Tool management
    # ----------------------------------------------------------------

    def update_from_remote(self, remote_data: List[Dict[str, Any]]):
        """Merge remote data (public index, MCP scan, skill scan) into the index."""
        for tool in remote_data:
            name = tool.get("name")
            if name:
                tool.setdefault("source", "public")
                self.index_data["tools"][name] = tool

        self.index_data["meta"]["last_updated"] = datetime.now(
            timezone.utc).isoformat()
        self.index_data["meta"]["count"] = len(self.index_data["tools"])
        self.save()

    def register_tool(self, tool_def: Dict[str, Any]) -> None:
        """Register or update a single tool."""
        name = tool_def.get("name")
        if not name:
            raise ValueError("Tool definition must have a 'name'")
        tool_def.setdefault("source", "local")
        self.index_data["tools"][name] = tool_def
        self.index_data["meta"]["count"] = len(self.index_data["tools"])
        self.save()

    def unregister_tool(self, name: str) -> bool:
        """Remove a tool from the index. Returns True if it existed."""
        existed = name in self.index_data.get("tools", {})
        self.index_data["tools"].pop(name, None)
        self.index_data["meta"]["count"] = len(self.index_data["tools"])
        if existed:
            self.save()
        return existed

    # ----------------------------------------------------------------
    # Search
    # ----------------------------------------------------------------

    def search(self, query: str,
               tool_type: str = None,
               source: str = None) -> List[Dict[str, Any]]:
        """Search for tools matching query across name, description, and keywords.

        Args:
            query: Search string (case-insensitive substring match)
            tool_type: Optional filter by tool type ('api', 'mcp', 'skill')
            source: Optional filter by source ('public', 'mcp:name', 'skill')
        """
        results = []
        query = query.lower()
        tools = self.index_data.get("tools", {})

        for name, tool in tools.items():
            # Type filter
            if tool_type and tool.get("type") != tool_type:
                continue
            # Source filter
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
        """Get a specific tool definition by name."""
        return self.index_data.get("tools", {}).get(tool_name)

    # ----------------------------------------------------------------
    # Type-aware queries
    # ----------------------------------------------------------------

    def list_by_type(self, tool_type: str) -> List[Dict[str, Any]]:
        """Return all tools of a given type."""
        return [
            t for t in self.index_data.get("tools", {}).values()
            if t.get("type") == tool_type
        ]

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Return the full tools dict."""
        return dict(self.index_data.get("tools", {}))

    def count(self) -> int:
        return len(self.index_data.get("tools", {}))
