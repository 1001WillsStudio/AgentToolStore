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
from ..mcp_client import FullMCPClient, disconnect_all

# ── Constants ──

_SPA_MCP_KEY = "mcp_servers"
_CLI_MCP_KEY = "mcpServers"

_DEFAULT_CFG: dict[str, Any] = {
    "mcp_servers": {},
    "tools": {},
    "skills": {},
    "toolsets": {},
}


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
    for k in ("tools", "skills", "toolsets"):
        if k in cm.config:
            cfg[k] = cm.config[k]
    return cfg


def save_config(cfg: dict) -> None:
    cm = _config_manager()
    spa_servers = cfg.get(_SPA_MCP_KEY, {})
    if spa_servers:
        cm.config[_CLI_MCP_KEY] = dict(spa_servers)
    cm.config["tools"] = cfg.get("tools", {})
    cm.config["skills"] = cfg.get("skills", {})
    cm.config["toolsets"] = cfg.get("toolsets", {})
    cm.save()


# ── MCP connection state ──

_connected_clients: dict[str, FullMCPClient] = {}
_mcp_processes: dict[str, subprocess.Popen] = {}


def mcp_status(server_id: str) -> str:
    return "connected" if server_id in _connected_clients else "disconnected"


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
    _connected_clients[server_id] = client
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
    client = _connected_clients.pop(server_id, None)
    if client:
        try: client.disconnect()
        except Exception: pass


def disconnect_all_clients() -> None:
    for cid in list(_connected_clients.keys()):
        disconnect_server(cid)
    for pid in list(_mcp_processes.keys()):
        shutdown_mcp_process(pid)
    try: disconnect_all()
    except Exception: pass


def count_mcp_tools(cfg: dict, server_id: str) -> int:
    prefix = f"mcp:{server_id}"
    return sum(1 for v in cfg.get("tools", {}).values()
               if v.get("source") == prefix)
