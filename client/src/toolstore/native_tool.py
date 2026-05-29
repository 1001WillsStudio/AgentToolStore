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

    # ── Also scan skill dirs and auto-register matching skills ──
    config_manager.load()
    skill_dirs = config_manager.get_skill_dirs()
    if skill_dirs:
        from toolstore.skill_manager import get_skill_manager
        sm = get_skill_manager(skill_dirs)
        if not sm.list_skill_names():
            sm.scan()
        query_lower = query.lower()
        for skill_name in sm.list_skill_names():
            sd = sm.get_skill(skill_name)
            if not sd:
                continue
            skill_key = f"skill:{skill_name}"
            # Check if already in results
            if any(r.get("name") == skill_key for r in results):
                continue
            # Check if matches query
            desc = sd.description.lower()
            if (query_lower in skill_name.lower()
                    or query_lower in desc
                    or query_lower in skill_key.lower()):
                # Auto-register in index so future calls find it
                tool = sd.to_tool_definition()
                tool["name"] = skill_key
                index_manager.register_local_tool(tool)
                results.append(tool)

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

    # ── Skill:xxx fallback ── scan skill dirs and auto-register ──
    if tool_name.startswith("skill:"):
        config_manager.load()
        raw_name = tool_name[len("skill:"):]
        from toolstore.skill_manager import get_skill_manager
        sm = get_skill_manager(config_manager.get_skill_dirs())
        if not sm.get_skill(raw_name):
            sm.scan()
        sd = sm.get_skill(raw_name)
        if sd:
            tool = sd.to_tool_definition()
            tool["name"] = tool_name
            index_manager.register_local_tool(tool)
            return json.dumps(tool, indent=2)

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
    display_to_server: dict[str, str] = {}  # reverse lookup for _do_secondary_prompt
    if isinstance(servers, dict):
        for sid, srv in servers.items():
            if isinstance(srv, dict):
                dname = srv.get("display_name") or sid
                server_display[sid] = dname
                display_to_server[dname] = sid

    for name in tool_names:
        # Direct server-id match (e.g. "echo-server")
        if name in mcp_tools_by_server:
            tool_count = len(mcp_tools_by_server[name])
            display = server_display.get(name, name)
            lines.append(f"- {display} (MCP server, {tool_count} tool{'s' if tool_count != 1 else ''})")
            continue
        # display_name match (e.g. "Echo Service")
        if name in display_to_server:
            sid = display_to_server[name]
            tool_count = len(mcp_tools_by_server.get(sid, []))
            lines.append(f"- {name} (MCP server, {tool_count} tool{'s' if tool_count != 1 else ''})")
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
    servers = config_manager.config.get("mcpServers", {})
    if isinstance(tools, dict):
        for name, info in tools.items():
            if not isinstance(info, dict):
                continue
            if info.get("exposure") != "secondary":
                continue
            source = info.get("source", "")
            if source.startswith("mcp:"):
                server_id = source[4:]
                mcp_srv = servers.get(server_id, {}) if isinstance(servers, dict) else {}
                if isinstance(mcp_srv, dict) and mcp_srv.get("mode", "toolset") == "individual":
                    # Individual mode: each tool appears as its own entry
                    names.append(name)
                elif isinstance(mcp_srv, dict):
                    # Toolset mode: group by server display_name
                    display = mcp_srv.get("display_name") or server_id
                    if mcp_srv.get("exposure", "secondary") == "secondary":
                        mcp_servers[display] = server_id
                else:
                    mcp_servers[server_id] = server_id
            else:
                names.append(name)  # skill:xxx, etc.

    # ── Also include MCP servers whose server-level exposure is secondary,
    # even if their individual tools are hidden (the agent can discover
    # tools via tool_store info when it needs the server).
    # Only applies to toolset-mode servers.
    if isinstance(servers, dict):
        for sid, srv in servers.items():
            if not isinstance(srv, dict):
                continue
            if srv.get("mode", "toolset") != "toolset":
                continue
            if srv.get("exposure", "secondary") != "secondary":
                continue
            display = srv.get("display_name") or sid
            if display not in mcp_servers:
                mcp_servers[display] = sid

    # Each MCP server appears as one toolset-like entry, using its display_name
    names.extend(sorted(mcp_servers.keys()))

    return names


# ---------------------------------------------------------------------------
# Execute — delegates to exec_tools.py
# ---------------------------------------------------------------------------

def _do_execute(tool_name: str, args: Dict[str, Any]) -> str:
    if not tool_name:
        return "Error: 'tool_name' argument is required for execute action."

    index_manager.load()
    tool = index_manager.get_tool(tool_name)

    if not tool and tool_name.startswith("skill:"):
        config_manager.load()
        raw_name = tool_name[len("skill:"):]
        from toolstore.skill_manager import get_skill_manager
        sm = get_skill_manager(config_manager.get_skill_dirs())
        if not sm.get_skill(raw_name):
            sm.scan()
        sd = sm.get_skill(raw_name)
        if sd:
            tool = sd.to_tool_definition()
            tool["name"] = tool_name
            index_manager.register_local_tool(tool)

    if not tool:
        # Maybe it's an MCP server (toolset mode) — look up by display_name or id
        tool = _resolve_mcp_toolset(tool_name, args)

    if not tool:
        return f"Error: Tool '{tool_name}' not found."

    tool_type = tool.get("type", "unknown")

    # toolset → fast inline path
    if tool_type == "toolset":
        return _execute_toolset_inline(tool, args)

    # mcp_toolset → resolve function → dispatch to MCP backend
    if tool_type == "mcp_toolset":
        return _execute_mcp_toolset(tool, args)

    # mcp / skill / everything else → exec_tools dispatch
    from toolstore.exec_tools import execute_tool
    return execute_tool(tool, args, config_manager, index_manager)


# ---------------------------------------------------------------------------
# MCP toolset helpers
# ---------------------------------------------------------------------------

def _resolve_mcp_toolset(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any] | None:
    """Resolve an MCP server (toolset mode) to a specific MCP tool.

    ``tool_name`` is either a server ``display_name`` (e.g. "Echo Server")
    or the raw server id (e.g. "echo-server").  The ``function`` argument
    selects which individual MCP tool to execute.
    """
    config_manager.load()
    servers = config_manager.config.get("mcpServers", {})
    if not isinstance(servers, dict):
        return None

    # Build server-id → (display_name, tools) lookup
    server_map: Dict[str, tuple] = {}
    tools = config_manager.config.get("tools", {})

    for sid, srv in servers.items():
        if not isinstance(srv, dict):
            continue
        display = srv.get("display_name") or sid
        prefix = f"mcp:{sid}"
        server_tools: Dict[str, dict] = {}
        for tname, tinfo in tools.items():
            if isinstance(tinfo, dict) and tinfo.get("source") == prefix:
                server_tools[tname] = tinfo
        if server_tools:
            server_map[sid] = (display, server_tools)
            server_map[display] = (display, server_tools)  # also key by display_name

    if tool_name not in server_map:
        return None

    _display, server_tools = server_map[tool_name]

    # Which function?
    function_name = args.get("function")
    if not function_name and len(server_tools) == 1:
        function_name = next(iter(server_tools))

    if not function_name:
        return None  # caller will report missing function

    mcp_tool = server_tools.get(function_name)
    if not mcp_tool:
        return None

    # Build a fake tool dict with type="mcp" so _execute_mcp can consume it
    return {
        "name": function_name,
        "type": "mcp",
        "mcp_server": mcp_tool.get("source", "").replace("mcp:", ""),
    }


def _execute_mcp_toolset(tool: Dict[str, Any], args: Dict[str, Any]) -> str:
    """Execute an MCP tool resolved from toolset mode.

    This is the toolset-mode counterpart of the individual-mode path.
    The tool dict was built by ``_resolve_mcp_toolset`` with the specific
    MCP tool name and server already resolved.
    """
    from toolstore.exec_tools import _execute_mcp

    function_name = args.get("function")
    if not function_name:
        return "Error: 'function' argument required. Specify which MCP tool to call."

    # _execute_mcp expects the tool dict to have "name" and "mcp_server"
    return _execute_mcp(tool, args, config_manager)


def _execute_toolset_inline(tool: Dict[str, Any], args: Dict[str, Any]) -> str:
    """Self-contained toolset execution — no external imports needed."""
    import base64
    import importlib
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    args = dict(args)
    bindings = tool.get("bindings", {})
    function_name = args.pop("function", None)
    if not function_name:
        if len(bindings) == 1:
            function_name = next(iter(bindings))
        else:
            names = list(bindings.keys()) if bindings else []
            return f"Error: 'function' argument required. Available: {', '.join(names) or '(none)'}"

    if function_name not in bindings:
        names = list(bindings.keys())
        return f"Error: Unknown function '{function_name}'. Available: {', '.join(names)}"

    code = tool.get("code", "")
    code_b64 = tool.get("code_base64", "")
    if code_b64 and not code:
        code = base64.b64decode(code_b64).decode("utf-8")

    # Local toolsets: read code from toolset_dir on disk
    if not code and tool.get("toolset_dir"):
        ts_dir = Path(tool["toolset_dir"])
        ts_file = ts_dir / "toolset.py"
        if ts_file.exists():
            code = ts_file.read_text(encoding="utf-8")

    if not code:
        return "Error: toolset has no code to execute"

    with tempfile.TemporaryDirectory(prefix="toolset_") as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "toolset.py").write_text(code, encoding="utf-8")

        requirements = tool.get("requirements", [])
        if isinstance(requirements, str):
            requirements = [r.strip() for r in requirements.split("\n") if r.strip()]
        if requirements:
            return (
                f"Error: Toolset '{function_name}' requires additional packages: "
                f"{', '.join(requirements)}.\n"
                f"Install them first: pip install {' '.join(requirements)}"
            )

        # Dynamically load and call the function
        mod_name = f"_toolset_{function_name}"
        spec = importlib.util.spec_from_file_location(mod_name, tmp / "toolset.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        fn = getattr(mod, function_name, None)
        if fn is None:
            return f"Error: Function '{function_name}' not found in toolset code"

        try:
            result = fn(**args)
            return json.dumps(result, default=str, indent=2)
        except Exception as exc:
            return f"Error executing '{function_name}': {exc}"

