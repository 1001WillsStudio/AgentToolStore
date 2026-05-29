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
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://via.placeholder.com/800x200/1a1a2e/eee?text=🛠️+AgentToolStore">
    <img alt="AgentToolStore" src="https://via.placeholder.com/800x200/ffffff/333?text=🛠️+AgentToolStore" width="600">
  </picture>
</p>

<p align="center">
  <strong>The "pip for AI Agents" — one tool store, every agent, any tool.</strong>
</p>

<p align="center">
  <a href="#-the-vision">Vision</a> ·
  <a href="#-the-problem">Problem</a> ·
  <a href="#-how-it-works">How It Works</a> ·
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#-tool-types">Tool Types</a> ·
  <a href="#-roadmap">Roadmap</a> ·
  <a href="#-contributing">Contributing</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10%2B-306998.svg" alt="Python 3.10+"></a>
  <a href="#"><img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha"></a>
</p>

---

## 💡 The Vision

Python didn't conquer the world because it was the fastest language. It won because of **pip** —
a single command that gave every developer instant access to 500,000+ libraries.

AI agents today each speak their own tool language — and that's fine.  Claude Desktop
has MCP.  GPT has function calling.  Most frameworks already support skills.

The problem isn't that these formats are incompatible.  It's that there is no
**universal meta-tool** that every agent can reach for.  Every agent reimplements
discovery from scratch.  Every project rebuilds its tool catalog.  There's no shared
layer that grows with the ecosystem — nothing like what `pip` did for Python.

**AgentToolStore is that layer.**

Think of it not as a bridge between formats, but as pip: a single, well-maintained
meta-tool that any agent — regardless of framework — can use to discover and invoke
tools.  Once an agent knows `tool_store_tool(...)`, it gains access to every API,
every MCP server, every skill, and every sandboxed code module ever published.
No per-framework wiring.  No reinvention.  Just one tool to rule them all.

> 🚀 **Our goal**: make `toolstore install` as obvious and universal for AI agents as
> `pip install` is for Python developers today.

---

## 🙏 Help Us Build This — Every Contribution Matters

This project is not backed by a big company or VC funding.  It's a moonshot by a
small group of people who believe the agent ecosystem desperately needs a shared
tool layer — something as obvious and universal as `pip` is for Python.

**We cannot do this alone.  We need you.**

Whether you're an individual developer, an open-source enthusiast, a startup, or
an enterprise — there is a way for you to help.  This project will only succeed if
the community rallies behind it the way Python's community rallied behind pip.

| You are... | How you can help |
|-------------|-----------------|
| 🧑‍💻 **A developer** | Contribute code, write tools, improve docs, report bugs |
| 🏢 **An organization** | Sponsor development, run a private registry, publish internal tools, provide infrastructure |
| 🧪 **An early adopter** | Test the CLI, build integrations, give feedback on the API |
| 📢 **An advocate** | Star the repo, share the vision, write about it, present at meetups |
| 💰 **A sponsor** | Fund development directly — GitHub Sponsors, Open Collective, or reach out for custom partnerships |

> 🚨 **The window is open now.**  The agent ecosystem is still young.  The patterns
> that win today will define how agents work for the next decade.  If we build the
> shared tool layer now, every agent — regardless of framework — benefits forever.
> If we wait, fragmentation calcifies and the opportunity is lost.

**Reach out directly:** [<!-- email/contact placeholder -->]

---
## 🧩 The Problem

| Problem | The pain today | How AgentToolStore fixes it |
|---------|---------------|---------------------------|
| **No universal meta-tool** | There's no single, shared tool layer that every agent can use — every project reinvents discovery, every framework maintains its own catalog | One `tool_store_tool(...)` call gives any agent access to the entire tool ecosystem.  Like pip, it grows *with* the community instead of being rebuilt by each team. |
| **Execution risk** | Running third-party tool code directly on your infrastructure | Docker sandbox with client-side image approval — your rules, your boundaries |
| **Discovery friction** | No central place to find, compare, and trust tools | Search across _all_ tool types from one index; inspect schemas before running |
| **Ecosystem fragmentation** | Great tools exist (MCP servers, skills, APIs) but they're scattered across registries; no single place ties them together | A unified index that surfaces *all* tool types together — search once, find everything, regardless of origin or format |
| **Cold start** | Every new agent project starts from an empty tool set | One `toolstore update` gives you the entire public index |
| **Training-deployment gap** | Agent behaves differently in production because tools differ between dev/staging/prod — brittle, unpredictable behavior | Same tool index everywhere — the agent sees identical tools in training, eval, and deployment.  Deterministic, auditable, reproducible. |

---

### 🎯 Training–Deployment Coherence

Today, training an agent with one set of tools and deploying it with a different
set is a recipe for silent failure.  The agent learned to call `create_jira_ticket` in
staging, but production has a different endpoint — or no endpoint at all.  Even worse:
different teams wire up different tools, so an agent that works on one engineer's
machine breaks on another's.

A shared, public tool store solves this at the ecosystem level.  When most tools are
published to — and consumed from — a single registry, the **training environment and
deployment environment naturally converge**.  The agent that learned to search the web
via the public `web-search` tool in training will find that exact same `web-search`
tool waiting for it in production, with the same schema, same behavior, same
semantics.  No per-environment wiring.  No surprising gaps.

This is the same dynamic that made pip and npm indispensable: the bigger the shared
registry grows, the more homogenous the ecosystem becomes, and the fewer painful
"works on my machine" surprises you hit when moving from development to deployment.
**The network effect is the reliability mechanism.**

---

## 🏗️ Architecture

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

## 🛠️ Tool Types

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

## 🔒 Your Tools, Your Rules — Privacy by Default

Not every tool belongs on a public registry.  Internal APIs, proprietary business
logic, customer data pipelines — some tools should never leave your infrastructure.

AgentToolStore treats **public and private as equal citizens**:

- **Local MCP servers** — register an MCP server running on your machine or private
  network.  It appears in your tool index just like any public tool, but the registry
  never sees it.  Ideal for internal systems (Jira, databases, CI/CD) that contain
  credentials or proprietary data.

- **Local skills** — drop a `SKILL.md` file in `~/.toolstore/skills/` and it's
  immediately available.  Perfect for team-specific workflows, company playbooks,
  or anything you'd rather not upload.

- **No forced sharing** — publishing to the public registry is entirely optional.
  The CLI works perfectly offline with zero external dependencies once your local
  index is set up.

> 🏢 **For enterprises**: you can run a private registry server on your own
> infrastructure, giving your entire organization a shared, governed tool catalog
> without any data leaving your network.  The architecture is the same — just point
> `toolstore` at your own registry URL.

---

## 🔌 MCP Support

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

## 🚀 Quick Start

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

## 🤖 Using from an Agent

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

## 🔄 Schema Bridge

Tool definitions are automatically converted between three formats:

| Format | Used by |
|--------|---------|
| **ToolStore** (canonical) | Internal representation |
| **OpenAI function-calling** | GPT, compatible APIs |
| **MCP JSON Schema** | Claude Desktop, MCP clients |

A tool registered once works everywhere.  No format lock-in.

---

## ⚙️ Configuration

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

## 🗺️ Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **Alpha** | Core CLI, registry server, Docker sandbox, MCP client/server | 🚧 In progress |
| **Beta** | `pip install toolstore`, public registry, verified publishers, tool ratings | 📋 Planned |
| **1.0** | Ecosystem integrations (LangChain, CrewAI, AutoGen), SLA guarantees, enterprise auth | 📋 Planned |
| **Beyond** | Tool composition pipelines, marketplace monetization, federated registries | 💭 Exploring |

---

## 👥 Contributing & Support

This project lives or dies by its community.  We are actively, urgently looking for
contributors and supporters of every kind.  If this vision resonates with you,
**please get involved**.

### 💻 Code Contributions

- **Good first issues**: We tag beginner-friendly issues — look for the label
- **Core development**: The CLI (`client/`), registry server (`server/`), MCP
  protocol, Docker sandbox — all need work
- **Integrations**: Build connectors for LangChain, CrewAI, AutoGen, Semantic
  Kernel, and other agent frameworks
- **Tool publishing**: Publish high-quality tools to the registry — APIs, MCP
  servers, skills, and Docker tools are all welcome
- **Documentation**: Tutorials, API reference, examples, deployment guides

Please open an issue to discuss larger changes before submitting a PR.

### 🤝 Organizational Partnerships

If your company or organization wants to accelerate this project:

- **Run a private registry** for your internal tools — we'll help you deploy it
- **Sponsor specific features or milestones** — get priority development on what
  matters most to you
- **Provide infrastructure** — CI/CD, hosting for the public registry, Docker
  image registries
- **Second full-time contributors** — donate engineering time from your team

### 💰 Financial Sponsorship

Building universal infrastructure takes sustained effort.  Financial support lets
us work on this full-time and move faster.

| Tier | What it supports |
|------|------------------|
| 🌱 **Community** | Coffee for late-night coding sessions.  Every dollar counts. |
| 🌿 **Supporter** | Server costs, domain, CI/CD infrastructure |
| 🌳 **Sustainer** | Part-time dedicated development |
| 🏛️ **Enterprise** | Full-time development, SLA guarantees, dedicated support channel |

<!-- TODO: add actual sponsorship links (GitHub Sponsors, Open Collective, Patreon, etc.) -->

**To discuss sponsorship or partnership:** reach out directly — we'll set up a call
and figure out how we can work together.

### 🌟 Other Ways to Help

- **Star the repo** — it genuinely helps with visibility and discovery
- **Share the vision** — blog posts, tweets, talks, podcasts, newsletter mentions
- **Use it** — the more people building on AgentToolStore, the stronger the
  network effect becomes
- **Give feedback** — tell us what's broken, what's confusing, what's missing

### 📋 What We Need Most Right Now

- [ ] **Core contributors** — people who can own subsystems (MCP, Docker sandbox, schema bridge, registry server)
- [ ] **Tool publishers** — seed the registry with high-quality tools so early adopters see immediate value
- [ ] **Framework integrators** — build the connectors that make AgentToolStore a one-liner in every agent framework
- [ ] **Design partners** — organizations willing to deploy the private registry and give real-world feedback
- [ ] **Sponsors** — funding to move from nights-and-weekends to full-time development

> 💬 **The only wrong way to help is not helping at all.**  If you're not sure how
> you can contribute, just reach out — we'll find something meaningful for you.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for detailed contribution guidelines.

---

## 📁 Repository Structure

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

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  <strong>🌟 Star this repo · Share the vision · Join the mission 🌟</strong>
</p>

<p align="center">
  <sub>AgentToolStore is built in the open, for the community, by people who believe</sub><br>
  <sub>that AI agents deserve a shared tool ecosystem as rich and accessible as pip made Python.</sub><br>
  <sub>Be part of it.  <strong>One tool, every agent — let's make it real.</strong></sub>
</p>

