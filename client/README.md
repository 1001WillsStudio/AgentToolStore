# ToolStore CLI

<p align="center">
  <strong>pip for AI agents — the universal meta-tool client.</strong>
</p>

---

The ToolStore CLI is the local client that gives any AI agent instant access to
every tool in the ecosystem — public APIs, MCP servers, local skills, and
sandboxed code modules — all through a single, uniform interface.

It handles discovery, inspection, schema conversion, and execution across all
tool types.  The agent doesn't need to know whether a tool is an HTTP endpoint,
a Docker container, or an MCP server — it just calls it.

For the full vision and architecture, see the [main README](../README.md).

---

## 🚀 Quick Start

### Install

```bash
pip install -e .
```

### Pull the public tool index

```bash
toolstore update                    # fetch the latest index
toolstore search "weather"          # search across all tool types
toolstore info weather-api          # inspect a tool's schema
```

### Run a tool

```bash
toolstore use world-time-api --timezone "America/New_York"
```

### Publish your own tool

```bash
toolstore publish my-tool.json
```

## 👤 Authentication & Publishing

To publish your own tools to the registry, you need a developer account.

### 1. Register an Account
Since the CLI is currently optimized for tools, registration is handled via the API directly (or use `curl`):

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "myuser",
    "email": "myuser@example.com",
    "password": "mypassword"
  }'
```

### 2. Login
Once registered, you can login via the CLI to save your credentials locally:

```bash
$ toolstore login
Username: myuser
Password: mypassword
Logging in to http://localhost:8000...
Login successful!
```
*(Tokens are saved to `~/.toolstore/credentials`)*

### 3. Publish a Tool
Create a `tool.json` file (see below) and run:

```bash
$ toolstore publish tool.json
```

## 🛠️ Creating Tools (The Standard)

ToolStore uses a simple JSON format to define tools.

### 1. API Tool Standard (V1)
To add a public API or local service, create a definition file (e.g., `my-tool.json`):

```json
{
  "name": "weather-api",
  "version": "1.0.0",
  "type": "api",
  "description": "Get current weather for any city",
  "author": "username",
  "license": "MIT",
  
  "endpoint": "https://api.open-meteo.com/v1/forecast",
  "method": "GET",
  
  "auth": {
    "type": "none"  // V1 only supports auth-free APIs
  },
  
  "schema": {
    "input": {
      "latitude": { "type": "number", "required": true, "description": "Latitude" },
      "longitude": { "type": "number", "required": true, "description": "Longitude" }
    },
    "output": {
      "temperature": "number",
      "unit": "string"
    }
  },
  
  "examples": [
    {
      "input": { "latitude": 37.77, "longitude": -122.41 },
      "output": { "temperature": 18, "unit": "celsius" }
    }
  ]
}
```

## 📖 Documentation
*   **[V1_SPEC.md](V1_SPEC.md)** - The technical specification for this implementation.
*   **[future_planning/](future_planning/)** - Original research and long-term roadmap.

## 🛠️ Development status
**Current Phase:** V1 Implementation (Foundation)
