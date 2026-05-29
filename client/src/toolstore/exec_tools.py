"""
Execution dispatching for ToolStore tools.

Routes execute calls to the appropriate backend:
- MCP  → FullMCPClient (connection pool)
- Skill → SkillManager (local SKILL.md execution)
- Toolset → local import + call, or remote Docker container
"""

from __future__ import annotations

import json as _json
from typing import Any, Dict

from toolstore.schema_converter import flatten_mcp_content
from toolstore.skill_manager import get_skill_manager


def execute_tool(tool: Dict[str, Any], args: Dict[str, Any],
                 config_manager, index_manager) -> str:
    """Dispatch a single tool execution to the correct backend.

    Returns the result as a JSON or plain-text string.
    """
    tool_name = tool["name"]
    tool_type = tool.get("type", "unknown")

    if tool_type == "mcp":
        return _execute_mcp(tool, args, config_manager)
    elif tool_type == "skill":
        return _execute_skill(tool, args, config_manager)
    elif tool_type == "toolset":
        return _execute_toolset(tool, args)
    else:
        return f"Error: Unknown tool type '{tool_type}'"


# ---------------------------------------------------------------------------
# MCP execution (via FullMCPClient + connection pool)
# ---------------------------------------------------------------------------

def _execute_mcp(tool: Dict[str, Any], args: Dict[str, Any],
                 config_manager) -> str:
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

def _execute_skill(tool: Dict[str, Any], args: Dict[str, Any],
                   config_manager) -> str:
    # Strip "skill:" prefix if present (index uses prefixed names)
    skill_name = tool["name"]
    if skill_name.startswith("skill:"):
        skill_name = skill_name[len("skill:"):]
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

        return _json.dumps(result, default=str, indent=2)
    except Exception as exc:
        clear_registry()
        return f"Error executing local toolset '{function_name}': {exc}"


def _execute_toolset_remote(tool: Dict[str, Any], function_name: str,
                            args: Dict[str, Any]) -> str:
    """Run a registry toolset in-process — no Docker needed.

    Writes code to a temp directory, pip‑installs deps, then imports
    and calls the function just like _execute_toolset_local.
    """
    import base64
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    code = tool.get("code", "")
    code_b64 = tool.get("code_base64", "")
    if code_b64 and not code:
        code = base64.b64decode(code_b64).decode("utf-8")

    if not code:
        return "Error: toolset has no code to execute"

    # Temp directory — lives for the duration of the function call
    with tempfile.TemporaryDirectory(prefix="toolset_") as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "toolset.py").write_text(code, encoding="utf-8")

        # Install requirements if present
        requirements = tool.get("requirements", [])
        if isinstance(requirements, str):
            requirements = [r.strip() for r in requirements.split("\n") if r.strip()]
        if requirements:
            return (
                f"Error: This toolset requires packages that aren't installed: "
                f"{', '.join(requirements)}.\n"
                f"Install them first: pip install {' '.join(requirements)}"
            )

        # Now delegate to the local runner
        return _execute_toolset_local(str(tmp), function_name, args)
