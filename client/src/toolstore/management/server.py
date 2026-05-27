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

import shutil

from ..config_manager import ConfigManager
from ..mcp_client import FullMCPClient, disconnect_all
from ..skill_manager import SkillDefinition, SkillManager, get_skill_manager

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
# Config I/O  (single source of truth: config.json, shared with CLI)
# ============================================================================

# Internal key we normalise to for the SPA (snake_case).
# ConfigManager (CLI) uses "mcpServers" (camelCase) in config.json.

_SPA_MCP_KEY = "mcp_servers"
_CLI_MCP_KEY = "mcpServers"


def _config_manager() -> ConfigManager:
    """Return a ConfigManager that respects TOOLSTORE_HOME."""
    cm = ConfigManager()
    cm.load()
    return cm


def load_config() -> dict:
    """Load ``config.json`` and normalise keys for the SPA.

    The CLI writes ``mcpServers`` (camelCase) but the SPA expects
    ``mcp_servers`` (snake_case).  We normalise on read + write so both
    consumers share the same file.
    """
    cfg = dict(_DEFAULT_CFG)
    cm = _config_manager()

    # Normalise mcpServers (CLI) → mcp_servers (SPA)
    cli_servers = cm.config.get(_CLI_MCP_KEY, {})
    if cli_servers:
        cfg[_SPA_MCP_KEY] = dict(cli_servers)

    # Copy SPA-specific keys if present
    for k in ("tools", "skills"):
        if k in cm.config:
            cfg[k] = cm.config[k]

    return cfg


def save_config(cfg: dict) -> None:
    """Persist SPA state back to ``config.json``.

    Writes ``mcp_servers`` (SPA) → ``mcpServers`` (CLI) so both the
    management UI and the CLI see the same MCP servers.
    """
    cm = _config_manager()

    # Normalise back: mcp_servers (SPA) → mcpServers (CLI)
    spa_servers = cfg.get(_SPA_MCP_KEY, {})
    if spa_servers:
        cm.config[_CLI_MCP_KEY] = dict(spa_servers)

    # Store SPA extensions alongside CLI keys
    cm.config["tools"] = cfg.get("tools", {})
    cm.config["skills"] = cfg.get("skills", {})

    cm.save()


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
    # Detect transport: explicit key → has command+args → has url → "sse"
    transport_type = srv.get("transport") or srv.get("type")
    if not transport_type:
        if srv.get("command"):
            transport_type = "stdio"
        else:
            transport_type = "sse"
    if transport_type == "folder":
        _start_mcp_folder(server_id, srv)
        time.sleep(1.5)
        sub_transport = srv.get("sub_transport", "sse")
        url = srv.get("url", "")
    elif transport_type == "docker":
        sub_transport = "docker"
        url = ""
    else:
        sub_transport = transport_type
        url = srv.get("url", "")
    client = FullMCPClient(server_id, {
        "type": sub_transport,
        "transport": sub_transport,
        "command": srv.get("command", ""),
        "args": srv.get("args", []),
        "url": url,
        "env": srv.get("env", {}),
        "timeout": srv.get("timeout", 30),
        "image": srv.get("image", ""),
        "entrypoint": [srv.get("command", "python")] + srv.get("args", []),
    })
    client.connect()
    tools_info = client.list_tools()
    _connected_clients[server_id] = client
    # list_tools() returns {"tools": [...]} — extract the list
    if isinstance(tools_info, dict):
        tool_list = tools_info.get("tools", [])
    else:
        tool_list = tools_info if isinstance(tools_info, list) else []
    tools: list[dict] = []
    for t in tool_list:
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
            elif p.startswith("/api/tools"):
                self._list_tools()
            elif p == "/api/mcp/servers":
                self._list_mcp()
            elif p == "/api/skills":
                self._list_skills()
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
        try:
            if p == "/api/skills/upload":
                self._upload_skill()
                return
            body = self._body()
            if p == "/api/mcp/code":
                self._run_mcp_code(body)
            elif p == "/api/mcp/servers":
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
        """Install all skills found in a folder tree.

        Walks *path* recursively, finds every directory containing a
        SKILL.md, validates each one, and copies them into the configured
        skill directories.  This replaces the old ``*.py`` glob.
        """
        from ..skill_discovery import discover_skills

        path = body.get("path", "").strip()
        if not path:
            self._json({"error": "path is required"}, 400); return
        fp = Path(path).expanduser().resolve()
        if not fp.is_dir():
            self._json({"error": f"Not a directory: {fp}"}, 400); return

        result = discover_skills(fp)
        if result.total == 0:
            self._json({"success": True, "registered": [],
                        "failed": [], "message": "No SKILL.md directories found"})
            return

        cm = ConfigManager()
        cm.load()
        sm = get_skill_manager(cm.get_skill_dirs())

        registered = []
        failed = []
        for ds in result.valid_skills:
            try:
                sd = sm.install_skill(ds.skill_def.skill_dir)
                if sd:
                    registered.append(sd.name)
                else:
                    failed.append({"name": ds.name,
                                   "error": "install returned None"})
            except Exception as exc:
                failed.append({"name": ds.name, "error": str(exc)})

        # Persist skill dirs to config
        for d in sm.skill_dirs:
            cm.add_skill_dir(str(d))

        # Register each installed skill as a tool (survives page refresh)
        cfg = load_config()
        cfg.setdefault("tools", {})
        for name in registered:
            cfg["tools"][f"skill:{name}"] = {
                "source": f"skill:{name}",
                "enabled": True,
                "exposure": "secondary",
                "parallel_safe": False,
                "subagent_safe": False,
                "description": "",
            }
        save_config(cfg)

        self._json({"success": True,
                    "registered": registered,
                    "failed": failed,
                    "total": result.total,
                    "valid": result.valid_count,
                    "invalid": result.invalid_count})

    def _upload_skill(self):
        """Handle browser-based skill upload (JSON-payload with base64 zip).

        Discovers ALL skills in the archive (recursively), validates each,
        and installs them — just like ``_register_skill_folder`` but against
        an uploaded zip instead of a server-side path.
        """
        import tempfile
        import zipfile
        import base64
        from io import BytesIO
        from ..skill_discovery import discover_skills

        try:
            body = self._body()
        except Exception:
            self._json({"error": "Invalid JSON body"}, 400); return

        archive_b64 = body.get("archive", "")
        if not archive_b64:
            self._json({"error": "No 'archive' field in upload"}, 400); return

        try:
            zip_data = base64.b64decode(archive_b64)
        except Exception:
            self._json({"error": "Invalid base64 data"}, 400); return

        tmp = Path(tempfile.mkdtemp(prefix="toolstore-skill-"))
        try:
            with zipfile.ZipFile(BytesIO(zip_data)) as zf:
                zf.extractall(tmp)

            # Discover ALL skills in the extracted tree (recursive)
            result = discover_skills(tmp)
            if result.total == 0:
                self._json({"error": "No SKILL.md found in uploaded archive"}, 400); return

            cm = ConfigManager()
            cm.load()
            sm = get_skill_manager(cm.get_skill_dirs())

            registered = []
            failed = []
            for ds in result.valid_skills:
                try:
                    installed = sm.install_skill(ds.skill_def.skill_dir)
                    if installed:
                        registered.append(installed.name)
                    else:
                        failed.append({"name": ds.name,
                                       "error": "install returned None"})
                except Exception as exc:
                    failed.append({"name": ds.name, "error": str(exc)})

            # Also report invalid skills that were skipped
            for ds in result.invalid_skills:
                failed.append({"name": ds.name or str(ds.rel_path),
                               "error": "; ".join(ds.errors)})

            # Persist skill dirs to config
            for d in sm.skill_dirs:
                cm.add_skill_dir(str(d))

            # Register each installed skill as a tool so it survives page
            # refresh and can be patched (exposure, …) afterwards.
            cfg2 = load_config()
            cfg2.setdefault("tools", {})
            for name in registered:
                cfg2["tools"][f"skill:{name}"] = {
                    "source": f"skill:{name}",
                    "enabled": True,
                    "exposure": "secondary",
                    "parallel_safe": False,
                    "subagent_safe": False,
                    "description": "",
                }
            save_config(cfg2)

            self._json({"success": True,
                        "registered": registered,
                        "failed": failed,
                        "total": result.total,
                        "valid": result.valid_count,
                        "invalid": result.invalid_count})
        except zipfile.BadZipFile:
            self._json({"error": "Uploaded file is not a valid zip archive"}, 400)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _register_skill(self, body: dict):
        """Install a single skill from a directory containing SKILL.md.

        Validates the directory, copies it into the configured skill dirs,
        and rescans so it is immediately available.
        """
        path = body.get("path", "").strip()
        if not path:
            self._json({"error": "path is required"}, 400); return

        skill_path = Path(path).expanduser().resolve()
        if not skill_path.is_dir():
            self._json({"error": f"Not a directory: {skill_path}"}, 400); return

        # Validate SKILL.md exists and is well-formed
        sd = SkillDefinition(skill_path)
        if not sd.load():
            self._json({"error": "Skill validation failed",
                        "details": sd.errors}, 400); return

        cm = ConfigManager()
        cm.load()
        sm = get_skill_manager(cm.get_skill_dirs())

        installed = sm.install_skill(skill_path)
        if installed is None:
            self._json({"error": "Failed to install skill"}, 500); return

        # Persist skill dirs to config
        for d in sm.skill_dirs:
            cm.add_skill_dir(str(d))

        # Register as a tool so it survives page refresh
        cfg = load_config()
        cfg.setdefault("tools", {})
        cfg["tools"][f"skill:{installed.name}"] = {
            "source": f"skill:{installed.name}",
            "enabled": True,
            "exposure": "secondary",
            "parallel_safe": False,
            "subagent_safe": False,
            "description": "",
        }
        save_config(cfg)

        self._json({"success": True,
                    "skill": installed.name,
                    "description": installed.description[:100],
                    "path": str(skill_path)})

    def _list_skills(self):
        """Return skills from SkillManager (not the old config.yaml dict)."""
        cm = ConfigManager()
        cm.load()
        sm = get_skill_manager(cm.get_skill_dirs())
        sm.scan()
        result = {}
        for name, sd in sm._skills.items():
            result[name] = {
                "description": sd.description,
                "path": str(sd.skill_dir),
                "license": sd.license,
            }
        self._json(result)

    def _remove_skill(self, name: str):
        """Remove a skill from the local filesystem."""
        cm = ConfigManager()
        cm.load()
        sm = get_skill_manager(cm.get_skill_dirs())
        sm.scan()

        sd = sm.get_skill(name)
        if not sd:
            self._json({"error": "Skill not found"}, 404); return

        # Remove skill directory from disk
        skill_dir = sd.skill_dir
        if skill_dir.exists():
            shutil.rmtree(skill_dir, ignore_errors=True)

        # Remove from in-memory index
        sm._skills.pop(name, None)

        # Remove from config.yaml tools
        cfg = load_config()
        prefix = f"skill:{name}"
        cfg["tools"] = {k: v for k, v in cfg.get("tools", {}).items()
                        if v.get("source") != prefix}
        save_config(cfg)
        self._json({"success": True})

    # ── API: run code in Docker ─────────────────────────────────────────

    def _run_mcp_code(self, body: dict):
        """POST /api/mcp/code  — paste MCP server code, run in Docker."""
        import tempfile, uuid
        from ..docker_pool import check_docker_available, dind_socket_check

        # ── validate inputs ─────────────────────────────────────────
        code = (body.get("code") or "").strip()
        if not code:
            self._json({"error": "No code provided"}, 400); return

        language = body.get("language", "python").lower()
        if language not in ("python", "node"):
            self._json({"error": f"Unsupported language: {language}. Use 'python' or 'node'."}, 400); return

        image = body.get("image", "").strip() or (
            "python:3.12-slim" if language == "python" else "node:22-slim")

        server_label = body.get("server_id", "").strip()
        if not server_label:
            server_label = f"mcp-code-{uuid.uuid4().hex[:8]}"

        # ── check Docker ────────────────────────────────────────────
        err = dind_socket_check() or check_docker_available()
        if err:
            self._json({"error": err}, 500); return

        # ── build Docker image from code ────────────────────────────
        tmp = Path(tempfile.mkdtemp(prefix="toolstore-mcp-code-"))
        try:
            if language == "python":
                code_file = tmp / "server.py"
                code_file.write_text(code)
                dockerfile = (
                    f"FROM {image}\n"
                    "WORKDIR /app\n"
                    "RUN pip install --no-cache-dir mcp 2>/dev/null || true\n"
                    "COPY server.py .\n"
                    'CMD ["python", "server.py"]\n'
                )
            else:  # node
                code_file = tmp / "server.js"
                code_file.write_text(code)
                dockerfile = (
                    f"FROM {image}\n"
                    "WORKDIR /app\n"
                    "RUN npm install @modelcontextprotocol/sdk 2>/dev/null || true\n"
                    "COPY server.js .\n"
                    'CMD ["node", "server.js"]\n'
                )
            (tmp / "Dockerfile").write_text(dockerfile)

            tag = f"toolstore-mcp-{server_label}:latest"
            build_proc = subprocess.run(
                ["docker", "build", "-t", tag, str(tmp)],
                capture_output=True, text=True, timeout=120,
            )
            if build_proc.returncode != 0:
                self._json({
                    "error": "Docker build failed",
                    "details": build_proc.stderr[-1000:],
                }, 500); return
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        # ── register MCP server with Docker image ───────────────────
        cfg = load_config()
        servers = cfg.setdefault("mcp_servers", {})
        if server_label in servers:
            self._json({"error": f"Server '{server_label}' already exists"}, 409); return

        srv: dict = {
            "transport": "docker",
            "image": tag,
            "command": "python" if language == "python" else "node",
            "args": [f"server.{'py' if language == 'python' else 'js'}"],
            "env": body.get("env") or {},
            "auto_connect": body.get("auto_connect", True),
        }
        servers[server_label] = srv
        save_config(cfg)

        # ── attempt to discover tools ───────────────────────────────
        tools = []
        conn_err = None
        if srv.get("auto_connect", True):
            try:
                tools = _connect_and_discover(server_label, srv)
                for t in tools:
                    cfg["tools"][t["name"]] = {
                        "source": f"mcp:{server_label}",
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
            "success": True, "server_id": server_label,
            "image": tag,
            "tools_discovered": len(tools), "tools": tools,
            "connection_error": conn_err,
        })

    # ── API: tools ───────────────────────────────────────────────────────

    def _list_tools(self):
        """GET /api/tools  — return tools organised by source.

        Returns a dict with per-source groups so the UI can display them
        in separate sections:

            {"mcp": {name: tool, ...}, "registry": {name: tool, ...}}
        """
        cfg = load_config()
        result: dict[str, dict] = {"mcp": {}, "registry": {}}

        # 1. MCP-discovered tools (already registered in config by connect)
        result["mcp"] = cfg.get("tools", {})

        # 2. Registry tools from index.json
        cm = _config_manager()
        index_path = cm.config_dir / "index.json"
        if index_path.exists():
            try:
                data = json.loads(index_path.read_text())
                for name, tdef in data.get("tools", {}).items():
                    result["registry"][name] = {
                        "source": tdef.get("source", "registry"),
                        "enabled": True,
                        "exposure": "primary",
                        "parallel_safe": False,
                        "subagent_safe": False,
                        "description": tdef.get("description", ""),
                    }
            except Exception:
                pass

        self._json(result)

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
