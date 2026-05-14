"""
ToolStore as an MCP server.

Exposes all indexed tools (api, mcp, skill) as MCP tools/resources/prompts
so any MCP-compatible host (Claude Desktop, VS Code, etc.) can connect and
use the entire ToolStore catalog.

Implements the full MCP server feature set:
- tools/list, tools/call
- resources/list, resources/read
- prompts/list, prompts/get
- notifications for list changes

Supports stdio transport natively, plus a FastAPI integration for SSE.
"""

from __future__ import annotations

import json
import sys
import threading
from typing import Dict, List, Any, Optional, Callable

from toolstore.schema_converter import (
    toolstore_to_mcp, flatten_mcp_content, bulk_to_openai
)
from toolstore.skill_manager import get_skill_manager


# ---------------------------------------------------------------------------
# ToolStore MCP Server (protocol logic only — transport agnostic)
# ---------------------------------------------------------------------------

class ToolStoreMCPServer:
    """Protocol handler for ToolStore-as-MCP-server.

    This is transport-agnostic. Hook it up to stdio or an SSE endpoint.
    """

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "toolstore"
    SERVER_VERSION = "2.0.0"

    def __init__(self, index_manager, config_manager, skill_manager=None):
        self._index = index_manager
        self._config = config_manager
        self._skills = skill_manager or get_skill_manager()
        self._request_id = 0
        self._lock = threading.Lock()
        self._on_send: Optional[Callable[[Dict[str, Any]], None]] = None
        # Track whether capabilities were declared
        self._declared_caps: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Transport hook
    # ------------------------------------------------------------------

    def set_send_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register the function used to send messages back to the client."""
        self._on_send = callback

    def handle_message(self, raw: Dict[str, Any]) -> None:
        """Process an incoming JSON-RPC message from the client."""
        method = raw.get("method")
        rid = raw.get("id")
        params = raw.get("params", {})

        # Notification (no id)
        if rid is None:
            self._handle_notification(method, params)
            return

        # Request
        try:
            result = self._dispatch(method, params)
            self._send({"jsonrpc": "2.0", "id": rid, "result": result})
        except Exception as exc:
            self._send({
                "jsonrpc": "2.0", "id": rid,
                "error": {"code": -32603, "message": str(exc)},
            })

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, method: str, params: Any) -> Any:
        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
        }
        handler = handlers.get(method)
        if handler is None:
            raise RuntimeError(f"Unknown method: {method}")
        return handler(params)

    def _handle_notification(self, method: str, params: Any) -> None:
        if method == "notifications/initialized":
            pass  # client is ready
        # Silently ignore others

    # ------------------------------------------------------------------
    # initialize
    # ------------------------------------------------------------------

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._declared_caps = {
            "tools": {"listChanged": True},
            "resources": {"listChanged": False},
            "prompts": {"listChanged": False},
        }
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": self._declared_caps,
            "serverInfo": {
                "name": self.SERVER_NAME,
                "version": self.SERVER_VERSION,
            },
        }

    # ------------------------------------------------------------------
    # tools/list
    # ------------------------------------------------------------------

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return all indexed tools in MCP format."""
        tools = []
        all_tools = self._index.index_data.get("tools", {})
        for _name, tool_def in all_tools.items():
            tools.append(toolstore_to_mcp(tool_def))
        # Also include live MCP-scanned tools not yet in index? For now,
        # only indexed tools are exposed.
        return {"tools": tools}

    # ------------------------------------------------------------------
    # tools/call
    # ------------------------------------------------------------------

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = params["name"]
        arguments = params.get("arguments", {})

        tool_def = self._index.get_tool(tool_name)
        if not tool_def:
            return {
                "content": [{"type": "text", "text": f"Tool '{tool_name}' not found"}],
                "isError": True,
            }

        # Dispatch by type
        tool_type = tool_def.get("type", "api")
        try:
            if tool_type == "skill":
                return self._execute_skill(tool_def, arguments)
            elif tool_type == "api":
                return self._execute_api(tool_def, arguments)
            elif tool_type == "mcp":
                return self._execute_mcp(tool_def, arguments)
            else:
                return {
                    "content": [{"type": "text",
                                 "text": f"Unknown tool type: {tool_type}"}],
                    "isError": True,
                }
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            }

    def _execute_api(self, tool_def: Dict[str, Any],
                     args: Dict[str, Any]) -> Dict[str, Any]:
        import httpx
        url = tool_def["endpoint"]
        method = tool_def.get("method", "GET").upper()
        # Path param substitution
        final_url = url
        for k, v in args.items():
            if f"{{{k}}}" in final_url:
                final_url = final_url.replace(f"{{{k}}}", str(v))
        request_params = {k: v for k, v in args.items()
                          if f"{{{k}}}" not in url}
        if method == "GET":
            resp = httpx.get(final_url, params=request_params, timeout=30.0)
        else:
            resp = httpx.request(method, final_url, json=request_params,
                                 timeout=30.0)
        try:
            body = json.dumps(resp.json(), indent=2)
        except Exception:
            body = resp.text
        return {"content": [{"type": "text", "text": body}]}

    def _execute_mcp(self, tool_def: Dict[str, Any],
                     args: Dict[str, Any]) -> Dict[str, Any]:
        from toolstore.mcp_client import get_client
        server_name = tool_def.get("mcp_server")
        if not server_name:
            return {"content": [{"type": "text",
                                 "text": "Tool missing mcp_server"}],
                    "isError": True}
        servers = self._config.get_mcp_servers()
        config = servers.get(server_name)
        if not config:
            return {"content": [{"type": "text",
                                 "text": f"MCP server '{server_name}' "
                                         "not configured"}],
                    "isError": True}
        client = get_client(server_name, config)
        result = client.call_tool(tool_def["name"], args)
        return result  # already has 'content' and 'isError'

    def _execute_skill(self, tool_def: Dict[str, Any],
                       args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a skill tool. Args: action (load/files/file), file_path?"""
        action = args.get("action", "load")
        skill_name = tool_def["name"]

        if action == "load":
            body = self._skills.get_skill_body(skill_name)
            if body is None:
                return {"content": [{"type": "text",
                                     "text": f"Skill '{skill_name}' not loaded"}],
                        "isError": True}
            return {"content": [{"type": "text", "text": body}]}

        elif action == "files":
            sd = self._skills.get_skill(skill_name)
            if not sd:
                return {"content": [{"type": "text",
                                     "text": f"Skill '{skill_name}' not found"}],
                        "isError": True}
            flist = [str(f) for f in sd.list_files()]
            return {"content": [{"type": "text",
                                 "text": "\n".join(flist) or "(no extra files)"}]}

        elif action == "file":
            file_path = args.get("file_path", "")
            if not file_path:
                return {"content": [{"type": "text",
                                     "text": "file_path is required for "
                                             "action='file'"}],
                        "isError": True}
            content = self._skills.get_skill_file(skill_name, file_path)
            if content is None:
                return {"content": [{"type": "text",
                                     "text": f"File '{file_path}' not found "
                                             f"in skill '{skill_name}'"}],
                        "isError": True}
            return {"content": [{"type": "text", "text": content}]}

        else:
            return {"content": [{"type": "text",
                                 "text": f"Unknown action: {action}"}],
                    "isError": True}

    # ------------------------------------------------------------------
    # resources/list
    # ------------------------------------------------------------------

    def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Expose skill SKILL.md files as resources."""
        resources = []
        for name, sd in self._skills._skills.items():
            resources.append({
                "uri": f"skill://{name}/SKILL.md",
                "name": f"Skill: {name}",
                "description": sd.description,
                "mimeType": "text/markdown",
            })
        return {"resources": resources}

    # ------------------------------------------------------------------
    # resources/read
    # ------------------------------------------------------------------

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uri = params["uri"]
        # Parse skill:// URIs
        if uri.startswith("skill://") and uri.endswith("/SKILL.md"):
            name = uri[len("skill://"):-len("/SKILL.md")]
            body = self._skills.get_skill_body(name)
            if body is not None:
                return {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "text/markdown",
                        "text": body,
                    }],
                }
        # Fallback: read raw from any indexed tool's schema
        for tname, tool_def in self._index.index_data.get("tools", {}).items():
            if uri == f"tool://{tname}":
                return {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(tool_def, indent=2),
                    }],
                }
        raise RuntimeError(f"Resource not found: {uri}")

    # ------------------------------------------------------------------
    # prompts/list
    # ------------------------------------------------------------------

    def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Expose each loaded skill's body as an available prompt."""
        prompts = []
        for name, sd in self._skills._skills.items():
            prompts.append({
                "name": name,
                "description": sd.description or f"Skill: {name}",
                "arguments": [],
            })
        return {"prompts": prompts}

    # ------------------------------------------------------------------
    # prompts/get
    # ------------------------------------------------------------------

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params["name"]
        body = self._skills.get_skill_body(name)
        if body is None:
            raise RuntimeError(f"Prompt not found: {name}")
        return {
            "description": f"Skill instructions for {name}",
            "messages": [
                {"role": "user", "content": {"type": "text", "text": body}},
            ],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _send(self, message: Dict[str, Any]) -> None:
        if self._on_send:
            self._on_send(message)

    # ------------------------------------------------------------------
    # Stdio runner (for standalone mode)
    # ------------------------------------------------------------------

    def run_stdio(self) -> None:
        """Run the server on stdin/stdout (e.g. for Claude Desktop)."""
        self.set_send_callback(
            lambda msg: sys.stdout.write(json.dumps(msg) + "\n")
        )
        # Debug logging to stderr
        print(f"ToolStore MCP Server v{self.SERVER_VERSION} ready",
              file=sys.stderr)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            self.handle_message(msg)
            sys.stdout.flush()
