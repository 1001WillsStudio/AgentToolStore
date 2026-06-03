"""
Docker container management for ToolStore.

Two separate container models:

1.  **Single shared worker** — one persistent Python worker for ALL toolset
    executions.  The container starts once and stays alive forever.  Toolset
    code is piped in/out per invocation via newline-delimited JSON.

2.  **MCP-server containers** — one container per MCP server (started by
    ``DockerTransport`` in ``transport.py``).  JSON-RPC over stdin/stdout.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Worker bootstrap (injected into every warm Python container)
# ---------------------------------------------------------------------------

WORKER_BOOTSTRAP = r'''
import sys as _sys, json as _json, traceback as _tb
from io import StringIO as _StringIO

_modules = {}  # module_name -> namespace holding its functions

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
    _action = _req.get("action", "call")

    if _action == "load":
        # Load a module — exec the code, store its namespace.
        _name = _req["module"]
        _code = _req["code"]
        _ns = {}
        try:
            exec(_code, _ns)
        except Exception:
            _res = {"id": _rid, "ok": False, "output": _tb.format_exc()}
        else:
            _modules[_name] = _ns
            _res = {"id": _rid, "ok": True, "output": f"module '{_name}' loaded"}

    elif _action == "call":
        _mod = _req["module"]
        _func = _req["function"]
        _args = _req.get("args", {})
        _ns = _modules.get(_mod)
        if _ns is None:
            _res = {"id": _rid, "ok": False,
                    "output": f"module '{_mod}' not loaded"}
        else:
            _fn = _ns.get(_func)
            if _fn is None:
                _res = {"id": _rid, "ok": False,
                        "output": f"function '{_func}' not found in module '{_mod}'"}
            elif not callable(_fn):
                _res = {"id": _rid, "ok": False,
                        "output": f"'{_func}' in module '{_mod}' is not callable"}
            else:
                _cap = _StringIO()
                _old = _sys.stdout
                _sys.stdout = _cap
                try:
                    _result = _fn(**_args)
                    _output = _cap.getvalue()
                    if _result is not None:
                        _output += _json.dumps(_result, default=str)
                    _res = {"id": _rid, "ok": True, "output": _output}
                except Exception:
                    _res = {"id": _rid, "ok": False,
                            "output": _cap.getvalue() + _tb.format_exc()}
                finally:
                    _sys.stdout = _old

    else:
        _res = {"id": _rid, "ok": False,
                "output": f"unknown action '{_action}'"}

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
        logger.warning("Docker daemon check failed: %s", exc)
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
        logger.debug("Failed to read /proc/self/cgroup for dind detection", exc_info=True)
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
# WarmContainer — the single shared Python worker for all toolset executions
# ---------------------------------------------------------------------------


class WarmContainer:
    """The single persistent Docker container that runs ALL toolset executions.

    Started once (lazily, on first use) and kept alive forever.  Toolset
    modules are loaded once and cached in the worker; subsequent calls
    invoke named functions from those modules.
    """

    def __init__(self, image: str, container_name: str) -> None:
        self.image = image
        self.name = container_name
        self.proc: Optional[subprocess.Popen] = None
        self._request_id: int = 0
        self._lock = threading.Lock()
        self._alive = False
        self._loaded_modules: set = set()  # track what we've sent load for

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
        # Bootstrap: load the worker loop as a module via the load action.
        self._write_line(json.dumps({
            "id": "_bootstrap",
            "action": "load",
            "module": "_worker",
            "code": WORKER_BOOTSTRAP,
        }))
        # Discard the bootstrap response, then send a dummy call to
        # confirm the worker is running and reading.
        self._read_line(timeout=15)
        self._write_line(json.dumps({
            "id": "_ping",
            "action": "call",
            "module": "_worker",
            "function": "_whoami_does_not_exist",
            "args": {},
        }))
        raw = self._read_line(timeout=15)
        if raw is None:
            self.stop()
            raise RuntimeError("Worker did not respond after bootstrap")
        # Any response (even error) means the worker is alive.
        self._alive = True

    def stop(self) -> None:
        self._alive = False
        if self.proc:
            try:
                self.proc.stdin.close()
            except Exception:
                logger.debug("Error closing worker stdin", exc_info=True)
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    logger.debug("Error killing worker process", exc_info=True)
            self.proc = None

    def is_alive(self) -> bool:
        return (
            self._alive
            and self.proc is not None
            and self.proc.poll() is None
        )

    # -- load / call ---------------------------------------------------------

    def load_module(self, name: str, code: str, timeout_s: int = 15) -> str:
        """Load *code* into the worker as a named module (idempotent).

        Returns the worker response string (usually a confirmation or error).
        """
        if name in self._loaded_modules:
            return ""  # already loaded

        with self._lock:
            rid = self._request_id
            self._request_id += 1

        self._write_line(json.dumps({
            "id": rid, "action": "load", "module": name, "code": code,
        }))
        raw = self._read_line(timeout=timeout_s)
        if raw is None:
            return f"Error: load timed out for module '{name}'"
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            return f"Error: invalid load response: {raw!r}"
        if result.get("ok"):
            self._loaded_modules.add(name)
            return ""
        return result.get("output", "unknown load error")

    def call_function(
        self, module: str, function: str,
        args: Dict[str, Any], timeout_s: int,
    ) -> str:
        """Call *function* inside *module* with keyword *args*."""
        with self._lock:
            rid = self._request_id
            self._request_id += 1

        self._write_line(json.dumps({
            "id": rid, "action": "call",
            "module": module, "function": function,
            "args": args,
        }))
        raw = self._read_line(timeout=timeout_s + 5)

        if raw is None:
            return f"Error: call timed out after {timeout_s}s"
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            return f"Error: invalid call response: {raw!r}"

        if result.get("ok"):
            out = result.get("output", "")
            return out.strip() if out.strip() else "(no output)"
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
                logger.debug("Error reading from worker stdout", exc_info=True)
                result[0] = None

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            # Timed out — the thread will eventually read and discard.
            return None
        return result[0]


# ---------------------------------------------------------------------------
# Module-level singleton — the one shared worker
# ---------------------------------------------------------------------------

_worker: Optional[WarmContainer] = None
_worker_lock = threading.Lock()


def get_worker() -> WarmContainer:
    """Return (or lazily start) the single shared worker container.

    The image comes from the user's config (``default_docker_image``).
    """
    global _worker
    if _worker is not None and _worker.is_alive():
        return _worker

    with _worker_lock:
        # Double-check inside the lock
        if _worker is not None and _worker.is_alive():
            return _worker

        # Import here to avoid circularity at module level
        from toolstore.config_manager import ConfigManager
        cfg = ConfigManager()
        cfg.load()
        image = cfg.get_default_docker_image()

        name = "ts_worker"
        _worker = WarmContainer(image, name)
        _worker.start()
        return _worker


def shutdown_worker() -> None:
    """Stop the shared worker (e.g. at process exit)."""
    global _worker
    with _worker_lock:
        if _worker:
            _worker.stop()
            _worker = None
