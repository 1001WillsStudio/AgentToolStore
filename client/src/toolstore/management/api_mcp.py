"""
MCP server API handlers.

- GET    /api/mcp/servers           list
- POST   /api/mcp/servers           add
- POST   /api/mcp/servers/<id>/connect
- POST   /api/mcp/servers/<id>/disconnect
- DELETE /api/mcp/servers/<id>      remove
- PATCH  /api/mcp/servers/<id>      update exposure/display_name
"""

from __future__ import annotations

from typing import Any

from .api_helpers import (
    connect_and_discover, count_mcp_tools, disconnect_server,
    load_config, mcp_status, save_config,
)


def list_mcp_servers() -> dict:
    """GET /api/mcp/servers"""
    cfg = load_config()
    servers = cfg.get("mcp_servers", {})
    out = {}
    for sid, srv in servers.items():
        entry = dict(srv)
        entry["status"] = mcp_status(sid)
        entry["tools_count"] = count_mcp_tools(cfg, sid)
        out[sid] = entry
    return out


def add_mcp_server(body: dict) -> dict:
    """POST /api/mcp/servers"""
    sid = body.get("server_id", "").strip()
    if not sid:
        return {"error": "server_id is required"}, 400

    cfg = load_config()
    servers = cfg.setdefault("mcp_servers", {})
    if sid in servers:
        return {"error": "Server already exists"}, 409

    transport = body.get("transport", "sse")
    mode = body.get("mode", "toolset")  # "toolset" or "individual"
    exposure = body.get("exposure", "secondary")
    display_name = body.get("display_name", "").strip() or sid
    srv: dict[str, Any] = {
        "transport": transport,
        "enabled": body.get("enabled", True),
        "auto_connect": body.get("auto_connect", True),
        "exposure": exposure,
        "display_name": display_name,
        "mode": mode,
    }
    # When mode is "toolset", individual tools are hidden; server-level
    # exposure controls visibility of the whole server as a grouped toolset.
    # When mode is "individual", each tool has its own exposure and the
    # server-level exposure is irrelevant.
    tool_exposure = "hidden" if mode == "toolset" else exposure
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
            tools = connect_and_discover(sid, srv)
            srv_tools = cfg.setdefault("mcp_servers", {}).setdefault(sid, {}).setdefault("tools", {})
            for t in tools:
                tn = t["name"]
                srv_tools[tn] = {
                    "name": tn,
                    "source": f"mcp:{sid}",
                    "enabled": True,
                    "exposure": tool_exposure,
                    "parallel_safe": False,
                    "subagent_safe": False,
                    "description": t.get("description", ""),
                    "inputSchema": t.get("parameters", {}),
                }
            save_config(cfg)
        except Exception as exc:
            conn_err = str(exc)

    return {
        "success": True, "server_id": sid,
        "tools_discovered": len(tools), "tools": tools,
        "connection_error": conn_err,
    }, 200


def connect_mcp_server(sid: str) -> dict:
    """POST /api/mcp/servers/<id>/connect"""
    cfg = load_config()
    servers = cfg.get("mcp_servers", {})
    if sid not in servers:
        return {"error": "Server not found"}, 404

    srv = servers[sid]
    tools = connect_and_discover(sid, srv)
    mode = srv.get("mode", "toolset")
    exposure = srv.get("exposure", "secondary")
    tool_exposure = "hidden" if mode == "toolset" else exposure
    srv_tools = cfg.setdefault("mcp_servers", {}).setdefault(sid, {}).setdefault("tools", {})
    for t in tools:
        tn = t["name"]
        if tn not in srv_tools:
            srv_tools[tn] = {
                "name": tn,
                "source": f"mcp:{sid}",
                "enabled": True,
                "exposure": tool_exposure,
                "parallel_safe": False,
                "subagent_safe": False,
                "description": t.get("description", ""),
                "inputSchema": t.get("parameters", {}),
            }
    save_config(cfg)
    return {"success": True, "tools": tools}, 200


def disconnect_mcp_server(sid: str) -> dict:
    """POST /api/mcp/servers/<id>/disconnect"""
    disconnect_server(sid)
    return {"success": True}, 200


def remove_mcp_server(sid: str) -> dict:
    """DELETE /api/mcp/servers/<id>"""
    cfg = load_config()
    if sid not in cfg.get("mcp_servers", {}):
        return {"error": "Server not found"}, 404

    disconnect_server(sid)
    del cfg["mcp_servers"][sid]

    # Tools are stored under cfg["mcp_servers"][sid]["tools"] —
    # deleting the server above removes them automatically.
    save_config(cfg)
    return {"success": True}, 200


def patch_mcp_server(server_id: str, body: dict) -> dict:
    """PATCH /api/mcp/servers/<id>"""
    cfg = load_config()
    servers = cfg.get("mcp_servers", {})
    if server_id not in servers:
        return {"error": "MCP server not found"}, 404

    srv = servers[server_id]
    updated = {}

    if "mode" in body:
        new_mode = body["mode"]
        if new_mode not in ("toolset", "individual"):
            return {"error": "mode must be 'toolset' or 'individual'"}, 400
        old_mode = srv.get("mode", "toolset")
        srv["mode"] = new_mode
        updated["mode"] = new_mode
        if new_mode == "toolset" and old_mode != "toolset":
            for tn, ti in srv.get("tools", {}).items():
                if isinstance(ti, dict):
                    ti["exposure"] = "hidden"
        elif new_mode == "individual" and old_mode != "individual":
            exp = srv.get("exposure", "secondary")
            for tn, ti in srv.get("tools", {}).items():
                if isinstance(ti, dict):
                    ti["exposure"] = exp

    if "exposure" in body:
        srv["exposure"] = body["exposure"]
        updated["exposure"] = body["exposure"]
        # Only sync tool exposures when mode is "individual"
        if srv.get("mode", "toolset") == "individual":
            synced = 0
            for tn, ti in srv.get("tools", {}).items():
                if isinstance(ti, dict):
                    ti["exposure"] = body["exposure"]
                    synced += 1
            updated["tools_synced"] = synced

    if "display_name" in body:
        srv["display_name"] = body["display_name"].strip()
        updated["display_name"] = srv["display_name"]

    save_config(cfg)
    return {"success": True, "server": server_id, **updated}, 200
