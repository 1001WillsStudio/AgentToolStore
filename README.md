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
  <img src="https://img.shields.io/badge/functions-40%2B-green" alt="40+ functions">
  <img src="https://img.shields.io/badge/license-MIT-purple" alt="MIT">
  <img src="https://img.shields.io/badge/registry-live-brightgreen" alt="live">
</p>

# 🛠️ AgentToolStore

**The shared index that turns a scattered collection of tools into a unified,
searchable, versioned ecosystem.** Same role PyPI plays for Python packages,
npm for JavaScript — but for agent-callable toolsets.

> **Live registry:** [mrw33554432-agenttoolstore.hf.space](https://mrw33554432-agenttoolstore.hf.space)
> — browse, search, and publish toolsets.

---

## Adding ToolStore to Your Agent

ToolStore gives your agent a single `tool_store` function that unlocks every
published toolset.  Add it once, and your agent can search, inspect, and
execute any toolset from the registry — **no per-toolset wiring needed**.

### 1. Install

```bash
pip install toolstore
```

Or from source:

```bash
git clone https://github.com/Mrw33554432/AgentToolStore.git
cd AgentToolStore
pip install -e client/
```

### 2. Register the `tool_store` tool in your agent

Import the native tool function and add it to your agent's tool list:

```python
from toolstore.native_tool import tool_store_tool

# Add to your agent's tools (example: OpenAI function-calling agent)
tools = [
    {
        "type": "function",
        "function": {
            "name": "tool_store",
            "description": "A universal tool manager that lets you search, inspect, and execute thousands of tools and local utilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["search", "info", "execute"],
                        "description": "The action to perform: 'search' for tools, 'info' to get a tool definition, 'execute' to run a tool"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (required for action='search')"
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to inspect or execute (required for action='info'/'execute')"
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Arguments to pass to the tool (required for action='execute')"
                    }
                },
                "required": ["action"]
            }
        }
    }
]

# Wire up the handler in your agent loop
def handle_tool_call(tool_name: str, arguments: dict) -> str:
    if tool_name == "tool_store":
        return tool_store_tool(**arguments)
    # ... other tools ...
```

### 3. How agents use it — the three-step flow

**Step 1 — Search** for relevant tools:

```json
// agent calls
tool_store(action="search", query="parse xlsx file")

// returns
"Found 2 tools:
- xlsx-toolkit (toolset): Read, create, and manipulate Excel files
- pdf-toolkit (toolset): Extract text, metadata, and form fields from PDFs"
```

**Step 2 — Inspect** a tool to see its functions and parameters:

```json
// agent calls
tool_store(action="info", tool_name="xlsx-toolkit")

// returns the full tool definition with bindings, parameters, and docs
```

**Step 3 — Execute** a function from the toolset:

```json
// agent calls
tool_store(action="execute", tool_name="xlsx-toolkit", arguments={
    "function": "xlsx_read",
    "filepath": "/workspace/data.xlsx"
})

// returns the JSON result from the function
```

### 4. What happens during execution

ToolStore executes **in-process** — no Docker, no sandbox, no network round-trips
beyond the initial fetch:

1. **Code is fetched** from the registry (cached locally after first download)
2. **Dependencies are checked** — if a toolset needs `openpyxl` or `pdfplumber`,
   the agent receives a clear error listing what to install.  Nothing is ever
   auto‑installed.
3. **The function is imported and called** with the arguments the agent provides
4. **Results are returned** as JSON

The safety model is identical to skills: all code is visible in the registry,
dependencies are explicit, and the agent controls what gets installed.

### 5. Full agent loop example

```python
import json
from toolstore.native_tool import tool_store_tool

def agent_tool_router(tool_name: str, args: dict) -> str:
    """Route tool calls to the right handler."""
    if tool_name == "tool_store":
        return tool_store_tool(**args)

    # Your other tools here...
    return json.dumps({"error": f"Unknown tool: {tool_name}"})

# Simulated agent conversation:
# 1. Agent searches for spreadsheet tools
result = agent_tool_router("tool_store", {
    "action": "search",
    "query": "spreadsheet"
})
print(result)

# 2. Agent inspects the xlsx-toolkit
result = agent_tool_router("tool_store", {
    "action": "info",
    "tool_name": "xlsx-toolkit"
})
print(result)

# 3. Agent reads an Excel file
result = agent_tool_router("tool_store", {
    "action": "execute",
    "tool_name": "xlsx-toolkit",
    "arguments": {
        "function": "xlsx_read",
        "filepath": "/workspace/report.xlsx"
    }
})
print(result)
```

### 6. Local-only usage (no registry)

You can also use toolsets directly from a local directory without any registry:

```python
from toolstore.exec_tools import _execute_toolset_local

result = _execute_toolset_local(
    toolset_path="./toolsets/xlsx-toolkit",
    function_name="xlsx_read",
    filepath="/workspace/data.xlsx"
)
print(result)
```

---

## What's a Toolset?

A **toolset** is a directory containing:

```
my-toolkit/
├── toolset.py   ← @tool functions (code bindings)
└── doc.md       ← guidance, process, best practices (the skill)
```

Two kinds exist:

| Type | `toolset.py` | `doc.md` | Example |
|------|-------------|----------|---------|
| **Code toolset** | Real `@tool` functions | Full docs | `xlsx-toolkit`, `file-verify` |
| **Doc-only toolset** | Minimal module, no `@tool` | Full skill doc | `stuck-toolkit` |

Every function decorated with `@tool` becomes a callable binding that agents
discover and execute. The `doc.md` serves as both human documentation and
agent guidance — the same content a skill would provide, now paired with code.

---

## Toolsets Catalog

### 📄 Documents

| Toolset | Functions | Deps |
|---------|-----------|------|
| **xlsx-toolkit** | `xlsx_read`, `xlsx_sheets`, `xlsx_to_csv`, `xlsx_create` | `openpyxl` |
| **pdf-toolkit** | `pdf_extract`, `pdf_meta`, `pdf_merge`, `pdf_form_fields` | `pdfplumber`, `PyPDF2` |
| **docx-toolkit** | `docx_read`, `docx_info`, `docx_extract_tables`, `docx_create` | `python-docx` |
| **pptx-toolkit** | `pptx_read`, `pptx_info`, `pptx_create` | `python-pptx` |

### 🔧 Utility

| Toolset | Functions | Deps |
|---------|-----------|------|
| **text-transform** | `text_diff`, `regex_extract`, `markdown_table`, `text_stats` | stdlib |
| **file-verify** | `check_json`, `check_yaml`, `check_csv`, `file_hash`, `detect_encoding` | `chardet` (opt) |
| **calc-toolkit** | `eval_expression`, `convert_unit`, `basic_stats` | stdlib |
| **text-gen** | `lorem_words`, `lorem_paragraphs`, `generate_sentences`, `generate_data` | stdlib |
| **batch-ops** | `batch_rename`, `batch_find_replace`, `batch_stats`, `batch_copy` | stdlib |

### 🧠 Guidance & Diagnostics

| Toolset | Functions | Deps |
|---------|-----------|------|
| **debug-toolkit** | `analyze_error`, `extract_log_patterns` | stdlib |
| **webapp-testing** | `check_url`, `extract_urls` | stdlib |
| **doc-coauthoring** | `document_outline`, `markdown_template` | stdlib |
| **internal-comms** | `comms_template`, `format_bullets` | stdlib |
| **stuck-toolkit** | *doc-only — no code bindings* | — |

---

## Quick Start (CLI)

### Use toolsets directly from the command line

```bash
toolstore update                          # pull registry index
toolstore use text-transform \
    --function text_stats \
    text="The quick brown fox..."
```

### Publish a toolset

```bash
toolstore login --username <user> --password <pass>
toolstore toolset publish ./toolsets/my-toolkit
```

### Write a toolset

```python
# toolsets/my-toolkit/toolset.py
from toolstore.toolset import tool

@tool
def my_function(*, input: str, count: int = 1) -> dict:
    """Do something useful.

    Args:
        input: The input text.
        count: How many times.
    """
    return {"result": input * count}
```

The `@tool` decorator auto-generates the OpenAI function-calling schema from
type hints and docstrings — no manual JSON needed.

---

## Architecture

```
┌──────────────┐     publish      ┌──────────────────┐
│  toolset.py  │ ────────────────→│  ToolStore        │
│  + doc.md    │                  │  Registry (HF)    │
└──────────────┘                  └────────┬─────────┘
                                          │
    ┌──────────┐    toolstore update      │
    │  Agent   │ ←────────────────────────┘
    │          │
    │  tool_   │    execute              ┌──────────────┐
    │  store() │ ───────────────────────→│  temp dir     │
    │          │                        │  + pip deps   │
    └──────────┘                        │  + import     │
                                         │  + call fn    │
                                         └──────────────┘
```

Toolsets execute **in‑process** — no Docker, no sandbox. Code is fetched from
the registry on demand, written to a temp directory, dependencies installed
(explicitly, not automatically), then imported and called.

**Safety model:** same as skills. All code is visible in the registry.
Dependencies are never auto‑installed — the agent sees what's needed and
decides whether to install.

---

## Development

### Setup

```bash
git clone https://github.com/Mrw33554432/AgentToolStore.git
cd AgentToolStore
pip install -e client/
```

### Run tests

```bash
# Test a toolset locally
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ts', 'toolsets/text-transform/toolset.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.text_stats(text='Hello world.'))
"

# Test via CLI
toolstore use text-transform --function text_stats text="Hello world."
```

### Registry

The default registry is the public HF Space:
```
https://mrw33554432-agenttoolstore.hf.space/index.json
```

Change it via settings or `TOOLSTORE_REGISTRY_URL` env var.

---

## Contributing

1. Write a toolset: `toolsets/<name>/toolset.py` + `doc.md`
2. Use `@tool` decorator on every callable function
3. Never add placeholder functions — code or nothing
4. Test via `toolstore use` before submitting
5. PR against `main`

---

## License

MIT — see [LICENSE](LICENSE)
