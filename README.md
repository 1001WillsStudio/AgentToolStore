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

## Quick Start

### Use toolsets (as an agent)

```
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
