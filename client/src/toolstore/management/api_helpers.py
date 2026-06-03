"""
Shared helpers for the management API.

Consolidates all MCP / Skill / Toolset state into
:class:`~toolstore.index_manager.IndexManager` (``local_registry.json``).
``settings.json`` is reserved for four config keys only:
``registry_url``, ``skill_dirs``, ``toolset_dirs``, ``auth_token``.
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from ..config_manager import ConfigManager
from ..index_manager import IndexManager
from ..mcp_client import FullMCPClient

import logging
logger = logging.getLogger(__name__)

_SPA_MCP_KEY = "mcp_servers"
_CLI_MCP_KEY = "mcpServers"

_CM_SINGLETON: ConfigManager | None = None
_IM_SINGLETON: IndexManager | None = None

# MCP connection state
_pool_lock = threading.Lock()
_connection_pool: dict[str, FullMCPClient] = {}
_mcp_processes: dict[str, subprocess.Popen] = {}


def _config_manager() -> ConfigManager:
    global _CM_SINGLETON
    if _CM_SINGLETON is None:
        _CM_SINGLETON = ConfigManager()
    return _CM_SINGLETON


def _index_manager() -> IndexManager:
    global _IM_SINGLETON
    if _IM_SINGLETON is None:
        _IM_SINGLETON = IndexManager()
    return _IM_SINGLETON


def refresh_config() -> None:
    """Force the ConfigManager singleton to reload from disk.

    Call this after any external modification (e.g. WebUI writes) to ensure
    subsequent reads see the latest data.
    """
    _config_manager().load()


def refresh_index() -> None:
    """Force the IndexManager singleton to reload local state from disk.

    Call this after any external modification (e.g. WebUI writes) to ensure
    subsequent reads see the latest data.
    """
    _index_manager().reload()


# ── migration from settings.json to local_registry.json ──────────────

def _migrate_from_settings(im: IndexManager) -> None:
    """One‑shot: move legacy MCP servers & skills from settings.json → local_registry.json."""
    cm = _config_manager()
    cm.load()
    
    mcp = cm.config.pop(_CLI_MCP_KEY, {})
    if mcp and not im._local_mcp:
        im._local_mcp = mcp
        
    skills = cm.config.pop("skills", {})
    if skills and not im._local_skills:
        im._local_skills.update(skills)
        
    cm.config.pop("tools", None)
    cm.config.pop("toolsets", None)
    
    if mcp or skills:
        im._save_local()
        cm.save()


# ── primary I/O ──────────────────────────────────────────────────────

def load_config() -> dict:
    """Return a merged view: tool data from IndexManager + settings from ConfigManager."""
    im = _index_manager()
    im.reload()
    
    _migrate_from_settings(im)
    
    cm = _config_manager()
    cm.load()
    
    cfg: dict[str, Any] = {
        "mcp_servers": dict(im._local_mcp),
        "skills": dict(im._local_skills),
        "toolsets": dict(im._local_tools),
    }
    for k in ("registry_url", "skill_dirs", "toolset_dirs", "auth_token"):
        if k in cm.config:
            cfg[k] = cm.config[k]
    return cfg


def save_config(cfg: dict) -> None:
    """Persist tool data → IndexManager, settings → ConfigManager."""
    im = _index_manager()
    im.reload()
    im._local_mcp = cfg.get("mcp_servers", {})
    im._local_skills = cfg.get("skills", {})
    im._local_tools = cfg.get("toolsets", {})
    im._save_local()
    
    cm = _config_manager()
    for k in ("registry_url", "skill_dirs", "toolset_dirs", "auth_token"):
        if k in cfg:
            cm.config[k] = cfg[k]
    cm.save()


# ── MCP helpers ──────────────────────────────────────────────────────

def count_mcp_tools(cfg: dict, server_id: str) -> int:
    return len(cfg.get("mcp_servers", {}).get(server_id, {}).get("tools", {}))


# ── MCP connection state ── (pool + processes shared with tab_mcp)


def mcp_status(server_id: str) -> str:
    """Check if an MCP server is connected, using the authoritative pool."""
    client = _connection_pool.get(server_id)
    if client is not None and client.is_connected():
        return "connected"
    # Prune stale entries
    if client is not None:
        with _pool_lock:
            _connection_pool.pop(server_id, None)
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


def connect_and_discover(server_id: str, srv: dict) -> list[dict]:
    transport_type = srv.get("transport") or srv.get("type")
    if not transport_type:
        transport_type = "stdio" if srv.get("command") else "sse"
    if transport_type == "folder":
        _start_mcp_folder(server_id, srv)
        time.sleep(1.5)
        sub_transport = srv.get("sub_transport", "sse")
        url = srv.get("url", "")
    elif transport_type == "docker":
        sub_transport, url = "docker", ""
    else:
        sub_transport, url = transport_type, srv.get("url", "")
    client = FullMCPClient(server_id, {
        "type": sub_transport, "transport": sub_transport,
        "command": srv.get("command", ""),
        "args": srv.get("args", []),
        "url": url, "env": srv.get("env", {}),
        "timeout": srv.get("timeout", 30),
        "image": srv.get("image", ""),
        "entrypoint": [srv.get("command", "python")] + srv.get("args", []),
    })
    client.connect()
    tools_info = client.list_tools()
    with _pool_lock:
        _connection_pool[server_id] = client
    tool_list = tools_info.get("tools", []) if isinstance(tools_info, dict) else (
        tools_info if isinstance(tools_info, list) else [])
    tools: list[dict] = []
    for t in tool_list:
        tools.append({
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "parameters": t.get("inputSchema", t.get("parameters", {})),
        })
    return tools


def shutdown_mcp_process(server_id: str) -> None:
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
        logger.debug("Suppressed exception in api_helpers.py", exc_info=True)
        pass


def disconnect_server(server_id: str) -> None:
    shutdown_mcp_process(server_id)
    with _pool_lock:
        client = _connection_pool.pop(server_id, None)
    if client:
        try:
            client.disconnect()
        except Exception:
            logger.debug("Suppressed exception in api_helpers.py", exc_info=True)
            pass


def disconnect_all_clients() -> None:
    """Disconnect all MCP clients and terminate child processes."""
    with _pool_lock:
        server_ids = list(_connection_pool.keys())
    for cid in server_ids:
        disconnect_server(cid)
    for pid in list(_mcp_processes.keys()):
        shutdown_mcp_process(pid)
