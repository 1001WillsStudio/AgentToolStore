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
# Docker execution (run executable code in an isolated container)
# ---------------------------------------------------------------------------

# Path used inside the container for the entrypoint script.
_CONTAINER_SCRIPT = "/toolstore_entry.py"


def _check_docker_available() -> str | None:
    """Return ``None`` if Docker is usable, otherwise an error message."""
    import shutil
    if shutil.which("docker") is None:
        return "Docker is not installed or not on PATH."

    import subprocess
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return "Docker daemon is unresponsive (timeout)."
    except FileNotFoundError:
        return "Docker CLI not found."
    except Exception as exc:
        return f"Cannot communicate with Docker daemon: {exc}"

    return None  # OK


def _resolve_docker_image(tool: Dict[str, Any]) -> tuple[str, bool]:
    """Determine the Docker image for a tool.

    Returns:
        ``(image, is_custom)`` — *is_custom* is ``True`` when the tool
        specifies its own ``docker_image`` (rather than falling back to
        the user-configured default).
    """
    custom = tool.get("docker_image")
    if custom:
        return custom, True
    return config_manager.get_default_docker_image(), False


def _check_approval(image: str, is_custom: bool) -> str | None:
    """Validate *image* against the user's Docker-approval policy.

    Returns ``None`` if the image is allowed, or an error message otherwise.
    """
    # The default image is always allowed (no custom Docker).
    if not is_custom:
        return None

    mode = config_manager.get_docker_approval_mode()
    if mode == "all":
        return None  # everything is allowed

    if mode == "none":
        return (
            f"Docker image '{image}' is not allowed. "
            f"Custom Docker images are blocked by your approval mode (currently 'none'). "
            f"Use 'toolstore docker mode list' or 'toolstore docker mode all' to relax this."
        )

    # mode == "list"
    approved = config_manager.get_approved_docker_images()
    if image in approved:
        return None

    return (
        f"Docker image '{image}' is not in your approved list. "
        f"Use 'toolstore docker approve {image}' to add it, "
        f"or 'toolstore docker mode all' to allow any image."
    )


def _execute_docker(tool: Dict[str, Any], args: Dict[str, Any]) -> str:
    """Run a *docker*-type tool inside a container."""
    import base64
    import subprocess
    import tempfile
    from pathlib import Path

    # 1. Check Docker availability
    docker_err = _check_docker_available()
    if docker_err:
        return f"Error: {docker_err}"

    # 2. Decode the code
    code = tool.get("code") or ""
    if tool.get("code_base64"):
        try:
            code = base64.b64decode(tool["code_base64"]).decode("utf-8")
        except Exception as exc:
            return f"Error: Failed to decode base64 code: {exc}"

    if not code.strip():
        return "Error: Docker tool has no code to execute."

    # 3. Resolve the image and check approval
    image, is_custom = _resolve_docker_image(tool)
    approval_err = _check_approval(image, is_custom)
    if approval_err:
        return f"Error: {approval_err}"

    # 4. Build the entrypoint script
    #    Serialise *args* as a JSON string injected into the script so the
    #    user code can access it via ``TOOLSTORE_ARGS`` / ``toolstore_args``.
    import json as _json
    args_json = _json.dumps(args)
    script = (
        "# Auto-generated entrypoint for ToolStore docker-type tool\n"
        "import json as _ts_json\n"
        f"_ts_raw_args = {args_json!r}\n"
        "toolstore_args = _ts_json.loads(_ts_raw_args)\n"
        "TOOLSTORE_ARGS = toolstore_args  # convenience alias\n"
        "del _ts_json, _ts_raw_args\n"
        + code
    )

    # 5. Write the script to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix="toolstore_", delete=False,
        encoding="utf-8",
    ) as tf:
        tf.write(script)
        host_script = tf.name

    # 6. Run the container
    timeout_s = tool.get("timeout", 30)
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--cpus", "1",
        "--memory", "256m",
        "-v", f"{host_script}:{_CONTAINER_SCRIPT}:ro",
        image,
        "python", _CONTAINER_SCRIPT,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout_s + 5,  # slight extra for docker overhead
        )
        out = proc.stdout
        if proc.returncode != 0:
            out += f"\n[exit code: {proc.returncode}]"
        if proc.stderr:
            out += f"\n[stderr]\n{proc.stderr}"
        return out.strip() or "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: Docker execution timed out after {timeout_s}s."
    except Exception as exc:
        return f"Error during Docker execution: {exc}"
    finally:
        # Clean up temp file
        try:
            Path(host_script).unlink(missing_ok=True)
        except Exception:
            pass
