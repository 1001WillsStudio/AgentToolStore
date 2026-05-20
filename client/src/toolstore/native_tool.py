"""
ToolStore native tool — the Python entry point that AuroraCoder (and other agents)
call to search, inspect, and execute ToolStore tools.

Supports three tool types:
- api:  HTTP GET/POST to public APIs
- mcp:  Full MCP protocol via persistent connection pool
- skill: SKILL.md-based agent skills (load, list files, read file)
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
                    ttype = tool.get("type", "api")
                    desc = tool.get("description", "No description")
                    if len(desc) > 100:
                        desc = desc[:100].rstrip() + "..."
                    return f"- {tool['name']} ({ttype}): {desc}"
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
        ttype = tool.get("type", "api")
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


def _do_secondary_prompt(tool_names: List[str],
                         max_desc_len: int = 100) -> str:
    """Return a compact prompt listing tool names, types, and descriptions.

    The output is plain text suitable for embedding in an agent's system
    prompt to communicate available secondary tools without consuming the
    context tokens that full JSON schemas would require.

    Descriptions longer than *max_desc_len* are truncated with an ellipsis
    to keep the prompt footprint small.
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
        ttype = tool.get("type", "api")
        desc = tool.get("description", "No description")
        if len(desc) > max_desc_len:
            desc = desc[:max_desc_len].rstrip() + "..."
        lines.append(f"- {tool['name']} ({ttype}): {desc}")
    return "\n".join(lines)


def _do_execute(tool_name: str, args: Dict[str, Any]) -> str:
    if not tool_name:
        return "Error: 'tool_name' argument is required for execute action."

    tool = index_manager.get_tool(tool_name)
    if not tool:
        return f"Error: Tool '{tool_name}' not found."

    tool_type = tool.get("type", "api")

    if tool_type == "api":
        return _execute_api(tool, args)
    elif tool_type == "mcp":
        return _execute_mcp(tool, args)
    elif tool_type == "skill":
        return _execute_skill(tool, args)
    elif tool_type == "docker":
        return _execute_docker(tool, args)
    else:
        return f"Error: Unknown tool type '{tool_type}'"

# ---------------------------------------------------------------------------
# API execution
# ---------------------------------------------------------------------------

def _execute_api(tool: Dict[str, Any], args: Dict[str, Any]) -> str:
    import httpx

    url = tool["endpoint"]
    method = tool.get("method", "GET").upper()

    # Path-parameter substitution
    final_url = url
    for k, v in args.items():
        if f"{{{k}}}" in final_url:
            final_url = final_url.replace(f"{{{k}}}", str(v))

    # Remaining params become query/body
    request_params = {k: v for k, v in args.items()
                      if f"{{{k}}}" not in url}

    try:
        if method == "GET":
            response = httpx.get(final_url, params=request_params, timeout=30.0)
        else:
            response = httpx.request(method, final_url,
                                     json=request_params, timeout=30.0)
        try:
            return json.dumps(response.json(), indent=2)
        except Exception:
            return response.text
    except Exception as req_err:
        return f"Error executing API tool: {str(req_err)}"


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
# Docker execution  (single shared warm worker — same container for all tools)
# ---------------------------------------------------------------------------

def _execute_docker(tool: Dict[str, Any], args: Dict[str, Any]) -> str:
    """Run a *docker*-type tool in the single shared warm worker.

    The module code is loaded once (keyed by a hash of the code string) and
    the named function is called with the provided arguments.  Multiple tools
    that share the same code module reuse the same loaded namespace.
    """
    import base64
    import hashlib
    from toolstore import docker_pool

    # 1. Check Docker availability
    docker_err = docker_pool.check_docker_available()
    if docker_err:
        return f"Error: {docker_err}"

    # 1b. DinD socket check
    socket_err = docker_pool.dind_socket_check()
    if socket_err:
        return socket_err

    # 2. Decode the code
    code = tool.get("code") or ""
    if tool.get("code_base64"):
        try:
            code = base64.b64decode(tool["code_base64"]).decode("utf-8")
        except Exception as exc:
            return f"Error: Failed to decode base64 code: {exc}"

    if not code.strip():
        return "Error: Docker tool has no code to execute."

    # 3. Derive a stable module name from the code hash so that tools
    #    that share identical code reuse the loaded namespace.
    module_name = "m_" + hashlib.sha256(code.encode()).hexdigest()[:12]

    # 4. The function to call — either declared in the tool definition or
    #    defaults to "main" by convention.
    function = tool.get("function", "main")

    # 5. Load the module (no-op if already loaded) and call the function.
    timeout_s = tool.get("timeout", 30)
    worker = docker_pool.get_worker()

    load_err = worker.load_module(module_name, code)
    if load_err:
        return f"Error loading module: {load_err}"

    return worker.call_function(module_name, function, args, timeout_s)

