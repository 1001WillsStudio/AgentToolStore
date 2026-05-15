# ToolStore (V1)

**The "PyPI for AI Agents" - Local Connector Edition**

ToolStore is a local CLI tool that gives AI Agents instant access to:
1.  **Public APIs** (Auth-free utilities like Weather, Time, Math).
2.  **Local Tools** (via MCP Servers like Filesystem, GitHub).

It handles discovery (Search) and execution (Proxy), abstracting away the differences between APIs and Local Tools.

**Supported Interfaces:**
*   **CLI Mode:** `toolstore search` / `toolstore use`
*   **LLM Native:** Export OpenAI-compatible schemas for direct integration.

## 🚀 Quick Start

### 1. Install
*(Coming soon via pip)*

### 2. Update Index
```bash
$ toolstore update
```

### 3. Search Tools
```bash
$ toolstore search "weather"
Found: world-time-api, weather-forecast
```

### 4. Use a Tool
```bash
$ toolstore use world-time-api --timezone "America/New_York"
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
