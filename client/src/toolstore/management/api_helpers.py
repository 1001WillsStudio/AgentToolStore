"""
Shared helpers for the management server API handlers.

- Config I/O (load / save with camelCase ↔ snake_case normalisation)
- MCP connection helpers
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from ..config_manager import ConfigManager
from ..mcp_client import FullMCPClient, disconnect_all, _connection_pool, _pool_lock

# ── Constants ──

_SPA_MCP_KEY = "mcp_servers"
_CLI_MCP_KEY = "mcpServers"

_DEFAULT_CFG: dict[str, Any] = {
    "mcp_servers": {},
    "skill_cache": {},
    "toolsets": {},
}


def _migrate_tools(cfg: dict[str, Any]) -> None:
    """One‑shot: move legacy ``cfg["tools"]`` entries to their correct homes.

    * MCP tools (``source`` starts with ``mcp:``) → ``cfg["mcpServers"][sid]["tools"]``
    * Skills (``source`` starts with ``skill:``) → ``cfg["skill_cache"]``

    Idempotent — after migration ``cfg["tools"]`` is deleted.
    """
    if "tools" not in cfg:
        return
    tools = cfg.pop("tools")
    for name, info in tools.items():
        if not isinstance(info, dict):
            continue
        source = info.get("source", "")
        if source.startswith("mcp:"):
            sid = source[4:]
            srv = cfg.setdefault("mcpServers", {}).setdefault(sid, {})
            srv.setdefault("tools", {})[name] = info
        elif source.startswith("skill:"):
            skill_name = name[len("skill:"):] if name.startswith("skill:") else name
            cfg.setdefault("skill_cache", {})[skill_name] = info


def _config_manager() -> ConfigManager:
    cm = ConfigManager()
    cm.load()
    return cm


def load_config() -> dict:
    cfg = dict(_DEFAULT_CFG)
    cm = _config_manager()
    cli_servers = cm.config.get(_CLI_MCP_KEY, {})
    if cli_servers:
        cfg[_SPA_MCP_KEY] = dict(cli_servers)
    for k in ("skill_cache", "toolsets"):
        if k in cm.config:
            cfg[k] = cm.config[k]
    # Legacy migration: move cfg["tools"] → cfg["mcpServers"][sid]["tools"] / cfg["skill_cache"]
    if "tools" in cm.config:
        cfg_tmp = dict(cfg)
        cfg_tmp["tools"] = cm.config["tools"]
        _migrate_tools(cfg_tmp)
        # Merge migrated entries back into cfg
        for sid, srv in cfg_tmp.get("mcpServers", {}).items():
            if sid not in cfg["mcp_servers"]:
                cfg["mcp_servers"][sid] = srv
            else:
                cfg["mcp_servers"][sid].setdefault("tools", {}).update(srv.get("tools", {}))
        for sn, si in cfg_tmp.get("skill_cache", {}).items():
            cfg["skill_cache"][sn] = si
    return cfg


def save_config(cfg: dict) -> None:
    cm = _config_manager()
    spa_servers = cfg.get(_SPA_MCP_KEY, {})
    if spa_servers:
        cm.config[_CLI_MCP_KEY] = dict(spa_servers)
    cm.config["skill_cache"] = cfg.get("skill_cache", {})
    cm.config["toolsets"] = cfg.get("toolsets", {})
    # Purge legacy key so it doesn't stick around
    cm.config.pop("tools", None)
    cm.save()


# ── MCP connection state ──

_mcp_processes: dict[str, subprocess.Popen] = {}


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
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()
    except Exception: pass


def disconnect_server(server_id: str) -> None:
    shutdown_mcp_process(server_id)
    with _pool_lock:
        client = _connection_pool.pop(server_id, None)
    if client:
        try: client.disconnect()
        except Exception: pass


def disconnect_all_clients() -> None:
    with _pool_lock:
        server_ids = list(_connection_pool.keys())
    for cid in server_ids:
        disconnect_server(cid)
    for pid in list(_mcp_processes.keys()):
        shutdown_mcp_process(pid)
    try: disconnect_all()
    except Exception: pass


def count_mcp_tools(cfg: dict, server_id: str) -> int:
    return len(cfg.get("mcp_servers", {}).get(server_id, {}).get("tools", {}))
