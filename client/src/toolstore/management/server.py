"""
Local management server for the ToolStore client.

Serves the management SPA and provides a REST API for:
  - Local config ( ``~/.toolstore/config.yaml`` )
  - MCP server management (connect, disconnect, discover tools)
  - Skill registration
  - Tool exposure control (primary / secondary / disabled)

All operations happen on the **local** machine.  This server is meant to run
alongside AuroraCoder (or any agent host) on a local port (default 8765).

Start it::

    python -m toolstore.management.server

Or from code::

    from toolstore.management.server import ManagementServer
    server = ManagementServer(port=8765)
    server.start()
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

import yaml

from ..config_manager import ConfigManager
from ..mcp_client import FullMCPClient, disconnect_all

# ── Constants ───────────────────────────────────────────────────────────────

MANAGEMENT_DIR = Path(__file__).resolve().parent
STATIC_DIR = MANAGEMENT_DIR / "static"
DEFAULT_PORT = 8765

_DEFAULT_CFG: dict[str, Any] = {
    "mcp_servers": {},
    "tools": {},
    "skills": {},
}


# ============================================================================
# Config I/O  (single source of truth: ~/.toolstore/config.yaml)
# ============================================================================

def _config_dir() -> Path:
    p = ConfigManager().config_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def _config_path() -> Path:
    return _config_dir() / "config.yaml"


def load_config() -> dict:
    """Load ``config.yaml``, normalising keys to what the SPA expects."""
    cfg = dict(_DEFAULT_CFG)
    cp = _config_path()
    if cp.exists():
        try:
            raw = yaml.safe_load(cp.read_text()) or {}
            # ConfigManager stores MCP servers under "mcpServers";
            # we normalise to "mcp_servers" everywhere.
            if "mcpServers" in raw:
                cfg["mcp_servers"] = raw["mcpServers"]
            if "mcp_servers" in raw:
                cfg["mcp_servers"] = raw["mcp_servers"]
            for k in ("tools", "skills"):
                if k in raw:
                    cfg[k] = raw[k]
        except (yaml.YAMLError, OSError):
            pass
    # Ensure "mcp_servers" key
    if "mcp_servers" not in cfg:
        cfg["mcp_servers"] = {}
    return cfg


def save_config(cfg: dict) -> None:
    """Write config back to ``config.yaml``.

    ``mcp_servers`` is written as ``mcpServers`` for ConfigManager compatibility.
    """
    cp = _config_path()
    out: dict[str, Any] = {
        # ConfigManager reads this key
        "mcpServers": cfg.get("mcp_servers", {}),
    }
    # Preserve any other top-level keys ConfigManager might use
    raw_servers = cfg.get("mcp_servers", {})
    if raw_servers:
        out["mcpServers"] = raw_servers
    # Our extensions
    out["tools"] = cfg.get("tools", {})
    out["skills"] = cfg.get("skills", {})
    cp.write_text(yaml.safe_dump(out, default_flow_style=False, allow_unicode=True))


# ============================================================================
# MCP helpers
# ============================================================================

# In-process cache of connected clients so we can check status.
_connected_clients: dict[str, FullMCPClient] = {}
_mcp_processes: dict[str, subprocess.Popen] = {}

def _mcp_status(server_id: str) -> str:
    """'connected' | 'disconnected'."""
    if server_id in _connected_clients:
        return "connected"
    return "disconnected"


def _start_mcp_folder(server_id: str, srv: dict) -> bool:
    fp = Path(srv.get("folder", "")).expanduser().resolve()
    if not fp.is_dir():
        raise RuntimeError(f"MCP folder not found: {fp}")
    command = srv.get("command", "python")
    args = list(srv.get("args", []))
    env = {**os.environ, **(srv.get("env") or {})}
    for k, v in list(env.items()):
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env[k] = os.environ.get(v[2:-1], "")
    proc = subprocess.Popen([command] + args, cwd=str(fp), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _mcp_processes[server_id] = proc
    return True


def _connect_and_discover(server_id: str, srv: dict) -> list[dict]:
    transport_type = srv.get("transport", "sse")
    if transport_type == "folder":
        _start_mcp_folder(server_id, srv)
        time.sleep(1.5)
        sub_transport = srv.get("sub_transport", "sse")
        url = srv.get("url", "")
    else:
        sub_transport = transport_type
        url = srv.get("url", "")
    client = FullMCPClient(server_id, {
        "transport": sub_transport,
        "command": srv.get("command", ""),
        "args": srv.get("args", []),
        "url": url,
        "env": srv.get("env", {}),
        "timeout": srv.get("timeout", 30),
    })
    client.connect()
    tools_info = client.list_tools()
    _connected_clients[server_id] = client
    tools: list[dict] = []
    for t in tools_info:
        tools.append({
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "parameters": t.get("inputSchema", t.get("parameters", {})),
        })
    return tools


def _shutdown_mcp_process(server_id: str) -> None:
    proc = _mcp_processes.pop(server_id, None)
    if proc is None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass


def _disconnect_server(server_id: str) -> None:
    _shutdown_mcp_process(server_id)
    client = _connected_clients.pop(server_id, None)
    if client:
        try:
            client.disconnect()
        except Exception:
            pass


def _disconnect_all() -> None:
    for cid in list(_connected_clients.keys()):
        _disconnect_server(cid)
    for pid in list(_mcp_processes.keys()):
        _shutdown_mcp_process(pid)
    try:
        disconnect_all()
    except Exception:
        pass


def _count_mcp_tools(cfg: dict, server_id: str) -> int:
    prefix = f"mcp:{server_id}"
    return sum(1 for v in cfg.get("tools", {}).values()
               if v.get("source") == prefix)


# ============================================================================
# HTTP handler
# ============================================================================

class _Handler(SimpleHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silent

    # ── dispatch ────────────────────────────────────────────────────────

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            if p == "/" or p == "/index.html":
                self._serve_spa()
            elif p == "/api/config":
                self._json(load_config())
            elif p == "/api/mcp/servers":
                self._list_mcp()
            elif p == "/api/skills":
                self._json(load_config().get("skills", {}))
            elif p == "/api/files":
                self._list_files()
            elif p.startswith("/static/"):
                self._serve_static(p)
            else:
                self._json({"error": "Not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        body = self._body()
        try:
            if p == "/api/mcp/servers":
                self._add_mcp(body)
            elif p == "/api/skills":
                self._register_skill(body)
            elif p == "/api/skills/folder":
                self._register_skill_folder(body)
            elif p.endswith("/connect") and "/api/mcp/servers/" in p:
                sid = p.rsplit("/", 2)[-2]
                self._connect_mcp(sid)
            elif p.endswith("/disconnect") and "/api/mcp/servers/" in p:
                sid = p.rsplit("/", 2)[-2]
                self._disconnect_mcp(sid)
            else:
                self._json({"error": "Not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_PATCH(self):
        p = urllib.parse.urlparse(self.path).path
        body = self._body()
        try:
            if p.startswith("/api/tools/") and len(p) > len("/api/tools/"):
                tool_name = p[len("/api/tools/"):]
                self._patch_tool(tool_name, body)
            else:
                self._json({"error": "Not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_DELETE(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            if p.startswith("/api/mcp/servers/"):
                sid = p.split("/")[-1]
                self._remove_mcp(sid)
            elif p.startswith("/api/skills/"):
                name = p.split("/")[-1]
                self._remove_skill(name)
            else:
                self._json({"error": "Not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── SPA / static ─────────────────────────────────────────────────────

    def _serve_spa(self):
        fp = STATIC_DIR / "index.html"
        if not fp.exists():
            self._json({"error": "SPA not found"}, 500)
            return
        data = fp.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path: str):
        rel = path[len("/static/"):].replace("\\", "/").lstrip("/")
        fp = STATIC_DIR / rel
        if not fp.resolve().is_relative_to(STATIC_DIR.resolve()):
            self._json({"error": "Forbidden"}, 403)
            return
        if not fp.is_file():
            self._json({"error": "Not found"}, 404)
            return
        data = fp.read_bytes()
        ct = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }.get(fp.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── API: MCP servers ─────────────────────────────────────────────────

    def _list_mcp(self):
        cfg = load_config()
        servers = cfg.get("mcp_servers", {})
        out = {}
        for sid, srv in servers.items():
            entry = dict(srv)
            entry["status"] = _mcp_status(sid)
            entry["tools_count"] = _count_mcp_tools(cfg, sid)
            out[sid] = entry
        self._json(out)

    def _add_mcp(self, body: dict):
        sid = body.get("server_id", "").strip()
        if not sid:
            self._json({"error": "server_id is required"}, 400); return

        cfg = load_config()
        servers = cfg.setdefault("mcp_servers", {})
        if sid in servers:
            self._json({"error": "Server already exists"}, 409); return

        transport = body.get("transport", "sse")
        srv: dict[str, Any] = {
            "transport": transport,
            "enabled": body.get("enabled", True),
            "auto_connect": body.get("auto_connect", True),
        }
        if transport == "stdio":
            srv["command"] = body.get("command", "")
            srv["args"] = body.get("args", [])
        elif transport == "folder":
            srv["folder"] = body.get("folder", "")
            srv["sub_transport"] = body.get("sub_transport", "sse")
            srv["command"] = body.get("command", "")
            srv["args"] = body.get("args", [])
            srv["url"] = body.get("url", "")
        else:
            srv["url"] = body.get("url", "")
        env = body.get("env")
        if env:
            srv["env"] = env

        servers[sid] = srv
        save_config(cfg)

        tools: list[dict] = []
        conn_err = None
        if srv.get("auto_connect", True):
            try:
                tools = _connect_and_discover(sid, srv)
                for t in tools:
                    tn = t["name"]
                    cfg["tools"][tn] = {
                        "source": f"mcp:{sid}",
                        "enabled": True,
                        "exposure": body.get("exposure_default", "secondary"),
                        "parallel_safe": False,
                        "subagent_safe": False,
                        "description": t.get("description", ""),
                    }
                save_config(cfg)
            except Exception as exc:
                conn_err = str(exc)

        self._json({
            "success": True, "server_id": sid,
            "tools_discovered": len(tools), "tools": tools,
            "connection_error": conn_err,
        })

    def _connect_mcp(self, sid: str):
        cfg = load_config()
        servers = cfg.get("mcp_servers", {})
        if sid not in servers:
            self._json({"error": "Server not found"}, 404); return

        tools = _connect_and_discover(sid, servers[sid])
        for t in tools:
            tn = t["name"]
            if tn not in cfg.get("tools", {}):
                cfg["tools"][tn] = {
                    "source": f"mcp:{sid}",
                    "enabled": True,
                    "exposure": "secondary",
                    "parallel_safe": False,
                    "subagent_safe": False,
                    "description": t.get("description", ""),
                }
        save_config(cfg)
        self._json({"success": True, "tools": tools})

    def _disconnect_mcp(self, sid: str):
        _disconnect_server(sid)
        self._json({"success": True})

    def _remove_mcp(self, sid: str):
        cfg = load_config()
        if sid not in cfg.get("mcp_servers", {}):
            self._json({"error": "Server not found"}, 404); return

        _disconnect_server(sid)
        del cfg["mcp_servers"][sid]

        prefix = f"mcp:{sid}"
        cfg["tools"] = {k: v for k, v in cfg.get("tools", {}).items()
                        if v.get("source") != prefix}
        save_config(cfg)
        self._json({"success": True})

    # ── API: file browser ──────────────────────────────────────────────

    def _list_files(self):
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        path = params.get("path", [""])[0] or os.path.expanduser("~")
        fp = Path(path).expanduser().resolve()
        if not fp.is_dir():
            self._json({"error": "Not a directory"}, 400); return
        entries = []
        try:
            for child in sorted(fp.iterdir()):
                try:
                    is_dir = child.is_dir()
                except OSError:
                    is_dir = False
                entries.append({
                    "name": child.name,
                    "type": "directory" if is_dir else "file",
                })
        except PermissionError:
            self._json({"error": "Permission denied"}, 403); return
        self._json({"path": str(fp), "parent": str(fp.parent), "entries": entries})

    # ── API: skills folder ─────────────────────────────────────────────

    def _register_skill_folder(self, body: dict):
        path = body.get("path", "").strip()
        if not path:
            self._json({"error": "path is required"}, 400); return
        fp = Path(path).expanduser().resolve()
        if not fp.is_dir():
            self._json({"error": f"Not a directory: {fp}"}, 400); return
        registered = []
        failed = []
        for py_file in sorted(fp.glob("*.py")):
            name = py_file.stem
            try:
                body_single = {
                    "name": name,
                    "path": str(py_file),
                    "description": body.get("description", ""),
                    "exposure": body.get("exposure", "secondary"),
                    "parallel_safe": body.get("parallel_safe", False),
                    "subagent_safe": body.get("subagent_safe", False),
                }
                self._register_skill(body_single)
                registered.append(name)
            except Exception as exc:
                failed.append({"name": name, "error": str(exc)})
        self._json({"success": True, "registered": registered, "failed": failed})

    def _register_skill(self, body: dict):
        name = body.get("name", "").strip()
        if not name:
            self._json({"error": "name is required"}, 400); return

        path = body.get("path", "").strip()
        if not path:
            self._json({"error": "path is required"}, 400); return

        # Expand ~ to user home
        skill_path = Path(path).expanduser().resolve()
        if not skill_path.exists():
            self._json({"error": f"File not found: {skill_path}"}, 404); return
        if not skill_path.is_file():
            self._json({"error": f"Not a file: {skill_path}"}, 400); return

        # Read the existing skill file (validates it exists and is readable)
        try:
            code = skill_path.read_text()
        except OSError as exc:
            self._json({"error": f"Cannot read file: {exc}"}, 400); return

        cfg = load_config()
        entry = {
            "description": body.get("description", ""),
            "path": str(skill_path),
            "enabled": True,
            "exposure": body.get("exposure", "secondary"),
            "parallel_safe": body.get("parallel_safe", False),
            "subagent_safe": body.get("subagent_safe", False),
        }
        cfg.setdefault("skills", {})[name] = entry

        cfg["tools"][name] = {
            "source": f"skill:{name}",
            "enabled": True,
            "exposure": entry["exposure"],
            "parallel_safe": entry["parallel_safe"],
            "subagent_safe": entry["subagent_safe"],
            "description": entry["description"],
        }

        save_config(cfg)
        self._json({"success": True, "skill": name, "path": str(skill_path)})

    def _remove_skill(self, name: str):
        cfg = load_config()
        if name not in cfg.get("skills", {}):
            self._json({"error": "Skill not found"}, 404); return

        del cfg["skills"][name]
        prefix = f"skill:{name}"
        cfg["tools"] = {k: v for k, v in cfg.get("tools", {}).items()
                        if v.get("source") != prefix}
        save_config(cfg)
        self._json({"success": True})

    # ── API: tools ───────────────────────────────────────────────────────

    def _patch_tool(self, name: str, body: dict):
        cfg = load_config()
        tools = cfg.setdefault("tools", {})
        if name not in tools:
            self._json({"error": "Tool not found"}, 404); return
        for k in ("exposure", "enabled", "parallel_safe", "subagent_safe"):
            if k in body:
                tools[name][k] = body[k]
        save_config(cfg)
        self._json({"success": True, "tool": name})

    # ── helpers ──────────────────────────────────────────────────────────

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods",
                         "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, Authorization")


# ============================================================================
# Public API
# ============================================================================

class ManagementServer:
    """Local management server for ToolStore.

    Usage::

        server = ManagementServer(port=8765)
        server.start()          # non-blocking background thread
        # … use the SPA at http://localhost:8765 …
        server.stop()
    """

    def __init__(self, port: int = DEFAULT_PORT, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self, blocking: bool = False) -> None:
        """Start the management server.

        Args:
            blocking: If *True*, block the calling thread; otherwise run in a
                daemon background thread.
        """
        self._httpd = HTTPServer((self.host, self.port), _Handler)
        if blocking:
            print(f"ToolStore management UI → {self.url}")
            try:
                self._httpd.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                _disconnect_all()
        else:
            self._thread = threading.Thread(
                target=self._httpd.serve_forever, daemon=True,
            )
            self._thread.start()
            print(f"ToolStore management UI → {self.url}")

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        for pid in list(_mcp_processes.keys()):
            _shutdown_mcp_process(pid)
        _disconnect_all()


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    ap = argparse.ArgumentParser(description="ToolStore local management server")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"Port (default: {DEFAULT_PORT})")
    ap.add_argument("--host", default="127.0.0.1", help="Bind address")
    args = ap.parse_args()
    ManagementServer(port=args.port, host=args.host).start(blocking=True)


if __name__ == "__main__":
    main()
