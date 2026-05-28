"""
ToolStore native tool — the Python entry point that agents call to search,
inspect, and execute ToolStore tools.

Supports three tool types:
- mcp:     External MCP servers (client-managed, established protocol)
- skill:   SKILL.md-based agent skills (client-managed, established format)
- toolset: Agent-centric managed tools — 1 doc + 1 code, @tool bindings
"""

from __future__ import annotations

import json
from typing import Dict, Any, List

from toolstore.index_manager import IndexManager
from toolstore.config_manager import ConfigManager
from toolstore.schema_converter import (
    toolstore_to_openai,
)

# ---------------------------------------------------------------------------
# Global singletons
# ---------------------------------------------------------------------------

index_manager = IndexManager()
config_manager = ConfigManager()


def load_toolstore_data():
    """Load index and config from disk."""
    index_manager.load()
    config_manager.load()


# Load at import time
load_toolstore_data()


# ---------------------------------------------------------------------------
# Main tool function
# ---------------------------------------------------------------------------

def tool_store_tool(
    action: str,
    query: str = None,
    tool_name: str = None,
    tool_names: List[str] = None,
    arguments: Dict[str, Any] = None,
    format: str = "raw",
) -> str:
    """Universal tool manager — search, inspect, and execute tools.

    Args:
        action: 'search', 'info', or 'execute'
        query: Search query string (for 'search')
        tool_name: Name of tool (for 'info' or 'execute')
        tool_names: List of tool names (for 'info'). With default format returns
                    OpenAI schemas; with format='secondary' returns a compact
                    prompt listing names, types, and descriptions.
        arguments: Dict of arguments (for 'execute')
        format: Output format for 'info' — 'raw' (default) returns the full
                ToolStore definition; 'openai' returns an OpenAI function-calling
                schema; 'secondary' returns a prompt-friendly summary line.
    """
    try:
        if action == "search":
            return _do_search(query)
        elif action == "info":
            # Bulk: compact secondary prompt (names + types + descriptions)
            if tool_names and format == "secondary":
                return _do_secondary_prompt(tool_names)
            # Bulk: OpenAI function-calling schemas
            if tool_names:
                return _do_bulk_schema(tool_names)
            # Single tool
            result = _do_info(tool_name)
            if format == "openai":
                try:
                    tool = json.loads(result)
                    return json.dumps(toolstore_to_openai(tool), indent=2)
                except Exception:
                    return result
            if format == "secondary":
                try:
                    tool = json.loads(result)
                    return f"- {tool['name']}"
                except Exception:
                    return result
            return result
        elif action == "execute":
            return _do_execute(tool_name, arguments or {})
        else:
            return f"Error: Unknown action '{action}'. Must be 'search', 'info', or 'execute'."
    except Exception as e:
        return f"Error in tool_store_tool: {str(e)}"


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _do_search(query: str) -> str:
    if not query:
        return "Error: 'query' argument is required for search action."

    index_manager.load()
    results = index_manager.search(query)
    if not results:
        return f"No tools found for query: '{query}'"

    lines: List[str] = [f"Found {len(results)} tools:"]
    for tool in results:
        ttype = tool.get("type", "unknown")
        desc = tool.get("description", "No description")
        lines.append(f"- {tool['name']} ({ttype}): {desc}")
    return "\n".join(lines)


def _do_info(tool_name: str) -> str:
    if not tool_name:
        return "Error: 'tool_name' argument is required for info action."

    # ── Check if tool_name is an MCP server (by id or display_name) ──
    config_manager.load()
    servers = config_manager.config.get("mcpServers", {})

    # Try exact server_id match first
    prefix = f"mcp:{tool_name}"
    mcp_tools: dict[str, dict] = {}
    for tname, tinfo in config_manager.config.get("tools", {}).items():
        if isinstance(tinfo, dict) and tinfo.get("source") == prefix:
            mcp_tools[tname] = tinfo

    # Try display_name match
    if not mcp_tools and isinstance(servers, dict):
        for sid, srv in servers.items():
            if isinstance(srv, dict) and srv.get("display_name") == tool_name:
                prefix = f"mcp:{sid}"
                for tname, tinfo in config_manager.config.get("tools", {}).items():
                    if isinstance(tinfo, dict) and tinfo.get("source") == prefix:
                        mcp_tools[tname] = tinfo
                if mcp_tools:
                    # Use the matched server_id for the response
                    srv_info = srv
                    break

    if mcp_tools:
        # Get server metadata
        actual_sid = tool_name
        srv_info = {}
        if isinstance(servers, dict):
            for sid, srv in servers.items():
                prefix2 = f"mcp:{sid}"
                if any(ti.get("source") == prefix2 for ti in mcp_tools.values() if isinstance(ti, dict)):
                    actual_sid = sid
                    srv_info = srv
                    break

        functions = []
        for tname, tinfo in mcp_tools.items():
            functions.append({
                "name": tname,
                "description": tinfo.get("description", ""),
                "exposure": tinfo.get("exposure", "secondary"),
            })
        return json.dumps({
            "name": srv_info.get("display_name") or actual_sid,
            "server_id": actual_sid,
            "type": "mcp_toolset",
            "exposure": srv_info.get("exposure", "secondary") if isinstance(srv_info, dict) else "secondary",
            "description": f"MCP server with {len(mcp_tools)} tool{'s' if len(mcp_tools) != 1 else ''}",
            "functions": functions,
        }, indent=2)

    # ── Fallback to index lookup ────────────────────────────────────
    index_manager.load()
    tool = index_manager.get_tool(tool_name)
    if not tool:
        return f"Error: Tool '{tool_name}' not found."

    return json.dumps(tool, indent=2)


def _do_bulk_schema(tool_names: List[str]) -> str:
    """Return OpenAI function-calling schemas for a list of tool names.

    The result is a JSON array of objects, each being an OpenAI
    function-calling schema ready to bind as an agent tool definition.
    Tools that cannot be found or converted are reported as error entries.
    """
    schemas: List[Dict[str, Any]] = []
    for name in tool_names:
        tool = index_manager.get_tool(name)
        if not tool:
            schemas.append({"error": f"Tool '{name}' not found"})
            continue
        try:
            schemas.append(toolstore_to_openai(tool))
        except Exception as exc:
            schemas.append({
                "error": f"Failed to convert '{name}': {str(exc)}"
            })
    return json.dumps(schemas, indent=2)


def _do_secondary_prompt(tool_names: List[str]) -> str:
    """Return a name-only listing of secondary tools.

    Secondary tools show only their names in the agent's system prompt
    to keep context footprint minimal.  The agent can call ``tool_store``
    with ``action="info"`` to fetch the full schema when needed.
    """
    header = (
        "Available secondary tools"
        " (use tool_store with action=\"execute\" to call them):"
    )
    lines = [header]

    # ── MCP servers (grouped toolsets) ──────────────────────────────
    config_manager.load()
    mcp_tools_by_server: dict[str, list] = {}
    for tname, tinfo in config_manager.config.get("tools", {}).items():
        source = tinfo.get("source", "") if isinstance(tinfo, dict) else ""
        if source.startswith("mcp:"):
            server = source[4:]
            mcp_tools_by_server.setdefault(server, []).append(tname)

    # Build display-name lookup for MCP servers
    servers = config_manager.config.get("mcpServers", {})
    server_display: dict[str, str] = {}
    if isinstance(servers, dict):
        for sid, srv in servers.items():
            if isinstance(srv, dict):
                server_display[sid] = srv.get("display_name") or sid

    for name in tool_names:
        if name in mcp_tools_by_server:
            tool_count = len(mcp_tools_by_server[name])
            display = server_display.get(name, name)
            lines.append(f"- {display} (MCP server, {tool_count} tool{'s' if tool_count != 1 else ''})")
            continue

        tool = index_manager.get_tool(name)
        if not tool:
            lines.append(f"- {name}: [NOT FOUND]")
            continue
        lines.append(f"- {name}")
    return "\n".join(lines)



# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_secondary_tool_names() -> list[str]:
    """Return names of all tools and toolsets with exposure == 'secondary'.

    MCP tools are grouped by server — each server appears as a single
    toolset-like name rather than listing every individual tool.  The
    server's ``display_name`` is used when set, otherwise the raw server id.

    Always reloads config from disk so tools registered by external
    processes (e.g. the management UI) are visible immediately.
    """
    config_manager.load()

    names: list[str] = []
    mcp_servers: dict[str, str] = {}  # display_name → server_id

    toolsets = config_manager.config.get("toolsets", {})
    if isinstance(toolsets, dict):
        for name, info in toolsets.items():
            if isinstance(info, dict) and info.get("exposure") == "secondary":
                names.append(name)

    tools = config_manager.config.get("tools", {})
    if isinstance(tools, dict):
        for name, info in tools.items():
            if not isinstance(info, dict):
                continue
            if info.get("exposure") != "secondary":
                continue
            source = info.get("source", "")
            if source.startswith("mcp:"):
                server_id = source[4:]
                mcp_srv = config_manager.config.get("mcpServers", {}).get(server_id, {})
                if isinstance(mcp_srv, dict):
                    display = mcp_srv.get("display_name") or server_id
                    if mcp_srv.get("exposure", "secondary") == "secondary":
                        mcp_servers[display] = server_id
                else:
                    mcp_servers[server_id] = server_id
            else:
                names.append(name)  # skill:xxx, etc.

    # Each MCP server appears as one toolset-like entry, using its display_name
    names.extend(sorted(mcp_servers.keys()))

    return names


# ---------------------------------------------------------------------------
# Execute — delegates to exec_tools.py
# ---------------------------------------------------------------------------

def _do_execute(tool_name: str, args: Dict[str, Any]) -> str:
    from toolstore.exec_tools import execute_tool

    if not tool_name:
        return "Error: 'tool_name' argument is required for execute action."

    tool = index_manager.get_tool(tool_name)
    if not tool:
        return f"Error: Tool '{tool_name}' not found."

    return execute_tool(tool, args, config_manager, index_manager)

