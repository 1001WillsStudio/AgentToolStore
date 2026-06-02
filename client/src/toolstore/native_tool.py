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
from typing import Dict, Any, List, Tuple, Optional

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

_index_manager: IndexManager | None = None


def _get_im() -> IndexManager:
    global _index_manager
    if _index_manager is None:
        _index_manager = IndexManager()
    return _index_manager



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
    mcp_tools: dict[str, dict] = {}
    srv_info: dict = {}
    im = _get_im(); im._load_local()
    _mcp_servers = im._local_mcp
    servers = im._local_mcp  # alias for server lookup below
    if isinstance(_mcp_servers, dict) and tool_name in _mcp_servers:
        for _tn, _ti in _mcp_servers[tool_name].get("tools", {}).items():
            if isinstance(_ti, dict):
                mcp_tools[_tn] = _ti

    # Try display_name match
    if not mcp_tools and isinstance(_mcp_servers, dict):
        for _sid, _srv in _mcp_servers.items():
            if isinstance(_srv, dict) and _srv.get("display_name") == tool_name:
                for _tn, _ti in _srv.get("tools", {}).items():
                    if isinstance(_ti, dict):
                        mcp_tools[_tn] = _ti
                if mcp_tools:
                    srv_info = _srv
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
    mcp_tools_by_server: dict[str, list[str]] = {}
    im = _get_im(); im._load_local()
    _mcp_servers2 = im._local_mcp
    if isinstance(_mcp_servers2, dict):
        for _sid, _srv in _mcp_servers2.items():
            if not isinstance(_srv, dict):
                continue
            for _tn, _ti in _srv.get("tools", {}).items():
                if isinstance(_ti, dict):
                    mcp_tools_by_server.setdefault(_sid, []).append(_tn)

    # Build display-name lookup for MCP servers
    servers = im._local_mcp
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
    im = _get_im(); im._load_local()

    names: list[str] = []
    mcp_servers: dict[str, str] = {}  # display_name → server_id

    # Toolsets
    for name, info in im._local_tools.items():
        if isinstance(info, dict) and info.get("exposure") == "secondary":
            names.append(name)

    # MCP tools → group by server (toolset mode) or list individually
    for sid, srv in im._local_mcp.items():
        if not isinstance(srv, dict):
            continue
        srv_tools = srv.get("tools", {})
        if srv.get("mode", "toolset") == "toolset":
            if srv.get("exposure", "secondary") == "secondary":
                display = srv.get("display_name") or sid
                mcp_servers[display] = sid
        else:
            for tn, ti in srv_tools.items():
                if isinstance(ti, dict) and ti.get("exposure") == "secondary":
                    names.append(tn)

    # Skills
    for sn, si in im._local_skills.items():
        if isinstance(si, dict) and si.get("exposure") == "secondary":
            names.append(f"skill:{sn}")

    # ── Also include MCP servers whose server-level exposure is secondary,
    # even if their individual tools are hidden (the agent can discover
    # tools via tool_store info when it needs the server).
    # Only applies to toolset-mode servers.
    if isinstance(im._local_mcp, dict):
        for sid, srv in im._local_mcp.items():
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




def _iter_individual_tools():
    """Iterate ``(name, info)`` for all individual MCP tools and skills.

    Reads from :class:`IndexManager` (``local_registry.json``).
    """
    im = _get_im(); im._load_local()
    # MCP tools
    for sid, srv in im._local_mcp.items():
        if not isinstance(srv, dict):
            continue
        for tn, ti in srv.get("tools", {}).items():
            if isinstance(ti, dict):
                yield tn, ti
    # Skills
    for sn, si in im._local_skills.items():
        if isinstance(si, dict):
            yield f"skill:{sn}", si


# ---------------------------------------------------------------------------
# Primary tool helpers — tools exposed directly to the LLM as native schemas
# ---------------------------------------------------------------------------

# Native AuroraCoder tool names that primary tools must NOT collide with.
_NATIVE_NAMES: set[str] = {
    "google_search", "web_browser", "read_file", "write_file",
    "edit_file", "delete_file", "close_file", "list_directory",
    "search_files", "run_terminal_command", "tool_store",
    "subagent", "continue_as_new_chat",
}


def _primary_log():
    """Lazy logger for primary-tool warnings."""
    import logging
    return logging.getLogger("toolstore.primary")


def get_primary_tool_names() -> list[str]:
    """Return function names of all primary‑exposed tools.

    For toolset‑level primary exposure every ``@tool`` function inside the
    toolset becomes a primary tool.  For individual primary tools (MCP,
    skills) the tool name itself is returned.

    Always reloads config from disk.
    """
    im = _get_im(); im._load_local()
    names: list[str] = []

    for info in im._local_tools.values():
        if not isinstance(info, dict):
            continue
        if info.get("exposure") != "primary":
            continue
        bindings = info.get("bindings", {})
        names.extend(bindings.keys())

    for t_name, t_info in _iter_individual_tools():
        if isinstance(t_info, dict) and t_info.get("exposure") == "primary":
            names.append(t_name)

    return sorted(set(names))


def get_primary_tool_schemas() -> list[dict]:
    """Get OpenAI function‑calling schemas for every primary tool.

    For toolset‑level primary exposure the toolset ``.py`` file is loaded
    and each ``@tool`` callable is converted to an OpenAI schema via
    :func:`tool_fn_to_openai`.  For individual primary tools the index
    definition is converted via :func:`toolstore_to_openai`.

    Tools whose names collide with native AuroraCoder tools are skipped
    with a warning.
    """
    im = _get_im(); im._load_local()
    schemas: list[dict] = []
    seen: set[str] = set()

    # ── 1. Primary toolsets — load .py → @tool → schema ────────────────
    toolsets = im._local_tools
    if isinstance(toolsets, dict):
        for ts_name, ts_info in toolsets.items():
            if not isinstance(ts_info, dict):
                continue
            if ts_info.get("exposure") != "primary":
                continue
            ts_dir = ts_info.get("directory", "")
            if not ts_dir:
                continue
            try:
                schemas.extend(
                    _load_primary_toolset_schemas(ts_name, ts_dir, seen)
                )
            except Exception as exc:
                _primary_log().warning(
                    "Failed to load primary toolset '%s': %s", ts_name, exc
                )

    # ── 2. Primary individual tools (MCP, skills) ──────────────────────
    for t_name, t_info in _iter_individual_tools():
        if not isinstance(t_info, dict):
            continue
        if t_info.get("exposure") != "primary":
            continue
        if t_name in _NATIVE_NAMES or t_name in seen:
            continue
        index_manager.load()
        tool_def = index_manager.get_tool(t_name)
        if tool_def:
            try:
                schema = toolstore_to_openai(tool_def)
                schemas.append(schema)
                seen.add(t_name)
            except Exception:
                pass

    return schemas


def _load_primary_toolset_schemas(
    ts_name: str, ts_dir: str, seen: set[str]
) -> list[dict]:
    """Load a primary toolset from disk and return OpenAI schemas."""
    import importlib.util
    from pathlib import Path
    from toolstore.toolset import clear_registry, get_tool_names as _gn, get_tool
    from toolstore.schema_converter import tool_fn_to_openai

    ts_file = Path(ts_dir) / "toolset.py"
    if not ts_file.exists():
        _primary_log().warning(
            "Primary toolset '%s': toolset.py not found at %s", ts_name, ts_dir
        )
        return []

    clear_registry()
    spec = importlib.util.spec_from_file_location(
        f"_primary_{ts_name}", str(ts_file)
    )
    if spec is None or spec.loader is None:
        return []
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result: list[dict] = []
    for fn_name in _gn():
        if fn_name in _NATIVE_NAMES:
            _primary_log().warning(
                "Primary tool '%s' from toolset '%s' collides with a "
                "native AuroraCoder tool — skipping",
                fn_name, ts_name,
            )
            continue
        if fn_name in seen:
            _primary_log().warning(
                "Primary tool '%s' from toolset '%s' already claimed by "
                "another toolset — skipping",
                fn_name, ts_name,
            )
            continue
        fn = get_tool(fn_name)
        if fn is None:
            continue
        schema = tool_fn_to_openai(fn)
        result.append(schema)
        seen.add(fn_name)

    clear_registry()
    return result


def get_primary_tool_prompt() -> str:
    """Build a compact text block listing primary tools for the system message.

    Groups tools by toolset and reads ``{toolset_dir}/doc.md`` for the
    full documentation body.  Function descriptions are NOT included —
    those already live in the OpenAI schemas.

    Format::

        ### calc-toolkit
        Safe expression evaluation, unit conversion, and basic statistics.
        Pure‑stdlib — no dependencies.

        - eval_expression
        - convert_unit

    Returns an empty string when no primary tools are configured.
    """
    from pathlib import Path
    from toolstore.tool import _read_doc

    im = _get_im(); im._load_local()
    blocks: list[str] = []

    toolsets = im._local_tools
    if isinstance(toolsets, dict):
        for ts_name, ts_info in toolsets.items():
            if not isinstance(ts_info, dict):
                continue
            if ts_info.get("exposure") != "primary":
                continue

            bindings = ts_info.get("bindings", {})
            fn_names = [
                fn for fn in bindings
                if fn not in _NATIVE_NAMES
            ]
            if not fn_names:
                continue

            fn_names.sort()

            # ── doc.md full body ─────────────────────────────────
            ts_dir = ts_info.get("directory", "")
            doc = ""
            if ts_dir:
                doc_path = Path(ts_dir) / "doc.md"
                doc = _read_doc(doc_path)

            parts = [f"### {ts_name}"]
            if doc:
                parts.append(doc)
            parts.extend(f"- {fn}" for fn in fn_names)
            blocks.append("\n".join(parts))

    # ── Individual primary tools (MCP, skills) ──────────────────────
    for t_name, t_info in _iter_individual_tools():
        if not isinstance(t_info, dict):
            continue
        if t_info.get("exposure") != "primary":
            continue
        if t_name in _NATIVE_NAMES:
            continue
        desc = t_info.get("description", "")
        if desc:
            blocks.append(f"- {t_name} — {desc}")
        else:
            blocks.append(f"- {t_name}")

    if not blocks:
        return ""

    return "\n".join(blocks)


def _find_primary_toolset(name: str) -> Optional[Tuple[str, dict]]:
    """Find the toolset that owns a primary tool function ``name``.

    Returns ``(toolset_name, toolset_info_dict)`` or ``None``.
    """
    im = _get_im(); im._load_local()
    toolsets = im._local_tools
    if isinstance(toolsets, dict):
        for ts_name, ts_info in toolsets.items():
            if not isinstance(ts_info, dict):
                continue
            if ts_info.get("exposure") != "primary":
                continue
            bindings = ts_info.get("bindings", {})
            if name in bindings:
                return (ts_name, ts_info)
    return None


def execute_tool_direct(name: str, kwargs: dict) -> str:
    """Execute a primary tool by function name — no ``tool_store`` dispatch.

    Looks up the function in primary toolsets' bindings; falls back to the
    standard ``_do_execute`` path for individual tools (MCP, skills).

    The LLM calls primary tools directly (e.g. ``calculator("1+2")``) —
    this is the entry point that routes those calls to the right backend.
    """
    # 1. Toolset-level primary: find which toolset owns this function
    found = _find_primary_toolset(name)
    if found is not None:
        ts_name, ts_info = found
        tool = {
            "name": ts_name,
            "type": "toolset",
            "bindings": ts_info.get("bindings", {}),
            "toolset_dir": ts_info.get("directory", ""),
            "code": ts_info.get("code", ""),
            "code_base64": ts_info.get("code_base64", ""),
            "requirements": ts_info.get("requirements", []),
        }
        if "function" not in kwargs:
            kwargs = dict(kwargs)
            kwargs["function"] = name
        return _execute_toolset_inline(tool, kwargs)

    # 2. Individual primary tools (MCP, skills) — standard dispatch
    return _do_execute(name, kwargs)


def prefetch_primary_tools() -> int:
    """Eager‑load all primary toolsets and cache their schemas.

    Called once at agent startup.  Returns the number of primary tools
    found.  Logs warnings for toolsets that fail to load or whose
    function names collide with native tools.
    """
    return len(get_primary_tool_schemas())


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

    # ── polymorphic dispatch via the Tool class hierarchy ────────────
    from toolstore.tool import Tool
    try:
        t = Tool.from_dict(tool)
        return t.execute(**args)
    except ValueError:
        pass

    # ── edge‑case fallbacks (should rarely trigger) ────────────────
    if tool_type == "toolset":
        return _execute_toolset_inline(tool, args)
    if tool_type == "mcp_toolset":
        return _execute_mcp_toolset(tool, args)
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
    im = _get_im(); im._load_local()
    servers = im._local_mcp
    if not isinstance(servers, dict):
        return None

    # Build server-id → (display_name, tools) lookup
    server_map: Dict[str, tuple] = {}

    for sid, srv in servers.items():
        if not isinstance(srv, dict):
            continue
        display = srv.get("display_name") or sid
        server_tools: Dict[str, dict] = srv.get("tools", {})
        if server_tools:
            server_map[sid] = (display, server_tools)
            server_map[display] = (display, server_tools)

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
    """Execute an MCP tool resolved from toolset mode."""
    from toolstore.exec_tools import _execute_mcp
    from toolstore.index_manager import IndexManager

    function_name = args.get("function")
    if not function_name:
        return "Error: 'function' argument required. Specify which MCP tool to call."

    im = IndexManager()
    im._load_local()
    return _execute_mcp(tool, args, im)


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

