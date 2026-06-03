"""
Transport abstraction for MCP connections.

Supports:
- stdio: subprocess-based JSON-RPC over stdin/stdout
- sse: HTTP Server-Sent Events with POST for requests (Streamable HTTP)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class MCPTransport(ABC):
    """Abstract transport for sending/receiving JSON-RPC messages."""

    @abstractmethod
    def start(self) -> None:
        """Open the transport connection."""
        ...

    @abstractmethod
    def send(self, message: Dict[str, Any]) -> None:
        """Send a JSON-RPC message (request or notification)."""
        ...

    @abstractmethod
    def receive(self) -> Dict[str, Any]:
        """Block until a complete JSON-RPC message is received."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the transport."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the transport is currently open."""
        ...


# ---------------------------------------------------------------------------
# Stdio transport
# ---------------------------------------------------------------------------

class StdioTransport(MCPTransport):
    """JSON-RPC over subprocess stdin/stdout."""

    def __init__(self, command: str, args: list[str] = None,
                 env: Dict[str, str] = None, cwd: str = None):
        self._cmd = [command] + (args or [])
        self._env = os.environ.copy()
        if env:
            self._env.update(env)
        self._cwd = cwd
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    # ---- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        use_shell = sys.platform == "win32"
        self._process = subprocess.Popen(
            self._cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            env=self._env,
            cwd=self._cwd,
            text=True,
            bufsize=1,
            shell=use_shell,
        )

    def close(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                logger.debug("StdioTransport: terminate failed, sending kill", exc_info=True)
                self._process.kill()
            self._process = None

    def is_connected(self) -> bool:
        return self._process is not None and self._process.poll() is None

    # ---- I/O ---------------------------------------------------------------

    def send(self, message: Dict[str, Any]) -> None:
        if not self._process or self._process.poll() is not None:
            raise ConnectionError("Stdio transport not connected")
        line = json.dumps(message, ensure_ascii=False)
        with self._lock:
            self._process.stdin.write(line + "\n")
            self._process.stdin.flush()

    def receive(self) -> Dict[str, Any]:
        if not self._process:
            raise ConnectionError("Stdio transport not connected")
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise ConnectionError("MCP server closed connection")
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue  # skip non-JSON (log lines)


# ---------------------------------------------------------------------------
# SSE / Streamable HTTP transport
# ---------------------------------------------------------------------------

class SSETransport(MCPTransport):
    """JSON-RPC over HTTP POST + SSE response stream.

    This implements the *Streamable HTTP* variant of MCP where:
    - Requests are sent via HTTP POST
    - Responses arrive on an SSE event stream (initiated by an initial GET)
    - The session id is tracked via a header.
    """

    def __init__(self, base_url: str, headers: Dict[str, str] = None,
                 timeout: float = 60.0):
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}
        self._timeout = timeout
        self._client: Optional[httpx.Client] = None
        self._session_id: Optional[str] = None
        self._sse_buffer: list[Dict[str, Any]] = []
        self._sse_lock = threading.Condition()
        self._sse_thread: Optional[threading.Thread] = None
        self._running = False

    # ---- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._client = httpx.Client(timeout=self._timeout)
        self._running = True
        self._sse_thread = threading.Thread(target=self._sse_loop, daemon=True)
        self._sse_thread.start()

    def close(self) -> None:
        self._running = False
        if self._sse_thread and self._sse_thread.is_alive():
            self._sse_thread.join(timeout=5)
        if self._client:
            self._client.close()
            self._client = None
        self._session_id = None

    def is_connected(self) -> bool:
        return self._running

    # ---- I/O ---------------------------------------------------------------

    def send(self, message: Dict[str, Any]) -> None:
        """POST a JSON-RPC message; responses arrive on the SSE stream."""
        if not self._client:
            raise ConnectionError("SSE transport not connected")
        headers = {**self._headers, "Content-Type": "application/json"}
        if self._session_id:
            headers["X-Session-Id"] = self._session_id
        resp = self._client.post(
            f"{self._base_url}/message",
            json=message,
            headers=headers,
        )
        resp.raise_for_status()
        sid = resp.headers.get("X-Session-Id")
        if sid:
            self._session_id = sid

    def receive(self) -> Dict[str, Any]:
        """Wait for the next message from the SSE buffer."""
        with self._sse_lock:
            while not self._sse_buffer:
                if not self._running:
                    raise ConnectionError("SSE transport closed")
                self._sse_lock.wait(timeout=1.0)
            return self._sse_buffer.pop(0)

    # ---- SSE event loop -----------------------------------------------------

    def _sse_loop(self) -> None:
        """Long-lived GET that reads SSE events into the buffer."""
        backoff = 0.5
        while self._running:
            try:
                headers = {**self._headers, "Accept": "text/event-stream"}
                if self._session_id:
                    headers["X-Session-Id"] = self._session_id
                with self._client.stream("GET", f"{self._base_url}/sse",
                                         headers=headers) as resp:
                    resp.raise_for_status()
                    sid = resp.headers.get("X-Session-Id")
                    if sid:
                        self._session_id = sid
                    # Parse SSE lines
                    data_lines: list[str] = []
                    for line in resp.iter_lines():
                        if not self._running:
                            return
                        if line.startswith("data: "):
                            data_lines.append(line[6:])
                        elif line == "" and data_lines:
                            payload = "\n".join(data_lines)
                            data_lines = []
                            try:
                                msg = json.loads(payload)
                                with self._sse_lock:
                                    self._sse_buffer.append(msg)
                                    self._sse_lock.notify_all()
                            except json.JSONDecodeError:
                                pass
                    # Stream ended normally, reconnect
                    backoff = 0.5
            except Exception:
                logger.debug("SSE stream error, reconnecting in %.1fs", backoff, exc_info=True)
                if self._running:
                    threading.Event().wait(backoff)
                    backoff = min(backoff * 2, 30)

# ---------------------------------------------------------------------------
# Docker transport  (containerised MCP server)
# ---------------------------------------------------------------------------

class DockerTransport(MCPTransport):
    """JSON-RPC over stdin/stdout of a Docker container running an MCP server.

    The container is started once and kept alive across tool calls — the
    same persistent model used by docker-type tools.  JSON-RPC messages
    are framed as newline-delimited JSON over the container's stdio.
    """

    def __init__(self, image: str, entrypoint: list[str] = None,
                 env: Dict[str, str] = None, timeout: float = 60.0):
        self._image = image
        self._entrypoint = entrypoint or ["python", "-m", "server"]
        self._env = os.environ.copy()
        if env:
            self._env.update(env)
        self._timeout = timeout
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    # ---- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        cmd = [
            "docker", "run", "-i", "--rm",
            "--network", "none",
            "--cpus", "1",
            "--memory", "256m",
            self._image,
        ] + self._entrypoint
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )

    def close(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    logger.debug("DockerTransport: kill failed", exc_info=True)
            self._process = None

    def is_connected(self) -> bool:
        return self._process is not None and self._process.poll() is None

    # ---- I/O ---------------------------------------------------------------

    def send(self, message: Dict[str, Any]) -> None:
        if not self._process or self._process.poll() is not None:
            raise ConnectionError("Docker transport not connected")
        line = json.dumps(message, ensure_ascii=False)
        with self._lock:
            self._process.stdin.write(line + "\n")
            self._process.stdin.flush()

    def receive(self) -> Dict[str, Any]:
        if not self._process:
            raise ConnectionError("Docker transport not connected")
        while True:
            line = self._process.stdout.readline()
            if not line:
                raise ConnectionError("MCP server (docker) closed connection")
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue  # skip non-JSON lines (logging, etc.)


# ---------------------------------------------------------------------------
# Transport factory
# ---------------------------------------------------------------------------

def create_transport(config: Dict[str, Any]) -> MCPTransport:
    """Create the appropriate transport from an MCP server config dict.

    Config shapes recognised:

    **stdio**:
        {"type": "stdio", "command": "npx", "args": ["-y", "@acme/server"],
         "env": {"KEY": "val"}, "cwd": "/tmp"}

    **sse / streamable-http**:
        {"type": "sse", "url": "http://localhost:3000",
         "headers": {"Authorization": "Bearer xxx"}}

    If ``image`` is present, docker is assumed (containerised MCP server).
    If ``type`` is omitted and ``command`` is present, stdio is assumed.
    If ``type`` is omitted and ``url`` is present, sse is assumed.
    """
    transport_type = config.get("type", "").lower()

    # Auto-detect
    if not transport_type:
        if "image" in config:
            transport_type = "docker"
        elif "command" in config:
            transport_type = "stdio"
        elif "url" in config:
            transport_type = "sse"

    if transport_type == "stdio":
        return StdioTransport(
            command=config["command"],
            args=config.get("args"),
            env=config.get("env"),
            cwd=config.get("cwd"),
        )
    elif transport_type in ("sse", "streamable-http"):
        return SSETransport(
            base_url=config["url"],
            headers=config.get("headers"),
            timeout=config.get("timeout", 60.0),
        )
    elif transport_type == "docker":
        return DockerTransport(
            image=config["image"],
            entrypoint=config.get("entrypoint", ["python", "-m", "server"]),
            env=config.get("env"),
            timeout=config.get("timeout", 60.0),
        )
    else:
        raise ValueError(f"Unknown MCP transport type: {transport_type!r}")
