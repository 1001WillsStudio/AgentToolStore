# AgentToolStore

**The universal tool platform for AI agents** — MCP Client + Skills Manager + Registry Server.

AgentToolStore gives AI agents a single, unified interface to discover, inspect, and execute
tools from multiple sources: public APIs, MCP servers, and agent skills. It bridges the gap
between different tool ecosystems by providing bidirectional schema conversion (ToolStore ↔
OpenAI function-calling ↔ MCP JSON Schema) so tools work across any agent framework.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                    Agent                         │
│         (ThinkWithTool / Claude / etc.)          │
│                                                  │
│  ┌───────────────────────────────────────────┐  │
│  │         tool_store meta-tool               │  │
│  │  action: search | info | execute           │  │
│  └──────────────┬────────────────────────────┘  │
└─────────────────┼────────────────────────────────┘
                  │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
  Public      MCP Client    Skills
  APIs        (stdio/SSE)   (SKILL.md)
     │            │            │
     └────────────┼────────────┘
                  ▼
          Registry Server
        (FastAPI + SQLite)
```

## Key Concepts

### Tools
A *tool* is any callable function exposed to an agent. ToolStore supports three kinds:

| Type     | Description | Example |
|----------|-------------|---------|
| **api**  | HTTP endpoint called via GET/POST | weather-api, currency-converter |
| **mcp**  | Tool exposed by an MCP server over stdio or HTTP/SSE | github_create_issue, filesystem_read |
| **skill**| Agent skill following the agentskills.io `SKILL.md` spec | pdf-processing, image-analysis |

### MCP (Model Context Protocol)
ToolStore is a full MCP client supporting the complete protocol — tools, resources, and
prompts — over both stdio and HTTP/SSE transports. It maintains a persistent connection
pool so multiple MCP servers can be used simultaneously without restarting.

### Schema Bridge
Tool definitions circulate in three formats. ToolStore converts between all of them:

- **ToolStore format** — internal canonical representation (with `schema.input` or `schema.inputSchema`)
- **OpenAI function-calling** — `{type: "function", function: {name, description, parameters}}`
- **MCP JSON Schema** — `{name, description, inputSchema: {type: "object", properties: {...}}}`

This means a tool registered once can be used with any LLM provider or agent framework.

### Registry Server
A FastAPI server that acts as a central index for tools. Clients pull the index to
discover available tools, and tool authors can publish their definitions. Supports
JWT authentication.

---

## Repository Structure

```
AgentToolStore/
├── client/              # CLI & Python library
│   └── src/toolstore/
│       ├── native_tool.py      # Entry point for agents (tool_store_tool)
│       ├── schema_converter.py # Bidirectional schema conversion
│       ├── mcp_client.py       # Full MCP protocol client
│       ├── mcp_server.py       # Expose tools as MCP server
│       ├── skill_manager.py    # SKILL.md parser & executor
│       ├── index_manager.py    # Tool index search & lookup
│       ├── config_manager.py   # ~/.toolstore/config.json
│       ├── transport.py        # stdio + SSE transport layer
│       └── cli.py              # Command-line interface
├── server/              # Registry server (FastAPI)
│   └── app/
│       ├── main.py             # Server entry point
│       ├── models.py           # SQLAlchemy models
│       └── api/v1/             # REST endpoints
├── plan/                # Specifications & roadmap
│   └── V1_SPEC.md
└── docs/                # Integration design documents
```

---

## Quick Start

### Client

```bash
cd client
pip install -e ".[all]"

# Pull the latest tool index from the registry
toolstore update

# Search for tools
toolstore search "weather"

# Inspect a tool's schema
toolstore info weather-api

# Execute a tool
toolstore execute weather-api --latitude 37.77 --longitude -122.41
```

### Registry Server

```bash
cd server
pip install -r requirements.txt
python init_db.py
uvicorn app.main:app --reload
```

### Run as MCP Server

ToolStore can expose all its indexed tools as an MCP server, making them available to
Claude Desktop, VS Code, and other MCP-compatible clients:

```bash
# stdio mode (for Claude Desktop)
toolstore serve --mode stdio

# HTTP/SSE mode
toolstore serve --mode sse --port 9090
```

---

## Using ToolStore from an Agent

The core entry point is `tool_store_tool()` in `native_tool.py`. Agents call it with
an action and parameters:

```python
from toolstore.native_tool import tool_store_tool

# Search
tool_store_tool(action="search", query="file system")

# Inspect
tool_store_tool(action="info", tool_name="filesystem_read")

# Get OpenAI schemas in bulk (ready to bind as agent tool definitions)
tool_store_tool(action="info",
                tool_names=["github_create_issue", "weather-api"])

# Execute
tool_store_tool(action="execute",
                tool_name="weather-api",
                arguments={"latitude": 37.77, "longitude": -122.41})
```

The `tool_names` parameter returns a JSON array of OpenAI function-calling schemas —
drop them directly into your agent's function definitions list.

---

## Configuration

All client configuration lives in `~/.toolstore/config.json`:

```json
{
  "registry_url": "http://localhost:8000/index.json",
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    }
  },
  "skill_dirs": ["~/.toolstore/skills"],
  "server": {
    "enabled": false,
    "mode": "stdio",
    "sse_port": 9090,
    "sse_host": "127.0.0.1"
  }
}
```

Manage it via the CLI:

```bash
toolstore config get                    # View current config
toolstore config add-mcp github ...     # Register an MCP server
toolstore skill add-dir ~/my-skills     # Add a skill directory
```

---

## Key Features

-   **MCP Client** — full protocol (tools, resources, prompts), stdio + HTTP/SSE,
    persistent connection pool
-   **Skills** — agentskills.io spec: `SKILL.md` parsing, progressive disclosure,
    local script execution, validation
-   **MCP Server** — expose all indexed tools as MCP endpoints for any
    MCP-compatible client
-   **Schema Bridge** — bidirectional ToolStore ↔ OpenAI ↔ MCP schema conversion
-   **Registry Server** — FastAPI with JWT auth, tool publishing, index distribution
-   **Three tool types** — APIs (HTTP), MCP (protocol), and Skills (SKILL.md) unified
    under one interface
