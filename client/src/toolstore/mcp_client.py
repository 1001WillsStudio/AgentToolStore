"""
Full MCP client with transport abstraction.

Supports:
- Protocol: initialize, tools/list, tools/call, resources/list, resources/read,
  prompts/list, prompts/get
- Transports: stdio + HTTP/SSE (via transport.py)
- Persistent connections with connection pooling
- Full content type handling (text, image, resource)
- Notifications: tools/list_changed, resources/list_changed, prompts/list_changed
- Thread-safe: shared message queue between listener and callers
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Dict, Any, Optional

from toolstore.transport import create_transport, MCPTransport
from toolstore.schema_converter import flatten_mcp_content

logger = logging.getLogger(__name__)


class FullMCPClient:
    """A complete MCP client that speaks the full protocol over any transport.

    Usage::

        config = {"command": "npx", "args": ["-y", "@acme/server"]}
        client = FullMCPClient("my-server", config)
        client.connect()

        tools = client.list_tools()
        result = client.call_tool("get_weather", {"city": "Tokyo"})

        resources = client.list_resources()
        prompts = client.list_prompts()

        client.disconnect()
    """

    def __init__(self, server_name: str, config: Dict[str, Any]):
        self.server_name = server_name
        self.config = config
        self._transport: Optional[MCPTransport] = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._capabilities: Dict[str, Any] = {}
        self._instructions: str = ""
        self._connected = False
        # Shared message queue — listener pushes, _call pops
        self._msg_queue: queue.Queue = queue.Queue()
        # Background notification handler state
        self._listener_thread: Optional[threading.Thread] = None
        self._listener_running = False
        self._notification_callbacks: Dict[str, list] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Create transport, perform MCP handshake, start notification listener."""
        if self._connected:
            return
        self._transport = create_transport(self.config)
        self._transport.start()
        self._handshake()
        self._connected = True
        self._start_listener()

    def disconnect(self) -> None:
        """Close transport and stop listener."""
        self._listener_running = False
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=3)
        if self._transport:
            self._transport.close()
            self._transport = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._transport is not None

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

    def _handshake(self) -> None:
        init_result = self._call_direct("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"listChanged": True, "subscribe": True},
                "prompts": {"listChanged": True},
            },
            "clientInfo": {"name": "toolstore", "version": "2.0.0"},
        })
        self._capabilities = init_result.get("capabilities", {})
        # The server's ``instructions`` field carries the human/agent-readable
        # description of what the server is for.  It is the canonical source
        # for the description surfaced to the agent — written by the server
        # author, not auto-generated.
        self._instructions = init_result.get("instructions", "") or ""
        self._send_notification("notifications/initialized")

    def get_instructions(self) -> str:
        """Return the server description from the MCP handshake.

        This is the text the server author put in ``initialize().instructions``
        — the authoritative description surfaced to the agent.
        """
        return self._instructions

    # ------------------------------------------------------------------
    # JSON-RPC primitives
    # ------------------------------------------------------------------

    def _call_direct(self, method: str, params: Any = None) -> Any:
        """Send request and read response DIRECTLY from transport (used
        during handshake, before the listener thread starts)."""
        with self._lock:
            self._request_id += 1
            rid = self._request_id
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        self._transport.send(msg)
        while True:
            resp = self._transport.receive()
            if resp.get("id") == rid:
                if "error" in resp:
                    err = resp["error"]
                    raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
                return resp.get("result")

    def _call(self, method: str, params: Any = None) -> Any:
        """Send request and wait for response via the shared message queue.
        Used for all calls after the listener thread is active."""
        with self._lock:
            self._request_id += 1
            rid = self._request_id
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        self._transport.send(msg)
        while True:
            try:
                resp = self._msg_queue.get(timeout=60)
            except queue.Empty:
                raise RuntimeError("Timeout waiting for MCP response")
            if resp.get("id") == rid:
                if "error" in resp:
                    err = resp["error"]
                    raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
                return resp.get("result")
            elif "method" in resp and "id" not in resp:
                # Notification — dispatch and continue waiting
                method_name = resp["method"]
                callbacks = self._notification_callbacks.get(method_name, [])
                params = resp.get("params")
                for cb in callbacks:
                    try:
                        cb(method_name, params)
                    except Exception:
                        logger.debug("Notification callback error", exc_info=True)
            # else: stale response for another caller — discard

    def _send_notification(self, method: str, params: Any = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._transport.send(msg)

    # ------------------------------------------------------------------
    # Notification listener (background thread)
    # ------------------------------------------------------------------

    def _start_listener(self) -> None:
        """Start a background thread that reads ALL messages from the
        transport and pushes them into the shared queue.  _call consumes
        from the queue, so there is no race."""
        self._listener_running = True
        self._listener_thread = threading.Thread(
            target=self._listen, daemon=True)
        self._listener_thread.start()

    def _listen(self) -> None:
        while self._listener_running and self._transport:
            try:
                msg = self._transport.receive()
            except Exception:
                logger.debug("Transport receive error in listener", exc_info=True)
                if self._listener_running:
                    continue
                break
            self._msg_queue.put(msg)

    def on_notification(self, method: str, callback) -> None:
        """Register a callback for incoming notifications."""
        self._notification_callbacks.setdefault(method, []).append(callback)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def list_tools(self, cursor: str = None) -> Dict[str, Any]:
        params = {}
        if cursor:
            params["cursor"] = cursor
        return self._call("tools/list", params or None)

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._call("tools/call", {"name": name, "arguments": arguments})

    def call_tool_text(self, name: str, arguments: Dict[str, Any]) -> str:
        result = self.call_tool(name, arguments)
        content = result.get("content", [])
        prefix = "[TOOL ERROR] " if result.get("isError") else ""
        return prefix + flatten_mcp_content(content)

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------

    def list_resources(self, cursor: str = None) -> Dict[str, Any]:
        params = {}
        if cursor:
            params["cursor"] = cursor
        return self._call("resources/list", params or None)

    def read_resource(self, uri: str) -> Dict[str, Any]:
        return self._call("resources/read", {"uri": uri})

    def list_resource_templates(self, cursor: str = None) -> Dict[str, Any]:
        params = {}
        if cursor:
            params["cursor"] = cursor
        return self._call("resources/templates/list", params or None)

    def subscribe_resource(self, uri: str) -> None:
        self._call("resources/subscribe", {"uri": uri})

    def unsubscribe_resource(self, uri: str) -> None:
        self._call("resources/unsubscribe", {"uri": uri})

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    def list_prompts(self, cursor: str = None) -> Dict[str, Any]:
        params = {}
        if cursor:
            params["cursor"] = cursor
        return self._call("prompts/list", params or None)

    def get_prompt(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"name": name}
        if arguments:
            params["arguments"] = arguments
        return self._call("prompts/get", params)

    # ------------------------------------------------------------------
    # Convenience: scan everything
    # ------------------------------------------------------------------

    def scan_all(self) -> Dict[str, Any]:
        """Return a snapshot of the server: tools, resources, prompts."""
        result: Dict[str, Any] = {}
        caps = self._capabilities

        if "tools" in caps:
            result["tools"] = self.list_tools().get("tools", [])
        if "resources" in caps:
            result["resources"] = self.list_resources().get("resources", [])
        if "prompts" in caps:
            result["prompts"] = self.list_prompts().get("prompts", [])

        return result


# ------------------------------------------------------------------
# Connection pool (lazy, server-name keyed)
# ------------------------------------------------------------------

_connection_pool: Dict[str, FullMCPClient] = {}
_pool_lock = threading.Lock()


def get_client(server_name: str, config: Dict[str, Any]) -> FullMCPClient:
    """Get or create a persistent MCP client from the pool."""
    with _pool_lock:
        client = _connection_pool.get(server_name)
        if client and client.is_connected():
            return client
        if client:
            try:
                client.disconnect()
            except Exception:
                logger.debug("Error disconnecting pooled client", exc_info=True)
        _connection_pool.pop(server_name, None)
        client = FullMCPClient(server_name, config)
        client.connect()
        _connection_pool[server_name] = client
        return client


def disconnect_all():
    """Disconnect all pooled clients."""
    with _pool_lock:
        for name, client in list(_connection_pool.items()):
            try:
                client.disconnect()
            except Exception:
                logger.debug("Error disconnecting client '%s'", name, exc_info=True)
        _connection_pool.clear()
