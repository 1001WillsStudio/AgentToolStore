# ToolStore - PyPI for AI Agents 🤖

> An open-source package repository and management system for AI agent tools

[![Status](https://img.shields.io/badge/status-planning-yellow)]()
[![License](https://img.shields.io/badge/license-TBD-blue)]()

---

## 🎯 Vision

**ToolStore is to AI agents what PyPI is to Python developers.**

A centralized, open-source repository where:
- **Developers** can publish and share tools for AI agents
- **Agents** can discover and execute tools autonomously
- **Everyone** benefits from a thriving ecosystem of reusable capabilities

**Key Innovation:** Unlike traditional package managers, most ToolStore tools are **API-based** - no installation required. Agents can discover and use tools instantly.

---

## 📚 Documentation

This repository currently contains planning documents:

- **[PROJECT_PLAN.md](PROJECT_PLAN.md)** - Comprehensive project plan
  - Core functionality (Publish, Discover, Install, Execute)
  - Architecture (Repository, Client Library, Package Format)
  - Development phases and roadmap
  - Success metrics and open questions

- **[PLAN_REVIEW.md](PLAN_REVIEW.md)** - Critical analysis
  - Major issues identified in original approach
  - How the "PyPI for agents" framing changed everything
  - Comparison of old vs. new focus
  - Lessons learned

- **[ECOSYSTEM_COMPARISON.md](ECOSYSTEM_COMPARISON.md)** - Learning from others
  - Analysis of PyPI, npm, Docker Hub, Maven, etc.
  - Best practices to adopt
  - Common pitfalls to avoid
  - ToolStore-specific considerations

---

## 🏗️ Core Components

### 1. Central Repository (Server)
- Tool registry with full definitions
- Index generation (~5-10 MB, 10,000+ tools)
- Publishing API for developers
- Web interface for browsing
- User authentication and verification

### 2. Client (Local)
**V1 Features:**
- CLI tool (`toolstore update`, `toolstore search`, `toolstore use`)
- Runs as MCP server (agents connect via MCP)
- HTTP API for agent integration
- Local index with instant search (SQLite FTS)
- API tool executor (HTTP client)
- MCP server manager (process lifecycle)
- Personal tool registry

**V2 Features (Future):**
- Docker sandbox manager
- Auto-container deployment
- Resource monitoring

### 3. Tool Types

**API Tools (80%):**
- HTTP endpoints
- Full definition in index
- No installation needed
- Instant execution

**MCP Servers (15%):**
- Local/remote processes
- ToolStore manages lifecycle
- JSON-RPC communication
- File system access, etc.

**Sandboxed Tools (5%, V2):**
- Docker containers
- Auto-managed by ToolStore
- Isolated execution
- Agent-autonomous

---

## ⚠️ V1 Limitations

To ship faster and validate the core concept, V1 has intentional limitations:

### What V1 Supports
- ✅ **Public APIs** (Auth-free utilities)
- ✅ **MCP Servers** (High-value tools using Env Vars for auth)
- ✅ **Local/Network Tools** (User-hosted APIs handling their own auth)
- ✅ Discovery & Execution (The core value)

### What's Deferred to V2
- ❌ **ToolStore-Managed Auth** (Vaults, OAuth flows, Key rotation)
- ❌ **Sandboxed Tools** (Docker, Code downloads)

**Rationale:** V1 provides access to *all* tools via MCP/Local proxies without needing a complex password manager built-in. Users manage their own keys; ToolStore manages discovery and connection.

---

## 🚀 Quick Start (Future)

Once implemented, the workflow will be:

### For Developers
```bash
# Create API tool definition
$ toolstore init my-weather-tool --type api

# Define endpoint and schema
$ toolstore publish
✓ Published weather-api v1.0.0
```

### For Agents

**Via CLI:**
```bash
# Update index
$ toolstore update

# Search tools
$ toolstore search "weather"

# Execute tool
$ toolstore use weather-api --city "San Francisco"
```

**Via Tool Calls:**
```json
// Agent calls ToolStore functions
{"tool": "toolstore.search", "params": {"query": "weather"}}
{"tool": "toolstore.execute", "params": {"tool": "weather-api", "city": "SF"}}
```

**Integration:**
- ToolStore runs as MCP server
- Agents connect via MCP protocol
- Or use HTTP API for RESTful access
- Or execute CLI commands

### Key Features
- 🚀 **Instant discovery** - Search 10,000+ tools locally (0.02s)
- ⚡ **No installation** - API tools work immediately
- 🔒 **Secure** - No code execution (V1), auth-free APIs only
- 🎯 **Agent-native** - CLI + Tool calls, no Python imports needed
- 🔌 **MCP compatible** - First-class MCP server
- 🌐 **Public APIs** - V1 focuses on open, auth-free APIs

---

## 🎯 Key Features (Planned)

### For Developers
- ✅ Simple publishing workflow
- ✅ Automated validation and testing
- ✅ Version management
- ✅ Auto-generated documentation
- ✅ Usage analytics

### For Agents
- ✅ **Agent-native interfaces** (CLI + Tool calls)
- ✅ **Instant search** (local, 0.02s)
- ✅ **No installation** (API tools work immediately)
- ✅ **MCP server** (native integration)
- ✅ **Personal registry** (add custom tools)
- ✅ Tool recommendations
- ✅ Unified execution interface

### For Everyone
- ✅ Open-source and community-driven
- ✅ Security scanning and verification
- ✅ Web interface for browsing
- ✅ Ratings and reviews
- ✅ MCP compatibility
- ✅ Private registries for enterprises

---

## 🔒 Security First

Learning from PyPI, npm, and Docker Hub security incidents:

- **Package signing** - Cryptographic verification
- **2FA required** - For all publishers
- **Malware scanning** - Automated security checks
- **Sandboxed execution** - Isolate tool execution
- **Namespace protection** - Prevent typosquatting
- **Code review** - For popular packages
- **Vulnerability database** - Track known issues

---

## 🗺️ Development Roadmap

### V1: API-Only Tools (20 weeks)

**Phase 1-2: Foundation** (Week 1-4)
- [ ] Tool definition format (API + MCP)
- [ ] Registry server + database
- [ ] Index generation system
- [ ] User authentication

**Phase 3-4: Client & Execution** (Week 5-8)
- [ ] CLI tool (`update`, `search`, `use`)
- [ ] Local index with FTS search
- [ ] API tool executor
- [ ] Error handling

**Phase 5-6: MCP & Personal Registry** (Week 9-12)
- [ ] MCP server integration
- [ ] Personal tool registry
- [ ] Configuration management

**Phase 7-8: Polish** (Week 13-16)
- [ ] Web interface
- [ ] ToolStore as MCP server
- [ ] HTTP API for agents
- [ ] Documentation

**Phase 9-10: Production** (Week 17-20)
- [ ] CDN integration
- [ ] Community features
- [ ] Monitoring

### V2: Authentication & Sandboxed Tools (Future)
- [ ] **Authentication support** (API keys, OAuth, JWT)
- [ ] Secure credential storage
- [ ] Docker-based sandboxes
- [ ] Auto-managed containers
- [ ] Agent-autonomous installation
- [ ] Resource limits & monitoring

### V3: Advanced Features (Long-term)
- [ ] AI-powered semantic search
- [ ] Tool composition/chaining
- [ ] Private registries
- [ ] Enterprise features

---

## 🤝 Challenges & Solutions

| Challenge | Solution Approach |
|-----------|------------------|
| **Security** | Multi-layered: signing, scanning, sandboxing, review |
| **Scale** | CDN, caching, efficient search indexing |
| **Dependencies** | Robust resolution algorithm, lock files |
| **Discovery** | AI-powered search, recommendations, curation |
| **MCP Integration** | First-class support, bidirectional conversion |
| **Sustainability** | Donations, sponsorships, optional enterprise features |

---

## 🌟 Inspiration

ToolStore draws inspiration from:
- **PyPI** - Python's package repository
- **npm** - JavaScript's package manager
- **Docker Hub** - Container registry
- **Homebrew** - macOS package manager
- **Crates.io** - Rust's package registry
- **MCP** - Model Context Protocol

But designed specifically for the unique needs of AI agents.

---

## 📊 Success Metrics

We'll measure success by:
- Number of published tools
- Number of registered developers
- Total downloads
- Package quality scores
- Agent framework integrations
- Community engagement

---

## 🔮 Future Vision

Beyond the initial release:
- **Tool composition** - Chain tools together
- **Async/streaming** - Long-running tool executions
- **Federation** - Multiple ToolStore instances
- **Marketplace** - Monetization for tool creators
- **Analytics** - Usage insights for developers
- **AI-powered discovery** - Natural language tool search

---

## 🤲 Contributing

This project is in the planning phase. We welcome:
- Feedback on architecture and design
- Suggestions for features
- Security considerations
- Comparison with similar systems
- Ideas for governance and sustainability

*(Contribution guidelines will be added once development begins)*

---

## 📝 License

TBD - Will be open-source (likely MIT or Apache 2.0)

---

## 📧 Contact

Project is currently in planning phase.

---

## ⭐ Status: Planning Complete → Implementation Ready

**Current Focus**: Ready to begin V1 implementation

**Architecture Finalized**:
- ✅ Local index with full tool definitions
- ✅ API-first approach (V1)
- ✅ MCP as first-class citizen
- ✅ Personal tool registry
- ✅ Sandboxed tools (V2 feature)

**Next Steps**:
1. Choose tech stack (recommend: Python + FastAPI + PostgreSQL)
2. Set up repository structure
3. Define detailed API specifications
4. Begin Phase 1: Foundation (Week 1-2)

**Timeline**: 20 weeks to V1 MVP

---

## 📖 Documentation

- **[PROJECT_PLAN.md](PROJECT_PLAN.md)** - Detailed technical specifications and architecture.
- **[AGENT_INTEGRATION.md](AGENT_INTEGRATION.md)** - Guide on how agents use ToolStore (CLI & Tool Calls).

---

## ⭐ Status & Next Steps

**Status:** Planning Complete → Ready for Implementation

**Immediate Next Steps:**
1. **Tech Stack Selection:** Recommended Python + FastAPI (Server) and Python/Go (CLI).
2. **Repository Setup:** Initialize Git structure for `server/` and `client/`.
3. **Phase 1 Implementation:** Begin "Foundation & Specifications" phase.

**Timeline:** 20 weeks to V1 MVP.

---

**Last Updated**: November 24, 2025

