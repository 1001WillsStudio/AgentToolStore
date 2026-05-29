---
title: AgentToolStore Registry
emoji: 🛠️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

<p align="center">
  <img src="https://img.shields.io/badge/toolsets-14-blue" alt="14 toolsets">
  <img src="https://img.shields.io/badge/functions-46-brightgreen" alt="46 functions">
  <img src="https://img.shields.io/badge/license-MIT-purple" alt="MIT">
  <img src="https://img.shields.io/badge/package-toolstore-orange" alt="toolstore">
  <img src="https://img.shields.io/badge/registry-live-brightgreen" alt="live">
</p>

# AgentToolStore

**A package index for agent tools.** PyPI for Python packages, npm for
JavaScript — ToolStore does the same for agent-callable toolsets. Agents
discover tools through a single `tool_store` function instead of wiring up
dozens of tools by hand.

→ **[Client SDK docs](client/README.md)** — installing, integrating into agents, CLI, MCP bridge, skills
→ **[Registry server docs](server/README.md)** — API endpoints, running locally, deploying on HF Spaces

> **Live registry:** [mrw33554432-agenttoolstore.hf.space](https://mrw33554432-agenttoolstore.hf.space)

---

## How it works

```
toolstore update                     ← downloads index.json from registry
       │
       ▼
┌─────────────────────────┐
│  Local index cache       │  ← search and info read from here (no network)
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│  tool_store(execute)     │  ← fetches code from registry on demand
│  → temp dir → import     │     runs in-process, no Docker
│  → call function → JSON  │
└─────────────────────────┘
```

1. **`toolstore update`** pulls the registry index and caches it locally
2. **`search` / `info`** read from the local cache — instant, no network
3. **`execute`** fetches code from the registry, installs deps explicitly,
runs in-process, returns JSON

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

## Adding to Your Agent

Add one tool definition and one handler. The agent discovers every published
toolset through a single `tool_store` call.

### How it fits into an agent loop

```
System prompt                         Tool call loop
─────────────────────────────────     ─────────────────────────────────
"Tool store includes but not          1. Agent calls tool_store(search)
 limited to: Echo Service,                → discovers xlsx-toolkit
 calculator, weather, ..."
                                      2. Agent calls tool_store(info)
                                         → gets xlsx_read params + docs

                                      3. Agent calls tool_store(execute)
                                         → runs xlsx_read, gets result

                                      4. Agent calls tool_store(close)
                                         → frees context space
```

### 1. Tool definition

Register this in your agent's function-calling tool list:

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
                    "enum": ["search", "execute", "info", "close"],
                    "description": (
                        "The action to perform: 'search' finds tools "
                        "matching a query; 'execute' runs a tool; "
                        "'info' adds a tool to your context so you can "
                        "see its parameters; 'close' removes it."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": "Search query string (for action='search')",
                },
                "tool_name": {
                    "type": "string",
                    "description": (
                        "Name of the tool to inspect, execute, or close "
                        "(required for action='info', 'execute', or 'close')"
                    ),
                },
                "arguments": {
                    "type": "object",
                    "description": (
                        "Arguments for the tool execution "
                        "(required for action='execute')"
                    ),
                },
            },
            "required": ["action"],
        },
    },
}
```

### 2. Handler

Wire the native function into your tool-call router. The native function
handles `search`, `info`, and `execute` — add a small shim for `close`:

```python
from toolstore.native_tool import tool_store_tool

def handle_tool_store(action: str, **kwargs) -> str:
    if action == "close":
        return f"Closed tool '{kwargs.get('tool_name', '')}'."
    return tool_store_tool(action=action, **kwargs)
```

### 3. Secondary tools prompt

Most tools are `exposure: secondary` — too many to list in every system
message. Inject a compact listing into the system prompt instead. Call
`get_secondary_tool_names()` then `info` with `format="secondary"`:

```python
from toolstore.native_tool import get_secondary_tool_names, tool_store_tool

names = get_secondary_tool_names()
listing = tool_store_tool(action="info", tool_names=names, format="secondary")
system_prompt += f"\n\n{listing}"
```

Produces:

```
Tool store includes but is not limited to the following tools:
- Echo Service
- calculator
- weather
- skill:algorithmic-art
...
```

The agent sees names; when it needs a tool it calls `info` again (without
`format="secondary"`) for the full schema, then `execute`.

### 4. Agent conversation example

```
Agent: tool_store(action="search", query="read Excel files")
  → Found: xlsx-toolkit — Read, create, and manipulate Excel files

Agent: tool_store(action="info", tool_name="xlsx-toolkit")
  → Returns bindings for xlsx_read, xlsx_sheets, xlsx_to_csv, xlsx_create
    with parameter types and docstrings for each

Agent: tool_store(action="execute", tool_name="xlsx-toolkit",
                  arguments={"function": "xlsx_read",
                             "filepath": "/workspace/report.xlsx"})
  → {"sheets": ["Sheet1"], "data": {"Sheet1": [[...], ...]}}

Agent: tool_store(action="close", tool_name="xlsx-toolkit")
  → Closed tool 'xlsx-toolkit'.
```

### 4. Execution model

| Property | Behaviour |
|----------|-----------|
| **Runtime** | In-process — no Docker, no sandbox |
| **Code origin** | Fetched from registry, cached after first download |
| **Dependencies** | Never auto-installed; agent gets a clear error listing what's needed |
| **Isolation** | Each toolset runs in its own temp directory |
| **Safety** | All code is visible in the registry; deps are explicit; agent decides what to install |

### 5. Local execution (no registry)

Skip the registry entirely and call toolsets from a local directory:

```python
from toolstore.exec_tools import _execute_toolset_local

result = _execute_toolset_local(
    toolset_path="./toolsets/xlsx-toolkit",
    function_name="xlsx_read",
    filepath="/workspace/data.xlsx",
)
```

---

## CLI Usage

```bash
# Pull the latest index from the registry
toolstore update

# Search for tools
toolstore search "spreadsheet"

# Inspect a toolset
toolstore info xlsx-toolkit

# Execute a function
toolstore use text-transform --function text_stats text="Hello world."

# Publish your own toolset
toolstore login --username <user> --password <pass>
toolstore toolset publish ./toolsets/my-toolkit

# Delete a toolset
toolstore delete my-toolkit

# Run ToolStore as an MCP server (stdio or SSE)
toolstore serve

# Export the tool_store schema for use with OpenAI / vLLM
toolstore export

# Manage skills
toolstore skill discover /path/to/skills
toolstore skill list
```

Full command reference:

| Command | Description |
|---------|-------------|
| `update` | Pull the latest registry index and scan local MCP servers |
| `search` | Search for tools by name, description, or tags |
| `use` | Execute a tool function immediately |
| `info` | Show detailed schema and documentation for a tool |
| `login` | Authenticate with the registry to publish |
| `publish` | Publish a new tool or update an existing one |
| `delete` | Remove a tool from the registry |
| `export` | Export the meta-tool schema (OpenAI / vLLM formats) |
| `serve` | Run ToolStore as an MCP server (stdio or SSE) |
| `skill` | Manage Agent Skills (discover, list, create) |
| `toolset` | Manage toolsets (publish, list, inspect) |
| `mcp-server` | Register and manage MCP servers |
| `docker` | Configure Docker execution permissions |

---

## Writing a Toolset

A toolset is a directory with two files:

```
my-toolkit/
├── toolset.py    # @tool functions (code bindings)
└── doc.md        # human + agent guidance
```

### toolset.py

Every function decorated with `@tool` becomes a callable binding. The decorator
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
- Write a **Google-style docstring** with an `Args:` section
- Return a **JSON-serializable dict**
- Put **dependencies** in `requirements.txt` next to `toolset.py`

### Two kinds of toolsets

| Type | `toolset.py` | `doc.md` | Example |
|------|-------------|----------|---------|
| **Code** | Real `@tool` functions | Full docs | `xlsx-toolkit`, `file-verify` |
| **Doc-only** | Minimal empty module | Full guidance | `stuck-toolkit` |

Doc-only toolsets are valid — they carry skill content without code bindings.
No placeholder functions allowed. Code or nothing.

---

## Registry API

The registry is a FastAPI server backed by SQLite, hosted on Hugging Face
Spaces. All endpoints are public except auth and publish.

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | Browse page (HTML) — dark-themed cards showing all published toolsets |
| `/api` | GET | No | API root |
| `/health` | GET | No | Health check — database connectivity status |
| `/index.json` | GET | No | Full index — every toolset with metadata, bindings, and full source code |
| `/auth/register` | POST | No | Register a new user account |
| `/auth/token` | POST | No | Login — returns JWT access token (OAuth2 password flow) |
| `/publish` | POST | JWT | Publish a new toolset or update an existing one |
| `/tools/{name}` | DELETE | JWT | Delete a toolset |

### Running your own registry

```bash
cd server
pip install -r requirements.txt
python init_db.py          # create SQLite database
uvicorn app.main:app --port 8000
```

Set `TOOLSTORE_REGISTRY_URL=http://localhost:8000/index.json` to point the
CLI at your local registry. The default is the public HF Space.

---

## Toolsets Catalog

All 14 toolsets published on the live registry.

### Document processing

| Toolset | Functions | Dependencies |
|---------|-----------|-------------|
| **xlsx-toolkit** | `xlsx_read` · `xlsx_sheets` · `xlsx_to_csv` · `xlsx_create` | `openpyxl` |
| **pdf-toolkit** | `pdf_extract` · `pdf_meta` · `pdf_merge` · `pdf_form_fields` | `pdfplumber`, `PyPDF2` |
| **docx-toolkit** | `docx_read` · `docx_info` · `docx_extract_tables` · `docx_create` | `python-docx` |
| **pptx-toolkit** | `pptx_read` · `pptx_info` · `pptx_create` | `python-pptx` |

### Utility

| Toolset | Functions | Dependencies |
|---------|-----------|-------------|
| **text-transform** | `text_diff` · `regex_extract` · `markdown_table` · `text_stats` | stdlib |
| **file-verify** | `check_json` · `check_yaml` · `check_csv` · `file_hash` · `detect_encoding` | `PyYAML`, `chardet` (optional) |
| **calc-toolkit** | `eval_expression` · `convert_unit` · `basic_stats` | stdlib |
| **text-gen** | `lorem_words` · `lorem_paragraphs` · `generate_sentences` · `generate_data` | stdlib |
| **batch-ops** | `batch_rename` · `batch_find_replace` · `batch_stats` · `batch_copy` | stdlib |

### Guidance & diagnostics

| Toolset | Functions | Dependencies |
|---------|-----------|-------------|
| **debug-toolkit** | `analyze_error` · `extract_log_patterns` | stdlib |
| **webapp-testing-toolkit** | `check_url` · `extract_urls` | stdlib |
| **doc-coauthoring-toolkit** | `document_outline` · `markdown_template` | stdlib |
| **internal-comms-toolkit** | `comms_template` · `format_bullets` | stdlib |
| **stuck-toolkit** | doc-only — no code bindings | — |

---

## Project Structure

```
AgentToolStore/
├── client/                          # Python SDK (pip install toolstore)
│   ├── pyproject.toml
│   └── src/toolstore/
│       ├── cli.py                   # Typer CLI (update, search, use, publish, …)
│       ├── native_tool.py           # tool_store_tool() — the agent-facing entry point
│       ├── toolset.py               # @tool decorator + schema generation
│       ├── toolset_manager.py       # AST-based toolset discovery & publishing
│       ├── exec_tools.py            # Local + remote toolset execution
│       ├── config_manager.py        # Settings, registry URL, env-var overrides
│       ├── mcp_client.py            # MCP client (stdio / SSE transport)
│       ├── mcp_server.py            # MCP server — expose ToolStore via MCP
│       ├── index_manager.py         # Local index cache
│       ├── transport.py             # stdio / SSE / streamable-http transports
│       ├── skill_manager.py         # Agent Skills loader + discovery
│       ├── skill_discovery.py       # Skill directory scanner
│       ├── schema_converter.py      # Convert ToolStore schemas to OpenAI format
│       ├── management/              # Management server + SPA (custom HTTP server)
│       │   ├── server.py
│       │   ├── api_helpers.py
│       │   ├── api_mcp.py
│       │   ├── api_skills.py
│       │   └── static/
│       │       └── app.js
│       └── docker_pool.py           # Docker container pool (optional)
│
├── server/                          # Registry server (FastAPI + SQLite)
│   ├── Dockerfile                   # HF Spaces deployment
│   ├── requirements.txt
│   ├── init_db.py
│   └── app/
│       ├── main.py                  # FastAPI app — browse page, API, auth
│       ├── models.py                # Pydantic models (ToolSet, Binding, …)
│       ├── database.py              # SQLite with HF Storage Bucket
│       ├── db.py                    # Connection helper
│       └── auth.py                  # JWT auth + user management
│
├── toolsets/                        # All 14 published toolsets
│   ├── xlsx-toolkit/
│   ├── pdf-toolkit/
│   ├── docx-toolkit/
│   ├── pptx-toolkit/
│   ├── text-transform/
│   ├── file-verify/
│   ├── calc-toolkit/
│   ├── text-gen/
│   ├── batch-ops/
│   ├── debug-toolkit/
│   ├── webapp-testing-toolkit/
│   ├── doc-coauthoring-toolkit/
│   ├── internal-comms-toolkit/
│   └── stuck-toolkit/
│
├── Dockerfile                       # Root Dockerfile (HF Spaces entry point)
├── _publish_toolsets.py             # Utility: batch-publish all toolsets
├── LICENSE                          # MIT
└── README.md
```

---

## Development

```bash
git clone https://github.com/Mrw33554432/AgentToolStore.git
cd AgentToolStore
pip install -e client/

# Run a local registry for testing
cd server && pip install -r requirements.txt && python init_db.py
uvicorn app.main:app --port 8000 &

# Point the CLI at your local registry
export TOOLSTORE_REGISTRY_URL=http://localhost:8000/index.json

# Test a toolset
toolstore use text-transform --function text_stats text="Hello world."
```

---

## Contributing

1. Write a toolset (`toolsets/<name>/toolset.py` + `doc.md`)
2. Decorate every callable function with `@tool`
3. Use keyword-only arguments with type hints and Google-style docstrings
4. List dependencies in `requirements.txt`
5. Test with `toolstore use <name> --function <fn> <args>`
6. Open a PR against `main`

---

## Remaining Work

- **xlsx / pdf / docx / pptx testing** — these toolsets need `openpyxl`,
  `pdfplumber`, `python-docx`, and `python-pptx` installed in the test
  environment for full integration tests
- **Rate limiting** — the registry server has no rate limiting on public
  endpoints
- **Large payload handling** — docx/pptx toolset bindings can be large;
  better error handling for oversized publishes

---

## License

MIT — see [LICENSE](LICENSE)
