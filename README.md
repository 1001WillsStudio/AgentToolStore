# AgentToolStore

**The universal tool platform for AI agents** — MCP Client + Skills Manager + MCP Server.

## Components

| Directory | Role |
|-----------|------|
| `client/` | **ToolStore CLI & Library** — search, execute, and manage tools. MCP client with full protocol support (tools/resources/prompts), Skill manager (agentskills.io spec), and MCP server mode. |
| `server/` | **Registry Server** — FastAPI backend for publishing, discovering, and distributing tool definitions. |
| `plan/` | **Specifications & Planning** — V1 spec, future roadmap, design documents. |

## Quick Start

```bash
# Client
cd client && pip install -e ".[all]"
toolstore update
toolstore search "weather"

# Server
cd server && pip install -r requirements.txt
uvicorn app.main:app --reload

# Run ToolStore as MCP server
toolstore serve --mode stdio
```

## Key features (v2)

- **MCP Client** — full protocol (tools, resources, prompts), stdio + HTTP/SSE transport, persistent connection pool
- **Skills** — agentskills.io spec: `SKILL.md` parsing, progressive disclosure, validation
- **MCP Server** — expose all indexed tools as MCP endpoints for Claude Desktop, VS Code, etc.
- **Schema Bridge** — bidirectional ToolStore ↔ OpenAI ↔ MCP schema conversion
- **Registry Server** — FastAPI with JWT auth, tool publishing, index distribution
