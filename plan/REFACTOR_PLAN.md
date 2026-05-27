# ToolStore Refactor Plan — Toolset (Agent-Centric Managed Tools)

## 1. Overview & Motivation

### Current State

| Type     | Mechanism                                    | Managed By |
|----------|----------------------------------------------|------------|
| `api`    | JSON definition → HTTP call via httpx         | Us          |
| `mcp`    | Discovered from external MCP servers          | Client      |
| `skill`  | SKILL.md (YAML + Markdown), progressive disc. | Client      |
| `docker` | Base64-encoded Python → warm Docker container | Us          |

**Problem**: `api` and `docker` are ad-hoc. An API "tool" is just a URL + method — no custom logic, no code reuse. A docker "tool" is a raw base64 blob — no structure, no metadata.

Skills are **human-centric** (progressive disclosure: load → browse files → read file → run script). Agents need to do a multi-step dance just to use one. That friction is appropriate for human-authored instructional content, not for executable code.

The new **toolset** is **agent-centric**: the agent calls `tool_store(action="execute", tool_name="weather", ...)` and it **just runs**.

### Goal

1. **Keep** `mcp` (external MCP servers — client-managed) and `skill` (human-centric progressive disclosure — client-managed).
2. **Introduce `toolset`** — a new type we manage. Agent-centric. **1 doc file + 1 code file**. Code has `@tool` decorator bindings.
3. **Remove `api` and `docker`**. Their functionality is refactored into toolsets.

---

## 2. New Type: `toolset`

### 2.1 The Core Idea

A toolset is a directory with exactly **two files**:

```
weather/                     # directory name = toolset name
├── doc.md                   # agent-facing documentation
└── toolset.py               # code with @tool-decorated functions
```

**That's it.** No scripts/, no references/, no assets/, no progressive disclosure, no SKILL.md. The agent calls it and it runs.

### 2.2 `doc.md` — Agent-Facing Documentation

Plain markdown. Describes what the toolset does, what functions are available, what parameters they take, what they return. The agent reads this to understand the tool.

```markdown
# Weather Toolset

Get weather data from public APIs.

## Functions

### get_weather
Get current weather for a location.

| Parameter | Type   | Required | Default | Description        |
|-----------|--------|----------|---------|--------------------|
| location  | string | yes      | —       | City name or coords|
| units     | string | no       | metric  | metric / imperial  |

Returns: JSON with temperature, humidity, wind speed.

### get_forecast
Get 5-day forecast.

| Parameter | Type    | Required | Default | Description  |
|-----------|---------|----------|---------|--------------|
| location  | string  | yes      | —       | City name    |
| days      | integer | no       | 5       | Number of days|

Returns: JSON array of daily forecasts.
```

### 2.3 `toolset.py` — Code with `@tool` Bindings

The code file uses a `@tool` decorator to mark functions as callable entry points:

```python
from toolstore.toolset import tool

@tool
def get_weather(location: str, units: str = "metric"):
    """Get current weather for a location."""
    import httpx
    resp = httpx.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": location, "units": units, "appid": "..."}
    )
    resp.raise_for_status()
    return resp.json()

@tool
def get_forecast(location: str, days: int = 5):
    """Get 5-day forecast for a location."""
    import httpx
    resp = httpx.get(
        "https://api.openweathermap.org/data/2.5/forecast",
        params={"q": location, "cnt": days * 8}
    )
    resp.raise_for_status()
    return resp.json()
```

**`@tool` decorator rules:**
- Marks a function as an entry point callable by agents.
- The function name becomes the binding name.
- The function docstring is used as the binding description.
- Function signature (params + type hints + defaults) defines the input schema.
- Return value is JSON-serialized and sent back to the agent.

Only `@tool`-decorated functions are callable. Other functions/classes in `toolset.py` are private helpers (not exposed).

### 2.4 How The Agent Uses It

One call, no ceremony:

```
tool_store(
    action="execute",
    tool_name="weather",
    arguments={"function": "get_weather", "location": "London", "units": "metric"}
)
```

That's it. No `load`/`files`/`file`/`run` dance. The agent can also request the doc:

```
tool_store(action="info", tool_name="weather")
```

Which returns the toolset definition including the full `doc.md` body.

### 2.5 How It Subsumes `api` and `docker`

| Old type | New equivalent |
|----------|---------------|
| `api` — `{"endpoint": "...", "method": "GET", "parameters": {...}}` | A `toolset.py` with `@tool` functions that use `httpx`. Full Python — headers, auth, retries, response parsing, chaining calls — not just a rigid URL + method template. |
| `docker` — `{"code": "<base64>", "function": "main"}` | A `toolset.py` with `@tool` functions. Same warm Docker worker executes it. But now it has proper structure, metadata, and a `doc.md`. |

---

## 3. `toolset` Module (the `@tool` decorator)

A lightweight module (`toolstore/toolset.py`) that toolsets import:

```python
# toolstore/toolset.py
"""
Decorator module imported by toolset code files.
Provides the @tool decorator that marks functions as agent-callable.
"""

from typing import Callable, Any

_REGISTRY: dict[str, Callable] = {}

def tool(fn: Callable) -> Callable:
    """Decorator: mark a function as a toolset entry point."""
    _REGISTRY[fn.__name__] = fn
    fn._is_toolset_tool = True
    return fn

def get_tool(name: str) -> Callable | None:
    """Get a registered tool function by name."""
    return _REGISTRY.get(name)

def get_tool_names() -> list[str]:
    """Get all registered tool names."""
    return list(_REGISTRY.keys())

def clear_registry() -> None:
    """Clear the registry (called between toolset loads)."""
    _REGISTRY.clear()
```

This module lives inside ToolStore itself (not a third-party dependency). Toolsets import it with `from toolstore.toolset import tool`.

---

## 4. Discovery & Registration

### 4.1 Toolset Discovery

A new `ToolsetManager` scans configured directories for `toolset.py` files:

```
toolsets/                    # configured toolset directory
├── weather/toolset.py       → name="weather", type="toolset"
├── github/toolset.py        → name="github", type="toolset"
└── calculator/toolset.py    → name="calculator", type="toolset"
```

Each directory containing a `toolset.py` is a toolset. The directory name becomes the tool name.

### 4.2 Registration

On scan, `ToolsetManager`:

1. Reads `doc.md` from the toolset directory.
2. Imports `toolset.py` in a controlled way (parses `@tool`-decorated functions without executing them).
3. Extracts function names, signatures, docstrings, and parameter info.
4. Builds a tool definition with a proper JSON Schema input.

### 4.3 Tool Definition (index entry)

```json
{
  "name": "weather",
  "type": "toolset",
  "description": "Get weather data from public APIs.",
  "source": "toolset",
  "toolset_dir": "/path/to/toolsets/weather",
  "doc": "<raw doc.md content>",
  "bindings": {
    "get_weather": {
      "description": "Get current weather for a location.",
      "parameters": {
        "location": {"type": "string", "required": true},
        "units": {"type": "string", "required": false, "default": "metric"}
      }
    },
    "get_forecast": {
      "description": "Get 5-day forecast for a location.",
      "parameters": {
        "location": {"type": "string", "required": true},
        "days": {"type": "integer", "required": false, "default": 5}
      }
    }
  },
  "schema": {
    "input_schema": {
      "type": "object",
      "properties": {
        "function": {
          "type": "string",
          "enum": ["get_weather", "get_forecast"],
          "description": "Which function to call in this toolset"
        },
        "location": {"type": "string", "description": "..."},
        "units": {"type": "string", "description": "..."},
        "days": {"type": "integer", "description": "..."}
      }
    }
  }
}
```

---

## 5. Execution Model

### 5.1 Flow

```
tool_store_tool(action="execute", tool_name="weather",
                function="get_weather", location="London", units="metric")
  │
  ├─ index_manager.get_tool("weather") → type="toolset"
  │
  └─ _execute_toolset(tool, args)
       │
       ├─ 1. Read toolset.py from disk
       ├─ 2. Extract function "get_weather" from args
       ├─ 3. Load module in warm Docker worker
       │     docker_pool.get_worker().load_module(name, code)
       ├─ 4. Call the function
       │     worker.call_function(name, "get_weather", fn_args, timeout)
       └─ 5. Return JSON result
```

### 5.2 Sandbox (reuses `docker_pool.py`)

Same warm Docker worker as today's docker tools. The worker:
- Loads the Python module (with `@tool` decorator available in its environment)
- Calls `get_tool(name)` to get the function
- Calls the function with the agent's arguments
- Serializes the return value as JSON

### 5.3 Argument Passing

The `function` argument selects which `@tool` function to call. All other arguments are passed as kwargs to the function:

```python
agent calls:  arguments={"function": "get_weather", "location": "London", "units": "metric"}
becomes:      get_weather(location="London", units="metric")
```

If `function` is omitted and there's only one `@tool` function, it's called directly.

---

## 6. What Gets Removed

### 6.1 Client (`toolstore/`)

| File                  | Change |
|-----------------------|--------|
| `native_tool.py`      | Remove `_execute_api()` (L200-227), `_execute_docker()` (L308-357), and their branches in `_do_execute()`. Add `_execute_toolset()`. |
| `mcp_server.py`       | Remove `_execute_api()` (L176-197), add `_execute_toolset()`. Remove api/docker from dispatch. |
| `cli.py`              | Remove `publish-api`, `publish-docker` commands. Add `publish-toolset` command. Remove api/docker interactive sections. |
| `schema_converter.py` | No changes needed (it already handles arbitrary tool defs by reading `schema`). |
| `index_manager.py`    | No changes. Type-agnostic. |
| `config_manager.py`   | Add `get_toolset_dirs()` alongside existing `get_skill_dirs()`. |
| `docker_pool.py`      | Update docstrings: "executes toolsets" instead of "docker tools". Add `@tool` decorator stub to the warm worker environment. |
| `transport.py`        | No changes (transport is MCP-only). |
| `management/server.py`| Remove api/docker UI and endpoints. Add toolset management. |
| `skill_manager.py`    | No changes. Skills stay as-is. |

### 6.2 Server (`server/app/`)

| File        | Change |
|-------------|--------|
| `models.py` | Remove `APITool` and `DockerTool` models. Add `ToolsetTool` model. |
| `main.py`   | Remove `/tools/api` and `/tools/docker` endpoints. Add `/tools/toolset` endpoint. |

### 6.3 New Files

| File                    | Purpose |
|-------------------------|---------|
| `toolstore/toolset.py`  | The `@tool` decorator module that toolsets import |
| `toolstore/toolset_manager.py` | Discovery, parsing, registration (reads doc.md + inspects toolset.py) |

---

## 7. Final Type Taxonomy

| Type      | Managed By | Description |
|-----------|------------|-------------|
| `mcp`     | Client     | External MCP servers (unchanged) |
| `skill`   | Client     | Human-centric SKILL.md progressive disclosure (unchanged) |
| `toolset` | Us         | Agent-centric: 1 doc + 1 code, `@tool` bindings, just runs |

All future "managed by us" extensibility goes through `toolset`. No other custom types.

---

## 8. Key Design Decisions

1. **`@tool` is a Python decorator, not a markdown annotation.** It lives in the code file, where code belongs. Simple, standard Python.
2. **1 doc + 1 code. Exactly two files.** No subdirectories, no scripts/, no assets/, no SKILL.md. Frictionless for agents.
3. **Agents just execute.** No progressive disclosure, no load/files/file/run. One call: `execute`.
4. **Skills stay human-centric.** Toolsets are the agent-centric sibling, not a replacement.
5. **Same warm Docker worker.** `docker_pool.py` is repurposed, not rewritten.
6. **The `@tool` decorator IS the binding.** Function name = binding name. Docstring = description. Signature = schema. No duplication.

---

## 9. Example: Converting API → Toolset

### Before (api JSON)

```json
{
  "name": "weather-api",
  "type": "api",
  "endpoint": "https://api.weather.com/data",
  "method": "GET",
  "parameters": {
    "location": {"type": "string", "required": true},
    "units": {"type": "string", "required": false, "default": "metric"}
  }
}
```

### After (toolset)

**`weather/doc.md`:**
```markdown
# Weather Toolset

### get_weather
Get weather for a location.
- `location` (string): City name
- `units` (string, default "metric"): metric or imperial
```

**`weather/toolset.py`:**
```python
from toolstore.toolset import tool

@tool
def get_weather(location: str, units: str = "metric"):
    """Get current weather for a location."""
    import httpx
    resp = httpx.get(
        "https://api.weather.com/data",
        params={"location": location, "units": units}
    )
    resp.raise_for_status()
    return resp.json()
```

Agent calls it:
```
tool_store(action="execute", tool_name="weather",
           arguments={"function": "get_weather", "location": "London"})
```

### Before (docker JSON)

```json
{
  "name": "calculator",
  "type": "docker",
  "code": "def main(a, b, op): ...",
  "function": "main"
}
```

### After (toolset)

**`calculator/doc.md`:**
```markdown
# Calculator Toolset

### compute
Basic arithmetic.
- `a` (number): First operand
- `b` (number): Second operand
- `op` (string): add, subtract, multiply, divide
```

**`calculator/toolset.py`:**
```python
from toolstore.toolset import tool

@tool
def compute(a: float, b: float, op: str = "add"):
    """Basic arithmetic."""
    ops = {"add": a + b, "subtract": a - b,
           "multiply": a * b, "divide": a / b}
    return {"result": ops[op]}
```

---

## 10. Migration Path

### Phase 1: Add toolset (zero breaking changes)
1. Create `toolstore/toolset.py` (the `@tool` decorator).
2. Create `toolstore/toolset_manager.py`.
3. Add `_execute_toolset()` in `native_tool.py`.
4. Add toolset dispatch in `mcp_server.py`.
5. Add toolset to `config_manager.py`.
6. Add server-side `ToolsetTool` model + endpoint.
7. Add `publish-toolset` CLI command.

All four types coexist. No existing tool breaks.

### Phase 2: Convert existing tools
1. Migration script: api JSON → toolset directory.
2. Migration script: docker JSON → toolset directory.
3. Convert all examples and reference tools.

### Phase 3: Remove api and docker
1. Delete `_execute_api()` + `_execute_docker()` from native_tool.py and mcp_server.py.
2. Remove `APITool` + `DockerTool` from server models.
3. Remove api/docker CLI commands, endpoints, UI sections.
4. Clean up stale references.

### Phase 4: Polish
1. Per-toolset timeout and env var config.
2. Toolset validation CLI (`toolstore validate-toolset <path>`).
3. Support for Node.js toolsets (`runtime: node` → warm Node container).
4. Package dependency declarations.
