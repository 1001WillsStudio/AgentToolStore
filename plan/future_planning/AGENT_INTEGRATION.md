# Agent Integration Guide

## How Agents Use ToolStore

ToolStore is designed to be used BY agents, not imported in code. It provides two agent-native interfaces:

---

## Interface 1: CLI Commands

### Overview
Agents execute shell commands to interact with ToolStore.

### Commands

```bash
# Update tool index
$ toolstore update
Downloading index... [5.2 MB]
10,234 tools available

# Search for tools
$ toolstore search "weather"
Found 15 tools:
  1. weather-api (v1.2.3) - Get current weather
  2. weather-forecast (v2.0.1) - 7-day forecasts
  ...

# Get tool information
$ toolstore info weather-api
Name: weather-api
Version: 1.2.3
Type: API
Endpoint: https://api.openweathermap.org/v1
...

# Execute a tool
$ toolstore use weather-api --city "San Francisco" --units "metric"
{
  "temperature": 18,
  "description": "Partly cloudy"
}

# Add personal tool
$ toolstore add my-company-api \
  --endpoint "http://company.internal/api" \
  --schema "./schema.json"
```

### Agent Workflow Example

```
Agent Task: "What's the weather in San Francisco?"

1. Agent: Search for weather tools
   → Execute: toolstore search "weather"
   → Parse output: ["weather-api", "weather-forecast", ...]

2. Agent: Get tool info
   → Execute: toolstore info weather-api
   → Parse: endpoint, schema, required params

3. Agent: Execute tool
   → Execute: toolstore use weather-api --city "San Francisco"
   → Parse output: {"temperature": 18, "description": "Partly cloudy"}

4. Agent: Respond to user
   → "It's 18°C and partly cloudy in San Francisco"
```

---

## Interface 2: Tool Calls (MCP Server)

### Overview
ToolStore runs as an MCP server. Agents connect and call ToolStore functions directly.

### Setup

```bash
# Start ToolStore as MCP server
$ toolstore serve --port 9000
ToolStore MCP server running on http://localhost:9000
```

Or add to MCP configuration:
```json
{
  "mcpServers": {
    "toolstore": {
      "command": "toolstore",
      "args": ["serve"]
    }
  }
}
```

### Available Tools

ToolStore exposes itself as a set of tools:

#### 1. `toolstore.search`
Search for tools in the registry.

```json
{
  "tool": "toolstore.search",
  "parameters": {
    "query": "weather",
    "limit": 10,
    "type": "api"  // optional filter
  }
}
```

**Returns:**
```json
{
  "tools": [
    {
      "name": "weather-api",
      "version": "1.2.3",
      "description": "Get current weather information",
      "type": "api",
      "rating": 4.8
    },
    ...
  ]
}
```

#### 2. `toolstore.info`
Get detailed information about a specific tool.

```json
{
  "tool": "toolstore.info",
  "parameters": {
    "name": "weather-api"
  }
}
```

**Returns:**
```json
{
  "name": "weather-api",
  "version": "1.2.3",
  "type": "api",
  "endpoint": "https://api.openweathermap.org/v1/weather",
  "schema": {
    "input": {
      "city": {"type": "string", "required": true},
      "units": {"type": "string", "enum": ["metric", "imperial"]}
    },
    "output": {
      "temperature": {"type": "number"},
      "description": {"type": "string"}
    }
  },
  "auth": {
    "type": "api_key",
    "header": "X-API-Key"
  },
  "examples": [...]
}
```

#### 3. `toolstore.execute`
Execute a tool with given parameters.

```json
{
  "tool": "toolstore.execute",
  "parameters": {
    "tool_name": "weather-api",
    "args": {
      "city": "San Francisco",
      "units": "metric"
    }
  }
}
```

**Returns:**
```json
{
  "success": true,
  "result": {
    "temperature": 18,
    "description": "Partly cloudy"
  }
}
```

#### 4. `toolstore.add_tool`
Add a custom tool to personal registry.

```json
{
  "tool": "toolstore.add_tool",
  "parameters": {
    "name": "my-company-api",
    "type": "api",
    "endpoint": "http://company.internal/api",
    "schema": {...}
  }
}
```

#### 5. `toolstore.update`
Update the local tool index.

```json
{
  "tool": "toolstore.update",
  "parameters": {}
}
```

**Returns:**
```json
{
  "updated": true,
  "tools_added": 5,
  "total_tools": 10234
}
```

### Agent Workflow Example

```
Agent Task: "What's the weather in San Francisco?"

1. Agent calls: toolstore.search
   {
     "tool": "toolstore.search",
     "parameters": {"query": "weather", "limit": 5}
   }
   
   ToolStore returns: List of weather tools

2. Agent calls: toolstore.execute
   {
     "tool": "toolstore.execute",
     "parameters": {
       "tool_name": "weather-api",
       "args": {"city": "San Francisco"}
     }
   }
   
   ToolStore:
   - Looks up tool definition in index
   - Makes HTTP POST to weather API
   - Returns result
   
3. Agent receives: {"temperature": 18, "description": "Partly cloudy"}

4. Agent responds: "It's 18°C and partly cloudy in San Francisco"
```

---

## Interface 3: HTTP API (Alternative)

### Overview
For agents that don't support MCP, ToolStore provides a REST API.

### Endpoints

```bash
# Search
POST /api/search
{
  "query": "weather",
  "limit": 10
}

# Get tool info
GET /api/tools/weather-api

# Execute tool
POST /api/execute
{
  "tool": "weather-api",
  "args": {"city": "SF"}
}

# Add custom tool
POST /api/tools
{
  "name": "my-tool",
  "endpoint": "...",
  "schema": {...}
}

# Update index
POST /api/update
```

---

## Comparison: CLI vs Tool Calls

| Aspect | CLI | Tool Calls (MCP) | HTTP API |
|--------|-----|------------------|----------|
| **Setup** | None | Start server | Start server |
| **Speed** | Slower (fork process) | Fast (in-process) | Fast (HTTP) |
| **Integration** | Shell-based agents | Function-calling agents | Any HTTP client |
| **Output** | Text (parse needed) | Structured JSON | Structured JSON |
| **Use Case** | Testing, simple agents | Production agents | Cross-platform |

---

## Agent Framework Integration Examples

### LangChain

```python
from langchain.tools import Tool

# ToolStore as shell tool
toolstore_search = Tool(
    name="toolstore_search",
    func=lambda q: subprocess.run(["toolstore", "search", q], capture_output=True).stdout,
    description="Search for tools in ToolStore"
)

# Or via MCP
from langchain_mcp import MCPClient

mcp = MCPClient("toolstore")
tools = mcp.get_tools()  # Gets all ToolStore tools
```

### AutoGPT

```yaml
# agents/config.yml
tools:
  - name: toolstore
    type: mcp
    server: toolstore
    command: ["toolstore", "serve"]
```

### CrewAI

```python
from crewai import Tool

toolstore_tool = Tool(
    name="ToolStore",
    description="Search and execute tools from ToolStore",
    func=lambda q: toolstore_client.search(q)
)
```

---

## Best Practices

### 1. Update Regularly
```bash
# Update index daily or before important tasks
toolstore update
```

### 2. Search Before Use
```bash
# Search to discover available tools
toolstore search "weather"
toolstore search "image" --type api
```

### 3. Check Tool Info
```bash
# Understand tool before using
toolstore info weather-api
```

### 4. Handle Errors
```bash
# Tools may fail - parse error codes
toolstore use weather-api --city "Invalid"
# Exit code: 1
# Stderr: Tool execution failed: Invalid city
```

### 5. Add Custom Tools
```bash
# Add company-internal tools
toolstore add internal-db --endpoint "http://internal/api"
```

---

## Authentication & High-Value Tools (V1)

ToolStore V1 does **not** manage API keys or credentials directly. However, you can still access authenticated, high-value services (like GitHub, Database, Slack) using **User-Managed Auth**.

### Method 1: MCP Servers (Recommended)

**Unified Abstraction:**
You configure the servers, but **the Agent never sees them**. ToolStore ingests the tools and presents them as native ToolStore tools.

**Configuration (`~/.toolstore/config.json`):**
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Docs"]
    }
  }
}
```

**Agent Experience:**
The Agent does **not** know about "MCP" or "filesystem server". It just sees tools:
```bash
$ toolstore search "file"
Found:
- read_file  <-- Looks like a normal tool
- write_file

$ toolstore use read_file --path "doc.txt"
# ToolStore internally routes this to the MCP connection
```

**Benefit:** You can swap a local MCP tool for a cloud API later, and the Agent's code doesn't change.

### Method 2: Local Proxy / Network Tools
Users can run their own authenticated tools locally (e.g., a Python script running on `localhost:8000` that holds the API keys).
1. User runs local server: `python my_server.py` (has API keys hardcoded or in env)
2. User adds tool: `toolstore add my-tool --endpoint http://localhost:8000`
3. Agent uses tool: `toolstore use my-tool ...`
   * *ToolStore makes a simple HTTP call; the local server handles the actual authentication.*

### Method 3: Auth-Free Public APIs
Many utility tools require no authentication at all:
- Unit converters
- Public data (holidays, countries)
- Calculators
- Time/Date utilities

**Summary:** Agents can access powerful tools in V1, provided the **User** has configured the environment (MCP) or the network (Local Proxy). ToolStore acts as the discovery and execution layer.

---

## Advanced: ToolStore Meta-Tool

Think of ToolStore as a **meta-tool** - a tool that manages other tools:

```
Agent has tools:
  1. calculator
  2. web_search
  3. toolstore  ← Meta-tool
  
Agent task: "Analyze weather patterns"

Agent: I don't have weather tools
  ↓
Agent uses toolstore.search("weather")
  ↓
Discovers: weather-api, weather-forecast, climate-data
  ↓
Agent uses toolstore.execute("weather-api", ...)
  ↓
Gets result, completes task
```

ToolStore **expands agent capabilities dynamically**.

---

## Summary

**Two Interfaces:**
1. **CLI** - Shell commands (`toolstore search`, `toolstore use`)
2. **Tool Calls** - MCP server or HTTP API (structured function calls)

**No Python SDK needed** - ToolStore IS the tool.

**Agent Workflow:**
```
Search → Info → Execute → Result
```

**Key Benefit:** Agents can discover and use 10,000+ tools without pre-configuration.

---

**Last Updated:** November 24, 2025  
**See Also:** [PROJECT_PLAN.md](PROJECT_PLAN.md), [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

