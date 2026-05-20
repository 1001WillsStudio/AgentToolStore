# AgentToolStore

**The universal tool platform for AI agents.**

Register any tool — an HTTP endpoint, an MCP server, a SKILL.md file, or raw Python
code — and every agent in your ecosystem can discover, inspect, and run it through a
single unified interface.  AgentToolStore bridges the gaps between tool ecosystems,
converting schemas on the fly so tools work across OpenAI, Anthropic, MCP, and any
other agent framework.

<p align="center">
  <strong>
    <a href="#quick-start">Quick Start</a> ·
    <a href="#tool-types">Tool Types</a> ·
    <a href="#docker-sandbox">Docker Sandbox</a> ·
    <a href="#mcp-support">MCP Support</a> ·
    <a href="#configuration">Configuration</a>
  </strong>
</p>

---

## Architecture

```
                        ┌──────────────────────┐
                        │    Any AI Agent       │
                        │  (Claude, GPT, etc.)  │
                        └──────────┬───────────┘
                                   │
                    tool_store_tool(action, ...)
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
 ┌─────────────┐          ┌───────────────┐          ┌──────────────┐
 │  API tools  │          │  Docker tools │          │  MCP tools   │
 │  HTTP GET   │          │  warm worker  │          │  JSON-RPC    │
 │  / POST     │          │  (persistent) │          │  over stdio  │
 └─────────────┘          └───────┬───────┘          └──────┬───────┘
                                  │                         │
                                  │  ┌──────────────────────┤
                                  │  │   MCP-in-Docker      │
                                  │  │   (1 container per   │
                                  │  │    MCP server)       │
                                  │  └──────────────────────┤
                                  ▼                         ▼
                         ┌────────────────────────────────────┐
                         │         Docker Engine               │
                         │    (host daemon or DinD socket)     │
                         └────────────────────────────────────┘
                                   │
                          Registry Server
                        (FastAPI + SQLite)
```

---

## Tool Types

AgentToolStore supports four kinds of tools.  Every tool type is discovered, inspected,
and executed through the exact same interface — the agent doesn't need to know or care
which kind it's calling.

| Type       | What it is | Example |
|------------|------------|---------|
| **api**    | HTTP endpoint, called via GET or POST | `weather-api`, `currency-converter` |
| **mcp**    | Tool exposed by an MCP server over stdio or SSE | `github_create_issue`, `filesystem_read` |
| **skill**  | Agent skill following the [agentskills.io](https://agentskills.io) `SKILL.md` spec | `pdf-processing`, `image-analysis` |
| **docker** | Raw Python code executed in an isolated container | `create_user`, `run_sql_query`, `train_model` |

### Docker tools: how they work

Docker tools run Python code in a persistent warm container.  The container starts
**once** and stays alive across all invocations — imports and interpreter state are
cached, so repeated calls feel instantaneous.

<p align="center">
  <strong>load once → call by name</strong>
</p>

```
┌─ First call to create_user ─────────────────────────────────────────────┐
│                                                                          │
│  LOAD  {"module":"m_a3f8b2c1", "code":"def create_user(name,email):..."}│
│     ←  {"ok":true, "output":"module 'm_a3f8b2c1' loaded"}              │
│                                                                          │
│  CALL  {"module":"m_a3f8b2c1", "function":"create_user",                │
│         "args":{"name":"Alice","email":"alice@e.com"}}                   │
│     ←  {"ok":true, "output":"Created Alice"}                            │
│                                                                          │
├─ Second call to delete_user (same module, already loaded) ──────────────┤
│                                                                          │
│  CALL  {"module":"m_a3f8b2c1", "function":"delete_user",                │
│         "args":{"id":42}}                                               │
│     ←  {"ok":true, "output":"Deleted 42"}                               │
└──────────────────────────────────────────────────────────────────────────┘
```

The default worker image is [`quay.io/jupyter/scipy-notebook`][scipy-notebook] — a
BSD-3-Clause licensed image with **numpy, scipy, pandas, matplotlib, scikit-learn,
seaborn, beautifulsoup4, sqlalchemy, dask, cython, numba, sympy, openpyxl, h5py**, and
20+ more scientific Python libraries pre-installed.  Most docker tools need nothing
beyond standard-library imports to be useful; when they do need heavier dependencies,
they're already there.

[scipy-notebook]: https://github.com/jupyter/docker-stacks

### Docker approval model

Custom Docker images are controlled by a client-side approval policy — the registry
never sees your credentials or image preferences:

| Mode     | Behaviour |
|----------|-----------|
| `none`   | Only the default base image is allowed.  No custom images. |
| `list`   | Only images that appear in your approved list are allowed. |
| `all`    | Any Docker image is allowed. |

```bash
toolstore docker mode list
toolstore docker approve ghcr.io/my-org/tool-image:v1
toolstore docker list
```

This is designed for environments where you want the convenience of community tools
but need to control what code runs on your infrastructure.

---

## MCP Support

AgentToolStore is a full MCP participant — both client and server.

### MCP Client

Speaks the complete MCP protocol (tools, resources, prompts) over **stdio** and
**HTTP/SSE** transports.  A persistent connection pool keeps multiple MCP servers
alive simultaneously.

```bash
toolstore mcp-server add github npx -a "-y @modelcontextprotocol/server-github"
toolstore mcp-server add weather ghcr.io/acme/weather-mcp:v1 --entrypoint "python -m weather_mcp"
toolstore update          # discover tools from all registered servers
toolstore list            # see everything available
```

### MCP-in-Docker

MCP servers can run inside Docker containers — each server gets its own persistent
container with its own image.  This gives you full isolation for servers with heavy
or conflicting dependencies without polluting the host.

### MCP Server

AgentToolStore itself can act as an MCP server, exposing every indexed tool to
Claude Desktop, VS Code, or any other MCP-compatible client:

```bash
# stdio mode (for Claude Desktop)
toolstore serve --mode stdio

# HTTP/SSE mode
toolstore serve --mode sse --port 9090
```

---

## Quick Start

### Install the CLI

```bash
pip install -e client/
```

### Pull the tool index

```bash
# From the default registry
toolstore update

# Search across all tool types
toolstore search "weather"

# Inspect a tool's schema (works for api, mcp, skill, and docker tools)
toolstore info weather-api
```

### Configure Docker for sandboxed execution

Running inside Docker yourself?  Mount the socket:

```yaml
# docker-compose.yml
services:
  app:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

The client auto-detects Docker-in-Docker and will tell you if the socket is missing.

### Run a docker tool

```bash
toolstore use create_user --name "Alice" --email "alice@example.com"
```

### Publish your own tool

```json
// my-tool.json
{
  "name": "create_user",
  "type": "docker",
  "description": "Create a new user account",
  "code": "def create_user(name, email):\n    return f'Created {name} ({email})'",
  "function": "create_user",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name":  {"type": "string"},
      "email": {"type": "string"}
    },
    "required": ["name", "email"]
  }
}
```

```bash
toolstore publish my-tool.json
```

### Run the registry server

```bash
cd server
pip install -r requirements.txt
python init_db.py
uvicorn app.main:app --reload
```

---

## Using from an Agent

```python
from toolstore.native_tool import tool_store_tool

# Search for tools
tool_store_tool(action="search", query="weather")

# Get OpenAI schemas — drop directly into your agent's function definitions
tool_store_tool(action="info",
                tool_names=["create_user", "weather-api", "github_create_issue"])

# Execute any tool type through the same interface
tool_store_tool(action="execute",
                tool_name="create_user",
                arguments={"name": "Alice", "email": "alice@e.com"})
```

---

## Schema Bridge

Tool definitions are automatically converted between three formats:

| Format | Used by |
|--------|---------|
| **ToolStore** (canonical) | Internal representation |
| **OpenAI function-calling** | GPT, compatible APIs |
| **MCP JSON Schema** | Claude Desktop, MCP clients |

A tool registered once works everywhere.  No format lock-in.

---

## Configuration

All settings live in `~/.toolstore/config.json`:

```json
{
  "registry_url": "http://localhost:8000/index.json",
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    },
    "weather": {
      "type": "docker",
      "image": "ghcr.io/acme/weather-mcp:v1",
      "entrypoint": ["python", "-m", "weather_mcp_server"]
    }
  },
  "skill_dirs": ["~/.toolstore/skills"],
  "docker": {
    "approval_mode": "list",
    "approved_images": ["ghcr.io/acme/weather-mcp:v1"],
    "default_image": "quay.io/jupyter/scipy-notebook"
  },
  "server": {
    "enabled": false,
    "mode": "stdio",
    "sse_port": 9090,
    "sse_host": "127.0.0.1"
  }
}
```

Everything is manageable through the CLI:

```bash
toolstore config get
toolstore docker mode list
toolstore docker approve ghcr.io/my-org/image:v1
toolstore mcp-server add-docker weather ghcr.io/acme/weather-mcp:v1
toolstore skill add-dir ~/my-skills
```

---

## Repository Structure

```
AgentToolStore/
├── client/src/toolstore/
│   ├── native_tool.py          # Entry point: tool_store_tool()
│   ├── docker_pool.py          # Warm container + worker protocol
│   ├── mcp_client.py           # Full MCP protocol client
│   ├── mcp_server.py           # ToolStore as an MCP server
│   ├── skill_manager.py        # SKILL.md parser & executor
│   ├── schema_converter.py     # Bidirectional format conversion
│   ├── index_manager.py        # Tool index search & lookup
│   ├── config_manager.py       # ~/.toolstore/config.json
│   ├── transport.py            # stdio, SSE, and Docker transports
│   └── cli.py                  # Command-line interface
├── server/app/
│   ├── main.py                 # FastAPI server entry point
│   ├── models.py               # SQLAlchemy models (Tool, User)
│   └── api/v1/                 # REST endpoints
├── plan/                       # Specifications & roadmap
└── docs/                       # Integration design documents
```

---

## License

MIT
