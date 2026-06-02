"""
Local management server for the ToolStore client.

Serves the management SPA and provides a REST API for:
  - Local config, MCP server management, skill registration,
    toolset management, registry toolsets, tool exposure control.

Start it::
    python -m toolstore.management.server
"""

from __future__ import annotations

import json
import threading
import urllib.parse
from urllib.request import urlopen
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

from .api_helpers import disconnect_all_clients, disconnect_server, _config_manager
from . import api_mcp, api_skills
import os
import tempfile
import zipfile
import base64
import shutil
from io import BytesIO
from ..toolset_manager import ToolsetDefinition, get_toolset_manager
from ..index_manager import IndexManager
from ..config_manager import ConfigManager
from ..skill_discovery import discover_skills
from ..skill_manager import get_skill_manager
from ..docker_pool import check_docker_available, dind_socket_check
import uuid
import subprocess

# ── Constants ───────────────────────────────────────────────────────────────

MANAGEMENT_DIR = Path(__file__).resolve().parent
STATIC_DIR = MANAGEMENT_DIR / "static"
DEFAULT_PORT = 8765


# ============================================================================
# HTTP handler — delegates to api_* modules
# ============================================================================

class _Handler(SimpleHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silent

    # ── dispatch ────────────────────────────────────────────────────────

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            if p in ("/", "/index.html"):
                return self._serve_spa()
            if p == "/api/config":
                return self._json(api_mcp.load_config())
            if p == "/api/tools":
                return self._list_tools()
            if p == "/api/mcp/servers":
                return self._json(api_mcp.list_mcp_servers())
            if p == "/api/skills":
                return self._json(api_skills.list_skills())
            if p == "/api/toolsets":
                return self._list_toolsets()
            if p == "/api/registry/toolsets":
                return self._list_registry_toolsets()
            if p == "/api/files":
                return self._list_files()
            if p.startswith("/static/"):
                return self._serve_static(p)
            self._json({"error": "Not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            if p == "/api/skills/upload":
                return self._upload_skill()
            if p == "/api/toolsets/upload":
                return self._upload_toolset()
            body = self._body()
            if p == "/api/mcp/code":
                return self._run_mcp_code(body)
            if p == "/api/mcp/servers":
                return self._respond(*api_mcp.add_mcp_server(body))
            if p == "/api/skills":
                return self._respond(*api_skills.register_skill(body))
            if p == "/api/skills/folder":
                return self._respond(*api_skills.register_skill_folder(body))
            if p == "/api/toolsets":
                return self._register_toolset(body)
            if p == "/api/toolsets/folder":
                return self._register_toolset_folder(body)
            if p == "/api/registry/toolsets/download":
                return self._download_toolset(body)
            if p.endswith("/connect") and "/api/mcp/servers/" in p:
                return self._respond(*api_mcp.connect_mcp_server(
                    p.rsplit("/", 2)[-2]))
            if p.endswith("/disconnect") and "/api/mcp/servers/" in p:
                return self._respond(*api_mcp.disconnect_mcp_server(
                    p.rsplit("/", 2)[-2]))
            self._json({"error": "Not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_PATCH(self):
        p = urllib.parse.urlparse(self.path).path
        body = self._body()
        try:
            if p.startswith("/api/tools/") and len(p) > len("/api/tools/"):
                return self._patch_tool(p[len("/api/tools/"):], body)
            if p.startswith("/api/mcp/servers/") and len(p) > len("/api/mcp/servers/"):
                return self._respond(*api_mcp.patch_mcp_server(
                    p[len("/api/mcp/servers/"):], body))
            self._json({"error": "Not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_DELETE(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            if p.startswith("/api/mcp/servers/"):
                return self._respond(*api_mcp.remove_mcp_server(
                    p.split("/")[-1]))
            if p.startswith("/api/skills/"):
                return self._respond(*api_skills.remove_skill(
                    p.split("/")[-1]))
            if p.startswith("/api/toolsets/"):
                return self._remove_toolset(urllib.parse.unquote(p.split("/")[-1]))
            self._json({"error": "Not found"}, 404)
        except Exception as exc:
            self._json({"error": str(exc)}, 500)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _respond(self, data: dict, status: int = 200):
        self._json(data, status)

    # ── SPA / static ───────────────────────────────────────────────────

    def _serve_spa(self):
        fp = STATIC_DIR / "index.html"
        if not fp.exists():
            self._json({"error": "SPA not found"}, 500); return
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
            self._json({"error": "Forbidden"}, 403); return
        if not fp.is_file():
            self._json({"error": "Not found"}, 404); return
        data = fp.read_bytes()
        ct = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png", ".svg": "image/svg+xml",
        }.get(fp.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── API: file browser ─────────────────────────────────────────────

    def _list_files(self):
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        path = params.get("path", [""])[0] or "~"
        fp = Path(path).expanduser().resolve()
        if not fp.is_dir():
            return self._json({"error": "Not a directory"}, 400)
        entries = []
        try:
            for child in sorted(fp.iterdir()):
                try: is_dir = child.is_dir()
                except OSError: is_dir = False
                entries.append({
                    "name": child.name,
                    "type": "directory" if is_dir else "file",
                })
        except PermissionError:
            return self._json({"error": "Permission denied"}, 403)
        self._json({"path": str(fp), "parent": str(fp.parent),
                    "entries": entries})

    # ── API: skills upload ────────────────────────────────────────────

    def _upload_skill(self):

        try: body = self._body()
        except Exception: return self._json({"error": "Invalid JSON body"}, 400)

        archive_b64 = body.get("archive", "")
        if not archive_b64:
            return self._json({"error": "No 'archive' field in upload"}, 400)
        try: zip_data = base64.b64decode(archive_b64)
        except Exception: return self._json({"error": "Invalid base64 data"}, 400)

        tmp = Path(tempfile.mkdtemp(prefix="toolstore-skill-"))
        try:
            with zipfile.ZipFile(BytesIO(zip_data)) as zf: zf.extractall(tmp)
            result = discover_skills(tmp)
            if result.total == 0:
                return self._json({"error": "No SKILL.md found in uploaded archive"}, 400)
            cm = ConfigManager(); cm.load()
            sm = get_skill_manager(cm.get_skill_dirs())
            registered, failed = [], []
            for ds in result.valid_skills:
                try:
                    inst = sm.install_skill(ds.skill_def.skill_dir)
                    if inst: registered.append(inst.name)
                    else: failed.append({"name": ds.name, "error": "install returned None"})
                except Exception as exc:
                    failed.append({"name": ds.name, "error": str(exc)})
            for ds in result.invalid_skills:
                failed.append({"name": ds.name or str(ds.rel_path), "error": "; ".join(ds.errors)})
            for d in sm.skill_dirs: cm.add_skill_dir(str(d))
            cfg = api_mcp.load_config(); cfg.setdefault("skills", {})
            for name in registered:
                cfg["skills"][name] = {
                    "source": f"skill:{name}", "enabled": True,
                    "exposure": "secondary", "parallel_safe": False,
                    "subagent_safe": False, "description": ""}
            api_mcp.save_config(cfg)
            self._json({"success": True, "registered": registered,
                        "failed": failed, "total": result.total,
                        "valid": result.valid_count, "invalid": result.invalid_count})
        except zipfile.BadZipFile:
            self._json({"error": "Uploaded file is not a valid zip archive"}, 400)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ── API: toolset upload ──────────────────────────────────────────

    def _upload_toolset(self):

        try: body = self._body()
        except Exception: return self._json({"error": "Invalid JSON body"}, 400)

        archive_b64 = body.get("archive", "")
        if not archive_b64:
            return self._json({"error": "No 'archive' field in upload"}, 400)
        try: zip_data = base64.b64decode(archive_b64)
        except Exception: return self._json({"error": "Invalid base64 data"}, 400)

        tmp = Path(tempfile.mkdtemp(prefix="toolstore-toolset-"))
        try:
            with zipfile.ZipFile(BytesIO(zip_data)) as zf: zf.extractall(tmp)
            toolset_dirs = []
            for root, dirs, _files in os.walk(tmp):
                for d in dirs:
                    if list((Path(root) / d).glob("*.md")):
                        toolset_dirs.append(Path(root) / d)
            if list(tmp.glob("*.md")):
                toolset_dirs.append(tmp)

            if not toolset_dirs:
                return self._json({"error": "No toolset found in uploaded archive (requires at least one .md file)"}, 400)

            cm = ConfigManager(); cm.load()
            im = IndexManager(); im.load()
            persistent_root = cm.config_dir / "toolsets"
            persistent_root.mkdir(parents=True, exist_ok=True)
            registered, failed = [], []

            for ts_dir in toolset_dirs:
                td = ToolsetDefinition(ts_dir)
                if not td.load():
                    failed.append({"name": ts_dir.name, "error": "; ".join(td.errors)})
                    continue
                name = td.name
                if td.doc and td.doc.startswith("#"):
                    name = td.doc.split("\n")[0].lstrip("#").strip()
                dest = persistent_root / name
                if not dest.exists():
                    shutil.copytree(ts_dir, dest)
                im._local_tools[name] = {
                    "name": name,
                    "type": "toolset",
                    "source": "local",
                    "toolset_dir": str(dest),
                    "description": td.doc[:200] if td.doc else "",
                    "doc": td.doc or "",
                    "bindings": td.functions,
                }
                registered.append(name)

            im._save_local()
            cfg_up = api_mcp.load_config()
            for name in registered:
                cfg_up.setdefault("toolsets", {})[name] = im._local_tools[name]
            api_mcp.save_config(cfg_up)
            self._json({"success": True, "registered": registered, "failed": failed})
        except zipfile.BadZipFile:
            self._json({"error": "Uploaded file is not a valid zip archive"}, 400)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ── API: toolsets + registry toolsets ─────────────────────────────

    def _list_toolsets(self):
        im = IndexManager()
        im.load()
        result = {}
        for name, entry in im._local_tools.items():
            if entry.get("type") != "toolset":
                continue
            result[name] = {
                "description": (entry.get("description") or ""),
                "path": entry.get("toolset_dir", ""),
                "functions": list(entry.get("bindings", {}).keys()),
            }
        self._json(result)

    def _register_toolset(self, body: dict):
        path = body.get("path", "").strip()
        if not path: return self._json({"error": "path is required"}, 400)
        ts_path = Path(path).expanduser().resolve()
        if not ts_path.is_dir(): return self._json({"error": f"Not a directory: {ts_path}"}, 400)
        td = ToolsetDefinition(ts_path)
        if not td.load(): return self._json({"error": "Toolset validation failed", "details": td.errors}, 400)
        cm = ConfigManager(); cm.load()
        persistent_root = cm.config_dir / "toolsets"
        persistent_root.mkdir(parents=True, exist_ok=True)
        dest = persistent_root / td.name
        if not dest.exists():
            shutil.copytree(ts_path, dest)
        im = IndexManager()
        im.load()
        im._local_tools[td.name] = {
            "name": td.name,
            "type": "toolset",
            "source": "local",
            "toolset_dir": str(dest),
            "description": td.doc[:200] if td.doc else "",
            "doc": td.doc or "",
            "bindings": td.functions,
        }
        im._save_local()
        cfg = api_mcp.load_config()
        cfg.setdefault("toolsets", {})[td.name] = im._local_tools[td.name]
        api_mcp.save_config(cfg)
        self._json({"success": True, "toolset": td.name,
                    "functions": list(td.functions.keys()), "path": str(dest)})

    def _register_toolset_folder(self, body: dict):
        path = body.get("path", "").strip()
        if not path: return self._json({"error": "path is required"}, 400)
        fp = Path(path).expanduser().resolve()
        if not fp.is_dir(): return self._json({"error": f"Not a directory: {fp}"}, 400)
        cm = ConfigManager(); cm.load(); cm.add_toolset_dir(str(fp))
        mgr = get_toolset_manager([str(fp)]); count = mgr.scan()

        im = IndexManager(); im.load()
        registered = []
        for td in mgr.get_all():
            if not td.is_valid:
                continue
            im._local_tools[td.name] = {
                "name": td.name,
                "type": "toolset",
                "source": "local",
                "toolset_dir": str(td.directory),
                "description": td.doc[:200] if td.doc else "",
                "doc": td.doc or "",
                "bindings": td.functions,
            }
            registered.append(td.name)
        im._save_local()
        cfg = api_mcp.load_config()
        for name in registered:
            cfg.setdefault("toolsets", {})[name] = im._local_tools[name]
        api_mcp.save_config(cfg)
        self._json({"success": True, "registered": registered, "count": count})

    def _remove_toolset(self, name: str):
        im = IndexManager()
        im.load()
        if name not in im._local_tools:
            return self._json({"error": "Toolset not found"}, 404)

        entry = im._local_tools[name]
        ts_dir = entry.get("toolset_dir")
        if ts_dir:
            shutil.rmtree(ts_dir, ignore_errors=True)
        del im._local_tools[name]
        im._save_local()
        cfg_rm = api_mcp.load_config()
        cfg_rm.get("toolsets", {}).pop(name, None)
        api_mcp.save_config(cfg_rm)
        self._json({"success": True})

    def _list_registry_toolsets(self):
        cm = _config_manager()
        ip = _config_manager().config_dir / "online_registry.json"

        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        if params.get("refresh", [""])[0] == "true":
            if ip.exists():
                ip.unlink()

        if not ip.exists():
            try:
                registry_url = cm.get_registry_url()
                with urlopen(registry_url, timeout=10) as resp:
                    raw = resp.read().decode("utf-8")
                    ip.parent.mkdir(parents=True, exist_ok=True)
                    ip.write_text(raw, encoding="utf-8")
            except Exception:
                return self._json({})
        try:
            data = json.loads(ip.read_text())
        except Exception:
            return self._json({})

        im = IndexManager()
        im.load()
        local_names = set(im._local_tools.keys())
        result = {}

        if isinstance(data, list):
            for tdef in data:
                if not isinstance(tdef, dict):
                    continue
                if tdef.get("type") != "toolset":
                    continue
                name = tdef.get("name", "")
                if not name or name in local_names:
                    continue
                bindings = tdef.get("bindings", {})
                result[name] = {
                    "description": tdef.get("description", ""),
                    "functions": list(bindings.keys()) if bindings else [],
                    "version": tdef.get("version", ""),
                    "source": tdef.get("source", "public"),
                    "category": tdef.get("category", ""),
                    "exposure": "hidden"}
        elif isinstance(data, dict):
            for name, tdef in data.get("tools", {}).items():
                if not isinstance(tdef, dict):
                    continue
                if tdef.get("type") != "toolset":
                    continue
                if name in local_names:
                    continue
                bindings = tdef.get("bindings", {})
                result[name] = {
                    "description": tdef.get("description", ""),
                    "functions": list(bindings.keys()) if bindings else [],
                    "version": tdef.get("version", ""),
                    "source": tdef.get("source", "public"),
                    "category": tdef.get("category", ""),
                    "exposure": "hidden"}
        self._json(result)

    def _download_toolset(self, body: dict):
        name = body.get("name", "").strip()
        if not name: return self._json({"error": "name is required"}, 400)
        cm = _config_manager()
        ip = _config_manager().config_dir / "online_registry.json"
        if not ip.exists(): return self._json({"error": "Registry index not found"}, 404)
        try: data = json.loads(ip.read_text())
        except Exception: return self._json({"error": "Failed to read registry index"}, 500)
        if isinstance(data, list):
            tdef = next((t for t in data if isinstance(t, dict) and t.get("name") == name), None)
        else:
            tdef = data.get("tools", {}).get(name)
        if not tdef or tdef.get("type") != "toolset":
            return self._json({"error": f"Toolset '{name}' not found in registry"}, 404)
        root = cm.config_dir / "toolsets"; (root / name).mkdir(parents=True, exist_ok=True)
        doc = tdef.get("doc", "") or tdef.get("description", "")
        (root / name / "doc.md").write_text(doc, encoding="utf-8")
        code = tdef.get("code", "")
        if not code and tdef.get("code_base64"):
            code = base64.b64decode(tdef["code_base64"]).decode("utf-8")
        if code:
            (root / name / "toolset.py").write_text(code, encoding="utf-8")

        im = IndexManager(); im.load()
        im._local_tools[name] = {
            "name": name,
            "type": "toolset",
            "source": "remote",
            "toolset_dir": str(root / name),
            "description": tdef.get("description", ""),
            "doc": tdef.get("doc", "") or "",
            "bindings": tdef.get("bindings", {}),
        }
        im._save_local()
        cfg_set = api_mcp.load_config()
        cfg_set.setdefault("toolsets", {})[name] = im._local_tools[name]
        api_mcp.save_config(cfg_set)
        self._json({"success": True, "toolset": name})

    # ── API: run code in Docker ───────────────────────────────────────

    def _run_mcp_code(self, body: dict):
        code = (body.get("code") or "").strip()
        if not code: return self._json({"error": "No code provided"}, 400)
        language = body.get("language", "python").lower()
        if language not in ("python", "node"):
            return self._json({"error": "Unsupported language. Use 'python' or 'node'."}, 400)
        image = body.get("image", "").strip() or (
            "python:3.12-slim" if language == "python" else "node:22-slim")
        server_label = body.get("server_id", "").strip() or f"mcp-code-{uuid.uuid4().hex[:8]}"
        err = dind_socket_check() or check_docker_available()
        if err: return self._json({"error": err}, 500)

        tmp = Path(tempfile.mkdtemp(prefix="toolstore-mcp-code-"))
        try:
            if language == "python":
                (tmp / "server.py").write_text(code)
                dockerfile = f"FROM {image}\nWORKDIR /app\nRUN pip install --no-cache-dir mcp 2>/dev/null || true\nCOPY server.py .\nCMD [\"python\", \"server.py\"]\n"
            else:
                (tmp / "server.js").write_text(code)
                dockerfile = f"FROM {image}\nWORKDIR /app\nRUN npm install @modelcontextprotocol/sdk 2>/dev/null || true\nCOPY server.js .\nCMD [\"node\", \"server.js\"]\n"
            (tmp / "Dockerfile").write_text(dockerfile)
            tag = f"toolstore-mcp-{server_label}:latest"
            bp = subprocess.run(["docker", "build", "-t", tag, str(tmp)],
                                capture_output=True, text=True, timeout=120)
            if bp.returncode != 0:
                return self._json({"error": "Docker build failed",
                                   "details": bp.stderr[-1000:]}, 500)
        finally: shutil.rmtree(tmp, ignore_errors=True)

        cfg = api_mcp.load_config()
        servers = cfg.setdefault("mcp_servers", {})
        if server_label in servers:
            return self._json({"error": f"Server '{server_label}' already exists"}, 409)
        srv = {"transport": "docker", "image": tag,
               "command": "python" if language == "python" else "node",
               "args": [f"server.{'py' if language == 'python' else 'js'}"],
               "env": body.get("env") or {},
               "auto_connect": body.get("auto_connect", True)}
        servers[server_label] = srv
        api_mcp.save_config(cfg)
        tools, conn_err = [], None
        if srv.get("auto_connect", True):
            try:
                tools = api_mcp.connect_and_discover(server_label, srv)
                srv_tools = cfg.setdefault("mcp_servers", {}).setdefault(server_label, {}).setdefault("tools", {})
                for t in tools:
                    srv_tools[t["name"]] = {
                        "source": f"mcp:{server_label}", "enabled": True,
                        "exposure": body.get("exposure_default", "secondary"),
                        "parallel_safe": False, "subagent_safe": False,
                        "description": t.get("description", "")}
                api_mcp.save_config(cfg)
            except Exception as exc: conn_err = str(exc)
        self._json({"success": True, "server_id": server_label, "image": tag,
                    "tools_discovered": len(tools), "tools": tools,
                    "connection_error": conn_err})

    # ── API: tools list / patch ───────────────────────────────────────

    def _list_tools(self):
        """List all tools from the 3‑type hierarchy (MCP servers, skills, toolsets)."""
        cfg = api_mcp.load_config()
        servers = cfg.get("mcp_servers", {})
        result = {"mcp": {}, "mcp_toolsets": {}, "registry": {}, "toolsets": {}, "skills": {}}

        if isinstance(servers, dict):
            for sid, srv in servers.items():
                if not isinstance(srv, dict):
                    continue
                srv_tools = srv.get("tools", {})
                if not isinstance(srv_tools, dict) or not srv_tools:
                    continue
                if srv.get("mode", "toolset") == "toolset":
                    display = srv.get("display_name") or sid
                    result["mcp_toolsets"][display] = {
                        "source": f"mcp:{sid}",
                        "server_id": sid,
                        "enabled": True,
                        "exposure": srv.get("exposure", "secondary"),
                        "parallel_safe": False,
                        "subagent_safe": False,
                        "description": srv.get("description", "") or f"MCP server with {len(srv_tools)} tool{'s' if len(srv_tools) != 1 else ''}",
                        "functions": list(srv_tools.keys()),
                    }
                else:
                    for tn, ti in srv_tools.items():
                        if not isinstance(ti, dict):
                            continue
                        result["mcp"][tn] = {
                            "source": f"mcp:{sid}", "enabled": ti.get("enabled", True),
                            "exposure": ti.get("exposure", "secondary"),
                            "parallel_safe": ti.get("parallel_safe", False),
                            "subagent_safe": ti.get("subagent_safe", False),
                            "description": ti.get("description", "")}

        # Skills (from cfg["skills"])
        skill_cache = cfg.get("skills", {})
        if isinstance(skill_cache, dict):
            for sn, si in skill_cache.items():
                if not isinstance(si, dict):
                    continue
                result["skills"][f"skill:{sn}"] = {
                    "source": f"skill:{sn}", "enabled": si.get("enabled", True),
                    "exposure": si.get("exposure", "secondary"),
                    "parallel_safe": si.get("parallel_safe", False),
                    "subagent_safe": si.get("subagent_safe", False),
                    "description": si.get("description", "")}

        # Registry toolsets (online_registry.json — unchanged)
        cm = _config_manager()
        ip = _config_manager().config_dir / "online_registry.json"
        if ip.exists():
            try:
                data = json.loads(ip.read_text())
                if isinstance(data, list):
                    for tdef in data:
                        if not isinstance(tdef, dict):
                            continue
                        name = tdef.get("name", "")
                        if not name or name in result["mcp"] or name in result["skills"]:
                            continue
                        result["registry"][name] = {
                            "source": tdef.get("source", "registry"),
                            "enabled": True, "exposure": "hidden",
                            "parallel_safe": False, "subagent_safe": False,
                            "description": tdef.get("description", "")}
                else:
                    for name, tdef in data.get("tools", {}).items():
                        if name in result["mcp"] or name in result["skills"]:
                            continue
                        result["registry"][name] = {
                            "source": tdef.get("source", "registry"),
                            "enabled": True, "exposure": "hidden",
                            "parallel_safe": False, "subagent_safe": False,
                            "description": tdef.get("description", "")}
            except Exception: pass

        # Local toolsets (from local_registry.json)
        im = IndexManager(); im.load()
        for name, entry in im._local_tools.items():
            if entry.get("type") != "toolset":
                continue
            result["toolsets"][name] = {
                "source": entry.get("source", f"toolset:{name}"),
                "enabled": True,
                "exposure": entry.get("exposure", "secondary"),
                "parallel_safe": False, "subagent_safe": False,
                "description": entry.get("description", "")}
        self._json(result)

    def _patch_tool(self, name: str, body: dict):
        """Patch a tool's exposure/enabled/etc.  Searches MCP servers, skills, and toolsets."""
        cfg = api_mcp.load_config()
        im = IndexManager(); im.load()

        target: dict | None = None
        target_key: str = ""

        # 1. Search MCP servers' tools dicts
        servers = cfg.get("mcp_servers", {})
        if isinstance(servers, dict):
            for sid, srv in servers.items():
                if isinstance(srv, dict) and name in srv.get("tools", {}):
                    target = srv["tools"]
                    target_key = name
                    break

        # 2. Search skill cache
        if target is None:
            raw_name = name[len("skill:"):] if name.startswith("skill:") else name
            skill_cache = cfg.get("skills", {})
            if raw_name in skill_cache:
                target = skill_cache
                target_key = raw_name

        # 3. Search local toolsets
        in_local = name in im._local_tools
        if target is None and in_local:
            target = im._local_tools
            target_key = name

        # 4. Check MCP server-level (display_name or server_id)
        if target is None:
            if isinstance(servers, dict):
                for sid, srv in servers.items():
                    if isinstance(srv, dict) and (srv.get("display_name") == name or sid == name):
                        res, code = api_mcp.patch_mcp_server(sid, body)
                        return self._json(res, code)
            return self._json({"error": "Tool not found"}, 404)

        # Apply patch
        for k in ("exposure", "enabled", "parallel_safe", "subagent_safe"):
            if k in body:
                target[target_key][k] = body[k]

        # Persist
        if target is im._local_tools:
            im._save_local()
            cfg.setdefault("toolsets", {})[name] = im._local_tools[name]
        api_mcp.save_config(cfg)
        self._json({"success": True, "tool": name})

    # ── helpers ───────────────────────────────────────────────────────

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0: return {}
        try: return json.loads(self.rfile.read(length))
        except json.JSONDecodeError: return {}

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
        server.start()   # non-blocking background thread
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
        self._httpd = HTTPServer((self.host, self.port), _Handler)
        if blocking:
            print(f"ToolStore management UI → {self.url}")
            try: self._httpd.serve_forever()
            except KeyboardInterrupt: pass
            finally: disconnect_all_clients()
        else:
            self._thread = threading.Thread(
                target=self._httpd.serve_forever, daemon=True)
            self._thread.start()
            print(f"ToolStore management UI → {self.url}")

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        disconnect_all_clients()


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    ap = argparse.ArgumentParser(description="ToolStore local management server")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    ManagementServer(port=args.port, host=args.host).start(blocking=True)


if __name__ == "__main__":
    main()
