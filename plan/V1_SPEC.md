# ToolStore V1 Implementation Specification

> **Status:** Implementation Ready
> **Focus:** Public APIs & MCP Proxy (Auth-free / User-managed)

---

## 1. Core Architecture (V1)

**The "Connector" Model:**
ToolStore V1 is a local search engine and proxy router. It does not manage authentication secrets or runtimes.

### Components
1.  **Local Index (JSON):** Stores definitions for 10,000+ public tools and local MCP tools. (Loaded into memory).
2.  **CLI Client:** The main interface for Agents (`search`, `use`).
3.  **MCP Client:** Connects to user-provided MCP servers (via stdio/HTTP).
4.  **HTTP Client:** Calls public API endpoints.

### Data Flow
1.  **Startup:** 
    *   Download Public Index (JSON) → Save to `~/.toolstore/index.json`.
    *   Connect to Local MCP Servers → Query `tools/list` → Merge into in-memory index.
2.  **Discovery:**
    *   Agent calls `toolstore search "query"`.
    *   Client loads JSON, performs linear search / regex.
    *   Returns unified list of tools.
3.  **Execution:**
    *   Agent calls `toolstore use <tool> <params>`.
    *   Client looks up tool by name in JSON.
    *   **If API:** Makes HTTP Request.
    *   **If MCP:** Forwards JSON-RPC request.

---

## 2. Scope & Limitations

### ✅ Included in V1
*   **Public APIs:** Auth-free GET/POST endpoints (e.g., Weather, Time, Math).
*   **MCP Servers:** User-managed servers (User runs `npx...`, handles auth via Env Vars).
*   **Local APIs:** User-managed `localhost` servers.
*   **Interfaces:** 
    *   CLI (`toolstore ...`) for Shell Agents.
    *   **OpenAI Compatible:** Export schemas for `client.chat.completions`.
    *   **Meta-Tool:** Expose `toolstore` itself as a tool (Search/Execute) for Agents.

### ❌ Excluded from V1 (Strict)
*   **Auth Management:** No API Keys, OAuth, or Vaults in ToolStore.
*   **Sandboxing:** No Docker or Runtime management.
*   **Server Hosting:** ToolStore is a client-side tool only.

---

## 3. Technical Specifications

### 3.1 Local Storage (JSON)
We use `~/.toolstore/index.json`. Simpler than SQL for V1.0.

**Structure:**
```json
{
  "meta": { "version": "2025-11-24", "count": 10234 },
  "tools": {
    "weather_api": {
      "name": "weather_api",
      "description": "Get current weather...",
      "type": "api",
      "schema": { ... },
      "openai_schema": { ... },
      "endpoint": "https://...",
      "method": "GET"
    },
    "filesystem_read": {
      "name": "filesystem_read",
      "type": "mcp",
      "mcp_server": "filesystem",
      "schema": { ... }
    }
  }
}
```

### 3.2 Configuration (`~/.toolstore/config.json`)
Minimal config for MCP servers.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/docs"]
    }
  }
}
```

### 3.3 Public Index Format (JSON)
Hosted on GitHub Pages or S3.

```json
[
  {
    "name": "world-time-api",
    "type": "api",
    "description": "Get current time by timezone",
    "endpoint": "http://worldtimeapi.org/api/timezone",
    "method": "GET",
    "schema": { ... }
  }
]
### 3.4 Meta-Tool Definition
ToolStore provides a "Master Tool" schema for agents to discover/use tools dynamically.

```json
{
  "name": "tool_store",
  "description": "Search and execute tools from a vast repository of APIs and local utilities.",
  "parameters": {
    "type": "object",
    "properties": {
      "action": { "type": "string", "enum": ["search", "execute", "info"] },
      "query": { "type": "string", "description": "Search query for tools" },
      "tool_name": { "type": "string", "description": "Exact name of tool to execute" },
      "arguments": { "type": "object", "description": "Arguments for the tool execution" }
    },
    "required": ["action"]
  }
}
```

---

## 4. CLI Commands (The Interface)

| Command | Description |
| :--- | :--- |
| `toolstore update` | Downloads public index + Scans local MCP servers. Saves to JSON. |
| `toolstore search <q>` | In-memory search of JSON index. |
| `toolstore use <tool> [args]` | Executes the tool. Args passed as flags (`--city SF`). |
| `toolstore info <tool>` | Prints full JSON schema of the tool. |

---

## 5. Implementation Plan

### Phase 1: Project Skeleton
- [ ] Initialize Python project (Poetry/Pip).
- [ ] Setup `toolstore` CLI entry point.
- [ ] Create JSON Index Manager (Load/Save).

### Phase 2: Index & Search
- [ ] Implement `toolstore update` (Download dummy JSON).
- [ ] Implement `toolstore search` (Linear Scan).
- [ ] Create a sample `index.json` with 5 public tools.

### Phase 3: API Execution
- [ ] Implement `toolstore use` for type `api`.
- [ ] Add generic HTTP client (httpx).
- [ ] Add basic parameter validation.

### Phase 4: MCP Integration
- [ ] Implement Config loader.
- [ ] Implement MCP Client (Stdio connection).
- [ ] Add "MCP Scanning" to `toolstore update`.
- [ ] Add "MCP Proxy" to `toolstore use`.

### Phase 5: Packaging
- [ ] Add `toolstore serve` (Optional HTTP server wrapper for Agents).
- [ ] Finalize documentation.

---

**Goal:** A functioning CLI that can call 1 Public API and 1 Local MCP Tool.

