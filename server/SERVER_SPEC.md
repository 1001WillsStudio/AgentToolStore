# ToolStore — Architecture

## Two-registry design

```
online_registry.json   ←── save()            ──► remote toolsets only
local_registry.json    ←── _save_local()    ──► local toolsets + skills + MCP
                          │
          _all_tools() ── merge at query time only ── search / execute
```

The two registries **never touch each other**. `save()` only writes `online_registry.json`. `_save_local()` only writes `local_registry.json`. Merging happens exclusively in `_all_tools()`, which is called by every query method (`search`, `get_tool`, `list_by_type`, `get_all`, `count`).

## online_registry.json

- **Single writer**: `update_from_remote()` at `index_manager.py`, called ONLY from the remote fetch path (`cli.py` → `cmd_update`).
- **Never locally edited**. No `register_tool`, no `unregister_tool` — those were removed.
- Contents: remote toolsets with `type: "toolset"`, `source: "public"`, and the `code` field included.
- Served by the online server at `GET /index.json`.

## local_registry.json

- Persisted to disk — scanned once, cached, re-scanned only on explicit `update` / `scan`.
- Written by three methods:
  - `discover_local_toolsets(dirs)` — scans toolset directories, reads `toolset.py` + `doc.md`, stores `toolset_dir` path
  - `update_local_skills(defs)` — merges skill definitions into local
  - `register_local_tool(tool)` — single-tool registration (MCP servers)
- Contents: `type: "toolset"` (with `toolset_dir`), `type: "skill"`, `type: "mcp"`, `source: "local"`

## Supported tool types

| Type     | Registry | How executed |
|----------|----------|--------------|
| `toolset` (remote) | online | `code` field loaded from index |
| `toolset` (local)  | local  | `toolset_dir`/`toolset.py` read from disk |
| `skill`  | local  | Skill runner (local) |
| `mcp`    | local  | MCP transport |
| ~~`api`~~ | ~~removed~~ | Dead, fully stripped from code |

## Execution dispatch

```
tool_store execute
  │
  ├─ toolset + code      → exec_tools._execute_toolset_remote()
  ├─ toolset + toolset_dir → exec_tools._execute_toolset_local()  ← reads toolset.py from disk
  ├─ mcp                → exec_tools._execute_mcp()
  └─ skill              → exec_tools._execute_skill()
```

## Publish flow

1. `toolset publish <name>` → AST-parses `toolset.py`, bundles `@tool` functions + `doc.md`
2. Sends `{name, type, code, doc, bindings}` to `POST /publish` on the online server
3. Server stores in SQLite, serves via `GET /index.json`

## Update flow (`toolstore update`)

1. Fetch remote `index.json` → `update_from_remote()` → `online_registry.json`
2. Scan local toolset dirs → `discover_local_toolsets()` → `local_registry.json`
3. Scan skills → `update_local_skills()` → `local_registry.json`
4. Scan MCP servers → `register_local_tool()` → `local_registry.json`

Steps 2–4 write to `local_registry.json` only. Step 1 writes to `online_registry.json` only. Neither path touches the other file.

## Server API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/index.json` | Full remote registry |
| `POST` | `/publish` | Publish a toolset |
| `DELETE` | `/tools/{name}` | Delete a toolset |
| `POST` | `/auth/register` | Register account |
| `POST` | `/auth/token` | Login |
| `GET`  | `/health` | Health check |

## Dependencies

Toolsets declare deps by guarding imports inside each function with `try/except ImportError`:

```python
@tool
def do_thing(*, path: str) -> dict:
    try:
        from some_package import Thing
    except ImportError:
        return {"error": "some-package not installed — run: pip install some-package"}
    ...
```

No `requirements.txt` is read or bundled by the publish pipeline.
