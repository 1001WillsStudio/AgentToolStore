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
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

from .api_helpers import disconnect_all_clients, disconnect_server, _config_manager
from . import api_mcp, api_skills

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
                return self._remove_toolset(p.split("/")[-1])
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
        from ..skill_discovery import discover_skills
        import tempfile, zipfile, base64, shutil
        from io import BytesIO
        from ..config_manager import ConfigManager
        from ..skill_manager import get_skill_manager

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
            cfg = api_mcp.load_config(); cfg.setdefault("tools", {})
            for name in registered:
                cfg["tools"][f"skill:{name}"] = {
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

    # ── API: toolsets + registry toolsets ─────────────────────────────

    def _list_toolsets(self):
        from ..config_manager import ConfigManager
        from ..toolset_manager import get_toolset_manager
        cm = ConfigManager(); cm.load()
        dirs = cm.get_toolset_dirs()
        if not dirs: return self._json({})
        mgr = get_toolset_manager(dirs); mgr.scan()
        result = {}
        for td in mgr.get_all():
            if not td.is_valid: continue
            result[td.name] = {
                "description": td.doc[:200] if td.doc else "",
                "path": str(td.directory),
                "functions": list(td.functions.keys())}
        cfg = api_mcp.load_config(); cfg.setdefault("toolsets", {})
        for name, info in result.items():
            if name not in cfg["toolsets"]:
                cfg["toolsets"][name] = {"source": f"toolset:{name}",
                                         "description": info["description"]}
        api_mcp.save_config(cfg)
        self._json(result)

    def _register_toolset(self, body: dict):
        import shutil
        from pathlib import Path
        from ..config_manager import ConfigManager
        from ..toolset_manager import ToolsetDefinition
        path = body.get("path", "").strip()
        if not path: return self._json({"error": "path is required"}, 400)
        ts_path = Path(path).expanduser().resolve()
        if not ts_path.is_dir(): return self._json({"error": f"Not a directory: {ts_path}"}, 400)
        td = ToolsetDefinition(ts_path)
        if not td.load(): return self._json({"error": "Toolset validation failed", "details": td.errors}, 400)
        cm = ConfigManager(); cm.load()
        # Copy into the persistent Docker dir if we're running in Docker,
        # otherwise just add the parent directory to the search path.
        persistent_root = cm.config_dir / "toolsets"
        persistent_root.mkdir(parents=True, exist_ok=True)
        dest = persistent_root / td.name
        if not dest.exists():
            shutil.copytree(ts_path, dest)
        if str(persistent_root) not in cm.get_toolset_dirs():
            cm.add_toolset_dir(str(persistent_root))
        cfg = api_mcp.load_config(); cfg.setdefault("toolsets", {})
        cfg["toolsets"][td.name] = {"source": f"toolset:{td.name}",
                                    "description": td.doc[:200] if td.doc else ""}
        api_mcp.save_config(cfg)
        self._json({"success": True, "toolset": td.name,
                    "functions": list(td.functions.keys()), "path": str(dest)})

    def _register_toolset_folder(self, body: dict):
        from pathlib import Path
        from ..config_manager import ConfigManager
        from ..toolset_manager import get_toolset_manager
        path = body.get("path", "").strip()
        if not path: return self._json({"error": "path is required"}, 400)
        fp = Path(path).expanduser().resolve()
        if not fp.is_dir(): return self._json({"error": f"Not a directory: {fp}"}, 400)
        cm = ConfigManager(); cm.load(); cm.add_toolset_dir(str(fp))
        mgr = get_toolset_manager([str(fp)]); count = mgr.scan()
        cfg = api_mcp.load_config(); cfg.setdefault("toolsets", {})
        registered = []
        for td in mgr.get_all():
            if not td.is_valid: continue
            cfg["toolsets"][td.name] = {"source": f"toolset:{td.name}",
                                        "description": td.doc[:200] if td.doc else ""}
            registered.append(td.name)
        api_mcp.save_config(cfg)
        self._json({"success": True, "registered": registered, "count": count})

    def _remove_toolset(self, name: str):
        import shutil
        from ..config_manager import ConfigManager
        cfg = api_mcp.load_config()
        if name not in cfg.get("toolsets", {}):
            return self._json({"error": "Toolset not found"}, 404)
        del cfg["toolsets"][name]
        # Also delete the toolset directory from disk so it doesn't
        # reappear when the filesystem is rescanned on the next refresh.
        cm = ConfigManager(); cm.load()
        for base in cm.get_toolset_dirs():
            candidate = Path(base) / name
            if candidate.is_dir():
                shutil.rmtree(candidate, ignore_errors=True)
                break
        api_mcp.save_config(cfg)
        self._json({"success": True})

    def _list_registry_toolsets(self):
        """Return online toolsets from the registry index."""
        cm = _config_manager()
        ip = cm.config_dir / "index.json"

        # Refresh: delete cache so we re‑fetch from registry
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        if params.get("refresh", [""])[0] == "true":
            if ip.exists():
                ip.unlink()

        # Fetch from registry if no local cache
        if not ip.exists():
            try:
                import urllib.request
                registry = cm.get_registry_url()
                with urllib.request.urlopen(registry, timeout=10) as resp:
                    raw = resp.read().decode("utf-8")
                    ip.parent.mkdir(parents=True, exist_ok=True)
                    ip.write_text(raw, encoding="utf-8")
            except Exception:
                return self._json({})
        try:
            data = json.loads(ip.read_text())
        except Exception:
            return self._json({})

        cfg = api_mcp.load_config()
        local_ts = cfg.get("toolsets", {})
        result = {}

        # Flat‑list format (ToolStore registry: [{name, description, ...}])
        if isinstance(data, list):
            for tdef in data:
                if not isinstance(tdef, dict):
                    continue
                if tdef.get("type") != "toolset":
                    continue
                name = tdef.get("name", "")
                if not name or name in local_ts:
                    continue
                bindings = tdef.get("bindings", {})
                result[name] = {
                    "description": tdef.get("description", ""),
                    "functions": list(bindings.keys()) if bindings else [],
                    "version": tdef.get("version", ""),
                    "source": tdef.get("source", "public"),
                    "category": tdef.get("category", ""),
                    "exposure": "hidden"}
        # Legacy dict‑in‑dict format
        elif isinstance(data, dict):
            for name, tdef in data.get("tools", {}).items():
                if not isinstance(tdef, dict):
                    continue
                if tdef.get("type") != "toolset":
                    continue
                if name in local_ts:
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
        import json, base64
        name = body.get("name", "").strip()
        if not name: return self._json({"error": "name is required"}, 400)
        cm = _config_manager(); ip = cm.config_dir / "index.json"
        if not ip.exists(): return self._json({"error": "Registry index not found"}, 404)
        try: data = json.loads(ip.read_text())
        except Exception: return self._json({"error": "Failed to read registry index"}, 500)
        # Handle both flat‑list and legacy dict format
        if isinstance(data, list):
            tdef = next((t for t in data if isinstance(t, dict) and t.get("name") == name), None)
        else:
            tdef = data.get("tools", {}).get(name)
        if not tdef or tdef.get("type") != "toolset":
            return self._json({"error": f"Toolset '{name}' not found in registry"}, 404)
        cfg = api_mcp.load_config()
        if name in cfg.get("toolsets", {}):
            return self._json({"error": f"Toolset '{name}' already installed locally"}, 409)
        exposure = body.get("exposure", "secondary")
        code = tdef.get("code") or tdef.get("code_base64")
        if code:
            root = cm.config_dir / "toolsets"; (root / name).mkdir(parents=True, exist_ok=True)
            if tdef.get("code_base64"): code = base64.b64decode(code).decode("utf-8")
            (root / name / "toolset.py").write_text(code, encoding="utf-8")
            cm.add_toolset_dir(str(root))
        cfg.setdefault("toolsets", {})
        cfg["toolsets"][name] = {"source": f"toolset:{name}",
                                 "exposure": exposure, "description": tdef.get("description", "")}
        api_mcp.save_config(cfg)
        self._json({"success": True, "toolset": name, "exposure": exposure})

    # ── API: run code in Docker ───────────────────────────────────────

    def _run_mcp_code(self, body: dict):
        import tempfile, uuid, shutil, subprocess
        from ..docker_pool import check_docker_available, dind_socket_check
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
                for t in tools:
                    cfg["tools"][t["name"]] = {
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
        import json
        cfg = api_mcp.load_config()
        servers = cfg.get("mcpServers", {})
        result = {"mcp": {}, "mcp_toolsets": {}, "registry": {}, "toolsets": {}, "skills": {}}

        # ── MCP toolset entries (toolset-mode servers grouped as one card) ──
        if isinstance(servers, dict):
            for sid, srv in servers.items():
                if srv.get("mode", "toolset") != "toolset":
                    continue
                prefix = f"mcp:{sid}"
                fn_names = []
                for tn, ti in cfg.get("tools", {}).items():
                    if isinstance(ti, dict) and ti.get("source") == prefix:
                        fn_names.append(tn)
                if fn_names:
                    display = srv.get("display_name") or sid
                    result["mcp_toolsets"][display] = {
                        "source": f"mcp:{sid}",
                        "server_id": sid,
                        "enabled": True,
                        "exposure": srv.get("exposure", "secondary"),
                        "parallel_safe": False,
                        "subagent_safe": False,
                        "description": srv.get("description", "") or f"MCP server with {len(fn_names)} tool{'s' if len(fn_names) != 1 else ''}",
                        "functions": fn_names,
                    }

        # ── Individual tools ──
        for tn, ti in cfg.get("tools", {}).items():
            src = ti.get("source", "")
            if src.startswith("mcp:"):
                sid = src[4:]
                srv = servers.get(sid, {}) if isinstance(servers, dict) else {}
                # Skip tools from toolset-mode servers (they're in mcp_toolsets)
                if srv.get("mode", "toolset") == "toolset":
                    continue
                result["mcp"][tn] = {
                    "source": src, "enabled": ti.get("enabled", True),
                    "exposure": ti.get("exposure", "secondary"),
                    "parallel_safe": ti.get("parallel_safe", False),
                    "subagent_safe": ti.get("subagent_safe", False),
                    "description": ti.get("description", "")}
            elif src.startswith("skill:"):
                result["skills"][tn] = {
                    "source": src, "enabled": ti.get("enabled", True),
                    "exposure": ti.get("exposure", "secondary"),
                    "parallel_safe": ti.get("parallel_safe", False),
                    "subagent_safe": ti.get("subagent_safe", False),
                    "description": ti.get("description", "")}
        cm = _config_manager(); ip = cm.config_dir / "index.json"
        if ip.exists():
            try:
                data = json.loads(ip.read_text())
                # Flat‑list format (ToolStore registry)
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
                # Legacy dict format
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
        for name, ts_info in cfg.get("toolsets", {}).items():
            result["toolsets"][name] = {
                "source": ts_info.get("source", f"toolset:{name}"),
                "enabled": True,
                "exposure": ts_info.get("exposure", "secondary"),
                "parallel_safe": False, "subagent_safe": False,
                "description": ts_info.get("description", "")}
        self._json(result)

    def _patch_tool(self, name: str, body: dict):
        cfg = api_mcp.load_config()
        tools = cfg.setdefault("tools", {})
        toolsets = cfg.setdefault("toolsets", {})
        target = tools if name in tools else (toolsets if name in toolsets else None)
        if target is None:
            # Check if name matches an MCP server's display_name or server_id
            servers = cfg.get("mcpServers", {})
            if isinstance(servers, dict):
                for sid, srv in servers.items():
                    if srv.get("display_name") == name or sid == name:
                        res, code = api_mcp.patch_mcp_server(sid, body)
                        return self._json(res, code)
            return self._json({"error": "Tool not found"}, 404)
        for k in ("exposure", "enabled", "parallel_safe", "subagent_safe"):
            if k in body: target[name][k] = body[k]
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
