# ToolStore Client

<p align="center">
  <strong>The SDK that gives any AI agent instant access to every published toolset
  through a single <code>tool_store</code> function.</strong>
</p>

---

The ToolStore client is the package you install into your agent environment.
It provides four things:

| Component | What it does |
|-----------|-------------|
| **`tool_store_tool()`** | The single function agents call to search, inspect, and execute toolsets |
| **CLI** | `toolstore update`, `toolstore use`, `toolstore publish`, … |
| **Management UI** | `toolstore serve` — web dashboard for tools, skills, MCP servers |
| **MCP bridge** | `toolstore mcp-server serve` — expose ToolStore as an MCP server |

For the full project overview, see the [main README](../README.md).

---

## Installation

```bash
pip install toolstore
```

Or from source:

```bash
git clone https://github.com/Mrw33554432/AgentToolStore.git
cd AgentToolStore/client
pip install -e .
```

Requirements: Python ≥3.10, `httpx`, `pydantic`, `rich`, `typer`.

---

## For Agent Developers

### `tool_store_tool()` — the agent entry point

Add one tool to your agent's function-calling schema and wire one handler.
The agent can then search, inspect, and execute every toolset on the registry:

```python
from toolstore.native_tool import tool_store_tool

# In your agent's tool-call router:
def handle_tool_call(tool_name: str, arguments: dict) -> str:
    if tool_name == "tool_store":
        return tool_store_tool(**arguments)
    # ... other tools
```

The `tool_store` tool accepts these actions:

| Action | Returns |
|--------|---------|
| `search` | List of toolsets matching a query string |
| `info` | Full toolset definition — bindings, parameters, docstrings, source code |
| `execute` | JSON result from running a toolset function in-process |

Execution is **in-process** — code is fetched from the registry on demand,
written to a temp directory, dependencies installed explicitly (never
auto-installed), imported, and called. No Docker needed.

### Tool definition schema

```python
TOOL_STORE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tool_store",
        "description": (
            "A universal tool manager that lets you search, inspect, "
            "and execute thousands of tools and local utilities."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "info", "execute"],
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for action='search')",
                },
                "tool_name": {
                    "type": "string",
                    "description": "Toolset name (for action='info' or 'execute')",
                },
                "arguments": {
                    "type": "object",
                    "description": (
                        "Arguments for the tool function. Must include "
                        "'function' key naming the function to call."
                    ),
                },
            },
            "required": ["action"],
        },
    },
}
```

### Local execution (no registry)

Call a toolset directly from a local directory without any registry:

```python
from toolstore.exec_tools import _execute_toolset_local

result = _execute_toolset_local(
    toolset_path="./toolsets/xlsx-toolkit",
    function_name="xlsx_read",
    filepath="/workspace/data.xlsx",
)
```

---

## For Toolset Authors

### The `@tool` decorator

Write a Python file with `@tool`-decorated functions. The decorator
auto-generates an OpenAI function-calling schema from type hints and docstrings:

```python
from toolstore.toolset import tool

@tool
def my_function(*, input: str, count: int = 1) -> dict:
    """Do something useful.

    Args:
        input: The input text.
        count: How many times to repeat.
    """
    return {"result": input * count}
```

Rules:
- Use **keyword-only arguments** (`*,`)
- Annotate every parameter with a **type hint**
- Write a **Google-style docstring** with `Args:` section
- Return a **JSON-serializable dict**
- Put **dependencies** in a `requirements.txt` next to `toolset.py`

### Publishing

```bash
# Authenticate
toolstore login --username <user> --password <pass>

# Publish your toolset
toolstore toolset publish ./toolsets/my-toolkit

# Delete if needed
toolstore delete my-toolkit
```

The publish command uses AST analysis to detect `@tool`-decorated functions
and bundles them with your `doc.md` and `requirements.txt` automatically.
No manual JSON schemas needed.

---

## CLI Reference

```bash
# Discovery
toolstore update                         # pull latest registry index
toolstore search "spreadsheet"           # search toolsets

# Inspection
toolstore info xlsx-toolkit              # full schema, bindings, docs

# Execution
toolstore use text-transform \
    --function text_stats text="Hello."  # run a function

# Publishing
toolstore login --username <u> --password <p>
toolstore toolset publish ./path/to/toolkit
toolstore delete my-toolkit

# Management UI
toolstore serve                          # web dashboard on :8765

# MCP bridge
toolstore mcp-server serve               # expose ToolStore via MCP (stdio)

# Export
toolstore export                         # meta-tool schema for OpenAI/vLLM

# Skills
toolstore skill discover /path/to/skills
toolstore skill list
```

### All commands

| Command | Description |
|---------|-------------|
| `update` | Pull the latest registry index and scan local MCP servers |
| `search` | Search for tools by name, description, or tags |
| `use` | Execute a tool function and print the result |
| `info` | Show detailed schema and documentation |
| `login` | Authenticate with the registry |
| `publish` | Publish or update a tool |
| `delete` | Remove a tool from the registry |
| `export` | Export the meta-tool schema (OpenAI / vLLM) |
| `serve` | Start the management web UI |
| `skill` | Discover, list, and register Agent Skills |
| `toolset` | Publish, list, and inspect toolsets |
| `mcp-server` | Register and manage MCP servers |
| `docker` | Configure Docker execution permissions |

---

## Management UI

`toolstore serve` starts a web dashboard at `http://127.0.0.1:8765`:

- **Tools tab** — view all active tools across MCP, skills, and toolsets
- **MCP Servers tab** — add/remove/connect MCP servers
- **Skills tab** — upload ZIPs or register skill directories
- **Toolsets tab** — register local toolsets, download from registry
- **Registry tab** — browse published toolsets on the registry

The UI is a single-page app (`management/static/index.html` + `app.js`) with
a REST API served by the built-in `ManagementServer` class.

---

## MCP Bridge

The client can act as an MCP server (`toolstore mcp-server serve`), exposing
the full ToolStore ecosystem to any MCP-compatible host (Claude Desktop,
Continue, etc.):

- **stdio** mode — for local MCP hosts
- **SSE** mode — `toolstore mcp-server serve --transport sse --port 9090`

The MCP client (`mcp_client.py`) handles connecting to third-party MCP servers
over stdio, SSE, or streamable-HTTP transports.

---

## Skills Integration

The client also manages Agent Skills (`skills-general/` format: `SKILL.md`
per skill). Use `toolstore skill discover` to scan directories, `toolstore
skill list` to view registered skills. Skills appear as `skill:<name>` tools
in the agent's tool list.

---

## Module Map

```
client/src/toolstore/
├── native_tool.py           # tool_store_tool() — agent-facing entry point
├── exec_tools.py            # In-process toolset execution (local + remote)
├── toolset.py               # @tool decorator + OpenAI schema generation
├── toolset_manager.py       # AST-based toolset discovery & publishing
├── cli.py                   # Typer CLI — all commands
├── config_manager.py        # Settings, registry URL, env-var overrides
├── mcp_client.py            # MCP client (stdio / SSE / streamable-HTTP)
├── mcp_server.py            # MCP server — expose ToolStore via MCP
├── transport.py             # Transport layer (stdio, SSE, HTTP)
├── index_manager.py         # Local index cache
├── schema_converter.py      # Convert ToolStore schemas to OpenAI format
├── skill_manager.py         # Agent Skills loader + registration
├── skill_discovery.py       # Skill directory scanner
├── docker_pool.py           # Docker container pool (optional)
└── management/              # Web UI
    ├── server.py            # ManagementServer — REST API + SPA
    ├── api_helpers.py       # Config load/save, MCP connection helpers
    ├── api_mcp.py           # MCP server CRUD endpoints
    ├── api_skills.py        # Skill registration endpoints
    └── static/
        └── app.js           # SPA frontend
```

---

## Configuration

Settings are stored at `~/.toolstore/settings.json` (or `$TOOLSTORE_DIR/settings.json`).
Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `registry_url` | HF Space | Registry index endpoint |
| `mcpServers` | `{}` | Registered MCP servers |
| `skill_dirs` | `[]` | Directories scanned for skills |
| `toolset_dirs` | `[]` | Directories scanned for toolsets |
| `tools` | `{}` | Per-tool exposure / enabled config |
| `server` | `{}` | MCP server mode config |

Override the registry URL via environment variable:

```bash
export TOOLSTORE_REGISTRY_URL=https://localhost:8000/index.json
```

---

## License

MIT — see [LICENSE](../LICENSE)
