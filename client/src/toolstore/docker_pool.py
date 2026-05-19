"""
Warm Docker container pool for ToolStore.

Two modes share the same container-lifecycle machinery:

1.  **Worker containers** — persistent Python workers for docker-type tools.
    One container per image.  Code is piped in/out per invocation.
    Protocol: newline-delimited JSON  {id, code, args} → {id, ok, output}.

2.  **MCP-server containers** — persistent containers running an MCP server.
    One container per server.  JSON-RPC travels over stdin/stdout.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from typing import Dict, Any, Optional, List

# ---------------------------------------------------------------------------
# Worker bootstrap (injected into every warm Python container)
# ---------------------------------------------------------------------------

WORKER_BOOTSTRAP = r'''
import sys as _sys, json as _json, traceback as _tb
from io import StringIO as _StringIO

_sys.__stdout__.write("READY\n")
_sys.__stdout__.flush()

while True:
    _line = _sys.stdin.readline()
    if not _line:
        break
    try:
        _req = _json.loads(_line)
    except _json.JSONDecodeError:
        continue

    _rid = _req["id"]
    _code = _req["code"]
    _args = _req.get("args", {})

    _cap = _StringIO()
    _old = _sys.stdout
    _sys.stdout = _cap
    try:
        exec(_code, {"toolstore_args": _args, "TOOLSTORE_ARGS": _args})
        _res = {"id": _rid, "ok": True, "output": _cap.getvalue()}
    except Exception:
        _res = {"id": _rid, "ok": False,
                "output": _cap.getvalue() + _tb.format_exc()}
    finally:
        _sys.stdout = _old

    _sys.__stdout__.write(_json.dumps(_res) + "\n")
    _sys.__stdout__.flush()
'''

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_docker_available() -> Optional[str]:
    """Return ``None`` if Docker is usable, otherwise an error message."""
    import shutil
    if shutil.which("docker") is None:
        return "Docker is not installed or not on PATH."

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

    return None


def detect_dind() -> bool:
    """Return ``True`` if this process is running inside a Docker container."""
    import os
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/self/cgroup", "r") as fh:
            if "docker" in fh.read() or "kubepods" in fh.read():
                return True
    except Exception:
        pass
    if os.environ.get("THINKTOOL_DOCKER") == "1":
        return True
    return False


def dind_socket_check() -> Optional[str]:
    """If we are inside Docker but ``/var/run/docker.sock`` is missing,
    return a helpful error message; otherwise ``None``."""
    import os
    if detect_dind() and not os.path.exists("/var/run/docker.sock"):
        return (
            "Error: Running inside Docker but /var/run/docker.sock is not mounted.\n"
            "Add this to docker-compose.yml:\n"
            "    volumes:\n"
            "      - /var/run/docker.sock:/var/run/docker.sock"
        )
    return None


# ---------------------------------------------------------------------------
# WarmContainer — one persistent worker per image
# ---------------------------------------------------------------------------


class WarmContainer:
    """A persistent Docker container running the Python worker.

    The container is started once and kept alive between tool invocations.
    Calls are serialised through a lock so the single-threaded worker
    inside the container never sees overlapping requests.
    """

    def __init__(self, image: str, container_name: str) -> None:
        self.image = image
        self.name = container_name
        self.proc: Optional[subprocess.Popen] = None
        self._request_id: int = 0
        self._lock = threading.Lock()
        self._alive = False

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Run *docker run -i* and bootstrap the worker."""
        self.proc = subprocess.Popen(
            [
                "docker", "run", "-i", "--rm",
                "--name", self.name,
                "--network", "none",
                "--cpus", "1",
                "--memory", "256m",
                self.image,
                "python", "-u",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Bootstrap: first message carries the worker loop.
        self._write_line(json.dumps({"id": "_bootstrap", "code": WORKER_BOOTSTRAP}))
        # Wait for the READY sentinel.
        ready = self._read_line(timeout=15)
        if not ready or "READY" not in ready:
            self.stop()
            raise RuntimeError(f"Worker container failed to start: {ready!r}")
        self._alive = True

    def stop(self) -> None:
        self._alive = False
        if self.proc:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None

    def is_alive(self) -> bool:
        return (
            self._alive
            and self.proc is not None
            and self.proc.poll() is None
        )

    # -- execute -------------------------------------------------------------

    def execute(self, code: str, args: Dict[str, Any], timeout_s: int) -> str:
        """Pipe *code* + *args* to the worker, return the captured output."""
        with self._lock:
            rid = self._request_id
            self._request_id += 1

        self._write_line(json.dumps({"id": rid, "code": code, "args": args}))
        raw = self._read_line(timeout=timeout_s + 5)

        if raw is None:
            return f"Error: Docker execution timed out after {timeout_s}s."

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            return f"Error: invalid worker response: {raw!r}"

        if result.get("ok"):
            return result.get("output", "").strip() or "(no output)"
        return f"Error:\n{result.get('output', 'unknown error')}"

    # -- I/O helpers ---------------------------------------------------------

    def _write_line(self, text: str) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(text + "\n")
        self.proc.stdin.flush()

    def _read_line(self, timeout: float) -> Optional[str]:
        """Read a single line from the worker stdout with a timeout.

        Uses a separate thread so we can enforce a wall-clock deadline
        without relying on file-descriptor-level timeouts.
        """
        assert self.proc and self.proc.stdout
        result: List[Optional[str]] = [None]

        def _target() -> None:
            try:
                result[0] = self.proc.stdout.readline()  # type: ignore[union-attr]
            except Exception:
                result[0] = None

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            # Timed out — the thread will eventually read and discard.
            return None
        return result[0]


# ---------------------------------------------------------------------------
# WarmContainerPool — global singleton keyed by image
# ---------------------------------------------------------------------------

class WarmContainerPool:
    """A pool of warm containers, keyed by Docker image.

    Usage::

        pool = WarmContainerPool()
        result = pool.execute(image, code, args, timeout=30)
        pool.shutdown_all()
    """

    def __init__(self) -> None:
        self._containers: Dict[str, WarmContainer] = {}
        self._lock = threading.Lock()

    def get(self, image: str) -> WarmContainer:
        """Return (or create) a warm container for *image*."""
        with self._lock:
            c = self._containers.get(image)
            if c is not None and c.is_alive():
                return c
            if c is not None:
                c.stop()
            name = f"ts_wrk_{abs(hash(image)) & 0xFFFF:04x}_{id(self) & 0xFF:02x}"
            c = WarmContainer(image, name)
            c.start()
            self._containers[image] = c
            return c

    def execute(
        self, image: str, code: str, args: Dict[str, Any], timeout_s: int = 30
    ) -> str:
        """Shortcut: get a container and execute code in one call."""
        return self.get(image).execute(code, args, timeout_s)

    def shutdown_all(self) -> None:
        with self._lock:
            for c in self._containers.values():
                c.stop()
            self._containers.clear()

    def shutdown_image(self, image: str) -> None:
        with self._lock:
            c = self._containers.pop(image, None)
            if c:
                c.stop()


# Module-level singleton (lazily initialised by native_tool / mcp_client).

_pool: Optional[WarmContainerPool] = None
_pool_lock = threading.Lock()


def get_pool() -> WarmContainerPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = WarmContainerPool()
    return _pool
