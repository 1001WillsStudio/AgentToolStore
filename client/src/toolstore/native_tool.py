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
    flatten_mcp_content,
    toolstore_to_openai,
)
from toolstore.skill_manager import get_skill_manager

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
    for name in tool_names:
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

    This is the canonical way for agent frameworks to discover which
    secondary tools should be listed in the system prompt without having
    to search first.
    """
    names: list[str] = []

    toolsets = config_manager.config.get("toolsets", {})
    if isinstance(toolsets, dict):
        for name, info in toolsets.items():
            if isinstance(info, dict) and info.get("exposure") == "secondary":
                names.append(name)

    tools = config_manager.config.get("tools", {})
    if isinstance(tools, dict):
        for name, info in tools.items():
            if isinstance(info, dict) and info.get("exposure") == "secondary":
                names.append(name)

    return names
def _do_execute(tool_name: str, args: Dict[str, Any]) -> str:
    if not tool_name:
        return "Error: 'tool_name' argument is required for execute action."

    tool = index_manager.get_tool(tool_name)
    if not tool:
        return f"Error: Tool '{tool_name}' not found."

    tool_type = tool.get("type", "unknown")

    if tool_type == "mcp":
        return _execute_mcp(tool, args)
    elif tool_type == "skill":
        return _execute_skill(tool, args)
    elif tool_type == "toolset":
        return _execute_toolset(tool, args)
    else:
        return f"Error: Unknown tool type '{tool_type}'"

# ---------------------------------------------------------------------------
# MCP execution (via FullMCPClient + connection pool)
# ---------------------------------------------------------------------------

def _execute_mcp(tool: Dict[str, Any], args: Dict[str, Any]) -> str:
    from toolstore.mcp_client import get_client

    server_name = tool.get("mcp_server")
    if not server_name:
        return "Error: Tool definition missing 'mcp_server'"

    servers = config_manager.get_mcp_servers()
    config = servers.get(server_name)
    if not config:
        return f"Error: MCP server '{server_name}' not found in config."

    try:
        client = get_client(server_name, config)
        result = client.call_tool(tool["name"], args)
        content = result.get("content", [])
        if result.get("isError"):
            return "[TOOL ERROR] " + flatten_mcp_content(content)
        return flatten_mcp_content(content)
    except Exception as exc:
        return f"Error executing MCP tool: {str(exc)}"


# ---------------------------------------------------------------------------
# Skill execution
# ---------------------------------------------------------------------------

def _execute_skill(tool: Dict[str, Any], args: Dict[str, Any]) -> str:
    skill_name = tool["name"]
    skill_action = args.get("action", "load")

    sm = get_skill_manager(config_manager.get_skill_dirs())
    # Lazily scan if not already loaded
    if not sm.get_skill(skill_name):
        sm.scan()

    if skill_action == "load":
        body = sm.get_skill_body(skill_name)
        if body is None:
            return f"Error: Skill '{skill_name}' not loaded."
        return body

    elif skill_action == "files":
        sd = sm.get_skill(skill_name)
        if not sd:
            return f"Error: Skill '{skill_name}' not found."
        flist = [str(f) for f in sd.list_files()]
        return "\n".join(flist) if flist else "(no additional files bundled)"

    elif skill_action == "file":
        file_path = args.get("file_path", "")
        if not file_path:
            return "Error: 'file_path' is required for action='file'."
        content = sm.get_skill_file(skill_name, file_path)
        if content is None:
            return f"Error: File '{file_path}' not found in skill '{skill_name}'."
        return content

    elif skill_action == "run":
        script = args.get("script", "")
        if not script:
            return "Error: 'script' argument is required for action='run'."
        return sm.run_skill_script(skill_name, script)

    else:
        return f"Error: Unknown skill action '{skill_action}'. Use 'load', 'files', or 'file'."


# ---------------------------------------------------------------------------
# Toolset execution
# ---------------------------------------------------------------------------

def _execute_toolset(tool: Dict[str, Any], args: Dict[str, Any]) -> str:
    """Execute a toolset.

    Two modes:
    - **Local** (has ``toolset_dir``): import + call directly in-process.
      No Docker, no sandbox — the toolset is installed on the host.
    - **Remote** (has ``code``, no ``toolset_dir``): run in a dedicated
      ephemeral Docker container with the toolset's pre-configured
      environment.  Zero approval required.

    The agent passes ``{"function": "...", ...}`` in arguments.
    """
    # Take a copy so we don't mutate the caller's dict.
    args = dict(args)

    # 1. Argument validation — which function?
    function_name = args.pop("function", None)
    if not function_name:
        bindings = tool.get("bindings", {})
        if len(bindings) == 1:
            function_name = next(iter(bindings))
        else:
            names = list(bindings.keys()) if bindings else []
            return (
                f"Error: 'function' argument required. "
                f"Available functions: {', '.join(names) or '(none)'}"
            )

    # 2. Validate the binding exists
    bindings = tool.get("bindings", {})
    if function_name not in bindings:
        names = list(bindings.keys())
        return (
            f"Error: Unknown function '{function_name}'. "
            f"Available: {', '.join(names)}"
        )

    # 3. Dispatch: local (in-process) vs remote (dedicated container)
    toolset_dir = tool.get("toolset_dir")
    if toolset_dir:
        return _execute_toolset_local(toolset_dir, function_name, args)

    code = tool.get("code") or tool.get("code_base64")
    if code:
        return _execute_toolset_remote(tool, function_name, args)

    return "Error: toolset has neither 'toolset_dir' nor 'code' — cannot execute"


def _execute_toolset_local(toolset_dir: str, function_name: str,
                           args: Dict[str, Any]) -> str:
    """Run a local toolset directly in-process — just import and call."""
    import importlib.util
    from pathlib import Path

    from toolstore.toolset import clear_registry, get_tool

    code_path = Path(toolset_dir) / "toolset.py"
    if not code_path.exists():
        return f"Error: toolset.py not found at {code_path}"

    try:
        clear_registry()

        # Dynamically load the toolset module
        spec = importlib.util.spec_from_file_location(
            "toolset_local", str(code_path)
        )
        if spec is None or spec.loader is None:
            return "Error: failed to create module spec for toolset.py"

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        fn = get_tool(function_name)
        if fn is None:
            from toolstore.toolset import get_tool_names
            names = get_tool_names()
            return (
                f"Error: Function '{function_name}' not found in toolset. "
                f"Available: {', '.join(names) or '(none)'}"
            )

        result = fn(**args)
        clear_registry()

        import json as _json
        return _json.dumps(result, default=str, indent=2)
    except Exception as exc:
        clear_registry()
        return f"Error executing local toolset '{function_name}': {exc}"


def _execute_toolset_remote(tool: Dict[str, Any], function_name: str,
                            args: Dict[str, Any]) -> str:
    """Run a remote (registry) toolset in a dedicated ephemeral Docker
    container with its pre-configured environment."""
    from toolstore.remote_runner import RemoteRunner

    runner = RemoteRunner(tool)
    return runner.run(function_name, args, tool.get("timeout", 30))

