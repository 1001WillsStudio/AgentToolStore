# ToolStore - Package Repository for AI Agent Tools

## Overview
ToolStore is an open-source package repository and management system for AI agent tools - essentially "PyPI for AI agents". It provides a centralized registry where developers can publish tools, and agents can discover and execute them instantly.

**Key Innovation:** Unlike traditional package managers, ToolStore tools are primarily **API-based** - no installation required. The index contains full tool definitions (endpoints, schemas, authentication), enabling agents to use tools immediately after discovery.

**Architecture:** The platform combines:
- **Public Registry** - Centralized, searchable repository of tools
- **Local Index** - Downloaded catalog with full tool definitions
- **Personal Registry** - User's own tools and configurations
- **Client Library** - Manages discovery, execution, and MCP integration

## Core Functionality

### 1. Publish Tools (Developer Side)
Enable tool developers to share their tools:

#### 1.1 Tool Publishing
- CLI tool for publishing: `toolstore publish`
- Tool definition format (manifest + schema)
- Automated validation and testing
- Version management and semantic versioning

#### 1.2 Tool Definition
- Standardized manifest (name, version, author, endpoint)
- OpenAPI/JSON Schema for input/output
- Authentication configuration
- License, documentation, examples
- Categories, tags, and capabilities

#### 1.3 Tool Types
**V1 - API Tools:**
- HTTP API endpoints (most tools)
- MCP servers (local or remote)
- Fully defined in index

**V2 - Sandboxed Tools (Future):**
- Tools requiring installation
- Automatic Docker-based sandboxes
- Agent-autonomous execution

### 2. Discover Tools (Agent/User Side)
Instant, local-first discovery:

#### 2.1 Index-Based Search
- Download full index once: `toolstore update`
- Local search (instant, no network calls)
- Full-text search across tool metadata
- Filter by type, category, tags, popularity

#### 2.2 Tool Information
- Complete tool definitions in local index
- API endpoints, schemas, authentication
- Usage examples and documentation
- Ratings, downloads, and reviews

#### 2.3 Personal Registry
- Add custom tools: `toolstore add my-tool --endpoint URL`
- Company internal APIs
- Self-hosted MCP servers
- Merged view with public tools

### 3. Execute Tools (No Installation Needed)
**V1 - Direct Execution:**

#### 3.1 API Tools (Primary)
- Direct HTTP calls to tool endpoints
- No installation required
- **V1: Auth-free APIs only** (no API keys, no OAuth)
- **V2: Authentication support** (API keys, OAuth, JWT)
- Rate limiting and error handling

#### 3.2 MCP Server Tools
- **Ingestion**: At startup/update, ToolStore queries configured MCP servers for `tools/list` and adds them to the local search index.
- **Proxy Execution**: Agents call ToolStore. ToolStore forwards the call to the appropriate MCP server.
- **Abstraction**: The MCP server is completely hidden from the Agent. To the Agent, it looks identical to a local or API tool.
- **Connect-Only**: ToolStore connects to user-defined MCP servers (via stdio or HTTP).
- **No Lifecycle Management**: User is responsible for ensuring servers are runnable/running.

#### 3.3 Unified Interface
```python
# Same interface for all tool types:
tool = ts.get_tool("tool-name")
result = tool.execute(params)
```

**V2 - Sandboxed Execution (Future):**
- Automatic Docker container sandboxes
- Agent-autonomous tool installation
- Isolated, secure execution environment
- Resource limits and monitoring

## Architecture

The system consists of three main components:

### 1. Central Repository (Server Infrastructure)
The hosted registry service (like pypi.org):

#### 1.1 Tool Registry Database
- Store tool definitions and metadata
- Version management and history
- Download statistics and analytics
- User accounts and authentication

#### 1.2 Index Generation
- Generate unified index file (JSON)
- Contains **full tool definitions** for API tools
- Updated continuously as tools are published
- Served via CDN for fast downloads

#### 1.3 Publishing API
- Accept tool definitions from developers
- Validate manifest and schema
- Security scanning and verification
- Generate and manage API keys/tokens
- Namespace management (@username/tool-name)

#### 1.4 Web Interface
- Browse and search tools via web
- Tool documentation pages
- User/organization profiles
- Tool submission interface
- Statistics and dashboards

#### 1.5 Authentication & Authorization
- User registration and login
- API key management
- Tool ownership and permissions
- Rate limiting and abuse prevention

### 2. Client Library (Local Side)
The tool manager and execution engine:

#### 2.1 CLI Tool
**V1 Commands:**
- `toolstore update` - Download/update tool index
- `toolstore search <query>` - Search tools locally
- `toolstore use <tool> [args]` - Execute tool
- `toolstore info <tool>` - Show tool details
- `toolstore add <tool>` - Add custom tool to personal registry
- `toolstore publish` - Publish tools (for developers)
- `toolstore list` - List available tools

**V2 Commands (Future):**
- `toolstore sandboxes` - Manage running sandboxes
- `toolstore sandbox stop <tool>` - Stop sandbox

#### 2.2 Index Manager
- Download index from registry
- Store locally (~5-10 MB compressed)
- Merge with personal registry
- Update with delta patches
- SQLite cache for fast search

#### 2.3 Execution Engine
**API Tools:**
- Direct HTTP calls to endpoints
- Authentication header injection
- Response parsing and validation
- Error handling and retries

**MCP Server Tools:**
- Auto-start MCP servers (`npx`, Python, etc.)
- JSON-RPC client
- Process lifecycle management
- Keep-alive for performance

**V2 - Sandboxed Tools (Future):**
- Docker container management
- Automatic sandbox spin-up
- Request proxying to sandboxes
- Resource monitoring and cleanup

#### 2.4 Agent Integration
ToolStore is designed for agent use via two interfaces:

**1. CLI Commands** (for shell-based agents):
```bash
# Agent executes shell commands
toolstore search "weather"
toolstore use weather-api --city "SF"
```

**2. Tool Calls** (ToolStore as MCP Server/Tool):
```json
// Agent calls ToolStore functions
{
  "tool": "toolstore.search",
  "params": {"query": "weather"}
}

{
  "tool": "toolstore.execute",
  "params": {
    "tool_name": "weather-api",
    "args": {"city": "SF"}
  }
}
```

**ToolStore exposes itself as:**
- MCP server (agents connect via MCP protocol)
- HTTP API (agents call REST endpoints)
- CLI tool (agents execute shell commands)

### 3. Tool Definition Format

#### 3.1 API Tool Definition (V1 - Auth-Free)
```json
{
  "name": "public-holidays-api",
  "version": "1.0.0",
  "type": "api",
  "author": "username",
  "description": "Get public holidays for any country",
  "license": "MIT",
  "keywords": ["holidays", "api", "calendar"],
  
  "endpoint": {
    "url": "https://date.nager.at/api/v3/PublicHolidays",
    "method": "GET"
  },
  
  "auth": {
    "type": "none"
  },
  
  "schema": {
    "input": {
      "year": {"type": "integer", "required": true},
      "countryCode": {"type": "string", "required": true}
    },
    "output": {
      "date": {"type": "string"},
      "name": {"type": "string"},
      "localName": {"type": "string"}
    }
  },
  
  "examples": [
    {
      "input": {"year": 2025, "countryCode": "US"},
      "output": [
        {"date": "2025-01-01", "name": "New Year's Day"},
        {"date": "2025-07-04", "name": "Independence Day"}
      ]
    }
  ],
  
  "rate_limit": "none",
  "pricing": "free"
}
```

**V2 will add authentication:**
```json
{
  "auth": {
    "type": "api_key",
    "header": "X-API-Key",
    "user_provides": true
  }
}
```
```

#### 3.2 MCP Server Tool Definition
```json
{
  "name": "filesystem-tools",
  "version": "1.0.0",
  "type": "mcp-server",
  "author": "modelcontextprotocol",
  "description": "File system operations",
  
  "package": {
    "manager": "npm",
    "name": "@modelcontextprotocol/server-filesystem",
    "version": "^1.0.0"
  },
  
  "start_command": "npx -y @modelcontextprotocol/server-filesystem ${workdir}",
  
  "config_schema": {
    "workdir": {"type": "string", "required": true, "description": "Working directory"}
  },
  
  "provides_tools": [
    {
      "name": "read-file",
      "description": "Read file contents",
      "schema": {
        "input": {"path": {"type": "string"}},
        "output": {"content": {"type": "string"}}
      }
    },
    {
      "name": "write-file",
      "description": "Write content to file",
      "schema": {
        "input": {
          "path": {"type": "string"},
          "content": {"type": "string"}
        },
        "output": {"success": {"type": "boolean"}}
      }
    }
  ]
}
```

#### 3.3 Sandboxed Tool Definition (V2 - Future)
```json
{
  "name": "pdf-analyzer",
  "version": "2.0.1",
  "type": "sandboxed",
  "author": "username",
  "description": "Analyze PDF documents",
  
  "runtime": {
    "type": "docker",
    "image": "toolstore/pdf-analyzer:2.0.1",
    "dockerfile_url": "https://github.com/user/pdf-analyzer/Dockerfile"
  },
  
  "api": {
    "endpoint": "/execute",
    "method": "POST"
  },
  
  "resources": {
    "memory": "512MB",
    "cpu": "0.5",
    "timeout": 30
  },
  
  "execution": {
    "cold_start_time": "2-3s",
    "warm_execution_time": "50ms"
  },
  
  "schema": {
    "input": {"file_path": {"type": "string"}},
    "output": {"analysis": {"type": "object"}}
  },
  
  "permissions": ["filesystem_read"],
  "sandbox_compatible": true
}
```

### 4. Index Architecture

#### 4.1 Public Index (toolstore-index.json)
Downloaded from registry and cached locally:

```json
{
  "version": "2025-11-24T10:30:00Z",
  "schema_version": "1.0",
  "total_tools": 10234,
  
  "tools": [
    {
      // Full API tool definitions (80% of tools)
      "name": "weather-api",
      "type": "api",
      "endpoint": {...},
      "schema": {...},
      // Everything needed to execute
    },
    {
      // Full MCP server definitions (15% of tools)
      "name": "filesystem-tools",
      "type": "mcp-server",
      "package": {...},
      "start_command": "...",
      "provides_tools": [...]
    },
    {
      // V2: Sandboxed tool metadata (5% of tools)
      "name": "pdf-analyzer",
      "type": "sandboxed",
      "runtime": {...},
      "execution": {...}
    }
  ]
}
```

**Size:** ~5-10 MB compressed (10,000+ tools with full definitions)

#### 4.2 Personal Registry (~/.toolstore/local-tools.json)
User's custom tools:

```json
{
  "tools": [
    {
      "name": "my-company-api",
      "type": "api",
      "endpoint": {"url": "http://company.internal/api"},
      "schema": {...},
      "local": true
    },
    {
      "name": "my-mcp-server",
      "type": "mcp-server",
      "start_command": "python /path/to/server.py",
      "provides_tools": [...],
      "local": true
    }
  ]
}
```

#### 4.3 Merged View
Client merges public + personal registries:

```python
# Agent sees all tools:
ts.search("api")
# Returns: public tools + user's custom tools

# Agent uses any tool the same way:
ts.get_tool("my-company-api").execute(...)
ts.get_tool("weather-api").execute(...)
```

## Key Challenges

### 1. Security & Trust (V1)
- **Malicious Tools**: Validate API endpoints, prevent phishing
- **Endpoint Verification**: Ensure tools point to legitimate APIs
- **Namespace Squatting**: Prevent typosquatting and name confusion
- **Tool Verification**: Verified publisher program
- **Rate Limiting**: Protect against abuse
- **No Authentication**: V1 only accepts auth-free APIs (simplifies security)

**V2 Additions:**
- **Authentication Management**: API keys, OAuth, JWT storage/injection
- **Credential Security**: Secure storage, encryption, key rotation
- **Sandbox Security**: Docker isolation, resource limits
- **Image Verification**: Scan Docker images for vulnerabilities
- **Supply Chain**: Verify base images and dependencies

### 2. Index Management
- **Index Size**: Keep index small while including full definitions
- **Update Strategy**: Delta updates vs. full downloads
- **Compression**: Efficient compression (gzip, brotli)
- **Freshness**: Balance between updates and bandwidth
- **Search Performance**: Fast local search with SQLite/FTS
- **Offline Support**: Work without internet after initial download

### 3. MCP Compatibility
- **First-Class Integration**: MCP servers as native tool type
- **Process Management**: Start/stop MCP servers automatically
- **Protocol Support**: JSON-RPC over stdio/HTTP/WebSocket
- **Existing Tools**: Package existing MCP servers easily
- **Bidirectional**: Convert between ToolStore and MCP formats

### 4. Scalability & Infrastructure
- **CDN**: Fast index distribution globally
- **Index Generation**: Efficient continuous updates
- **API Rate Limiting**: Prevent abuse
- **Costs**: Sustainable hosting (small index vs. large packages)
- **Bandwidth**: Index updates vs. individual tool metadata queries

### 5. Tool Integration
- **API Standards**: Support OpenAPI, REST (V1: GET/POST only)
- **MCP Standards**: Support all MCP server types
- **Authentication**: V1 = none, V2 = API key/OAuth/JWT
- **Error Handling**: Standardize error responses across tools
- **Versioning**: Semantic versioning for tool APIs
- **Public APIs**: V1 focuses on public, open APIs without authentication

### 6. Agent Experience
- **Discovery Speed**: Instant local search
- **Execution Simplicity**: Same interface for all tool types
- **Error Messages**: Clear, actionable error messages
- **Cost Tracking**: Monitor API usage and costs
- **Offline Capability**: Validate inputs offline

### 7. Community & Governance
- **Moderation**: Content policy for tool descriptions
- **Dispute Resolution**: Name conflicts, copyright issues
- **Tool Deprecation**: Clear policies for removing tools
- **Funding**: Sustainable hosting model
- **Open Source**: Community contributions and governance

## V1 Scope and Limitations

### What's Included in V1

**✅ API Tools (Public):**
- Public APIs without authentication (e.g., weather, holidays, math)
- Simple GET/POST endpoints
- JSON request/response

**✅ User-Managed Tools (Bypass Auth):**
- **MCP Servers:** High-value tools (GitHub, Filesystem) where user sets env vars (e.g., `GITHUB_TOKEN`). ToolStore inherits env vars.
- **Local/Network APIs:** Users run their own servers (e.g., `localhost:8000` or internal corporate APIs). Authentication is handled by the network/server, so ToolStore calls them without managing keys.

**✅ Discovery:**
- Local index with full tool definitions
- Fast search (SQLite FTS)
- Personal registry for custom/local tools

**✅ Execution:**
- Direct HTTP calls to API endpoints
- MCP server process management
- Basic error handling

### What's Deferred to V2

**❌ ToolStore-Managed Authentication:**
- No secure storage/vault for API keys
- No OAuth flows managed by ToolStore
- No JWT management

**❌ Sandboxed Tools:**
- No Docker containers
- No code downloads
- No dependency installation

### Rationale

**V1 MVP Focus:**
- **Agent Autonomy:** Discovery and execution.
- **Power Users:** Allow users to bring their own auth (via MCP env vars or local proxies).
- **Speed:** Avoid building complex credential management UI/Vault.

**Result:** Agents get high-value tools (via MCP/Local) AND ease of use (Public APIs) without ToolStore becoming a password manager in V1.

---

## Key Architectural Decisions

### 1. Local Index vs. Server-Side Search
**Decision:** Local index with full tool definitions

**Rationale:**
- ✅ **Instant search** - No network latency (0.02s vs 200ms+)
- ✅ **Offline support** - Agents can search without internet
- ✅ **Privacy** - Server doesn't track searches
- ✅ **No rate limiting** - Unlimited local searches
- ✅ **Agent-friendly** - Agents may search thousands of times

**Implementation:**
- Download index once: `toolstore update`
- ~5-10 MB compressed for 10,000+ tools
- SQLite FTS for fast search
- Delta updates to minimize bandwidth

### 2. API-First vs. Local Code Execution
**Decision:** API-first for V1, sandboxed execution for V2

**Rationale:**
- ✅ **Security** - No arbitrary code execution
- ✅ **Instant availability** - No installation needed
- ✅ **Simplicity** - Smaller, simpler codebase
- ✅ **80% use case** - Most tools are APIs anyway

**V1 (MVP):**
- API tools only
- MCP servers (process-based, safe)
- No code downloads

**V2 (Future):**
- Sandboxed tools for advanced needs
- Docker-based isolation
- Agent-autonomous installation

### 3. MCP as First-Class Citizen
**Decision:** Native MCP support, not just compatibility

**Rationale:**
- ✅ MCP is the emerging standard for LLM tools
- ✅ Existing MCP servers can be packaged easily
- ✅ ToolStore adds discovery layer MCP lacks
- ✅ Process-based execution is safe

**Integration:**
- MCP servers defined in index
- ToolStore manages process lifecycle
- Auto-start on first use
- Keep-alive for performance

### 4. Personal Registry
**Decision:** Users can add custom tools to local registry

**Rationale:**
- ✅ Company internal APIs
- ✅ Development/testing
- ✅ Self-hosted tools
- ✅ No barrier to use ToolStore

**Implementation:**
- `~/.toolstore/local-tools.json`
- Merged with public index at runtime
- Same interface for public and custom tools

### 5. Index Contains Full Definitions
**Decision:** Index includes complete tool definitions (endpoints, schemas)

**Rationale:**
- ✅ No secondary lookup needed
- ✅ Agents can use tools immediately
- ✅ Validate inputs offline
- ✅ Generate usage examples locally

**Trade-offs:**
- ⚠️ Larger index size (~5-10 MB vs ~500 KB)
- ✅ But: Only downloaded once, cached locally
- ✅ Worth it for instant execution

### 6. No Package Dependencies
**Decision:** Tools don't depend on other tools (V1)

**Rationale:**
- ✅ Simplifies implementation
- ✅ No dependency resolution needed
- ✅ No version conflicts
- ✅ Each tool is self-contained

**Future (V2):**
- May add tool composition/chaining
- But: Optional, not required

---

## Additional Features

### 1. Tool Range & Scoping
- Limit provided tools to a smaller, curated subset
- Create tool groups/collections (like "data-science-tools")
- Context-aware tool filtering
- User/agent-specific tool access
- Private registries for organizations
- Namespace management (@username/tool-name)

### 2. Community Features
- Tool ratings and reviews
- Download statistics and trending
- User profiles and reputation
- Package favorites/stars
- Discussion forums per tool
- Issue tracking integration

### 3. Quality & Discovery
- Automated testing and CI badges
- Documentation scoring
- Code quality metrics
- Example galleries
- Tutorial integration
- "Awesome lists" curated collections

### 4. Advanced Capabilities
- Tool composition and chaining
- Async/streaming tool execution
- Tool proxies and rate limiting
- A/B testing for tool versions
- Tool usage analytics
- Webhook notifications

### 5. Enterprise Features
- Private package hosting
- SSO integration
- Audit logs
- SLA guarantees
- Priority support
- Bulk licensing

## Technology Stack (To Be Determined)
- **Language**: Python, TypeScript, or Go
- **API Framework**: FastAPI, Express, or similar
- **Protocol**: REST, gRPC, or WebSocket
- **Storage**: SQLite/PostgreSQL for tool registry
- **Cache**: Redis for performance

## Development Phases

### V1: API-Only Tools (MVP)

#### Phase 1: Foundation & Specifications (Week 1-2)
- [ ] Define tool definition format (API + MCP)
- [ ] Design registry database schema
- [ ] Define index structure (JSON format)
- [ ] Create REST API specification
- [ ] Choose tech stack (Python + FastAPI + PostgreSQL)

#### Phase 2: Registry Server (Week 3-4)
- [ ] Basic registry server (tool submission, storage)
- [ ] Index generation system
- [ ] User authentication and API keys
- [ ] Tool validation (manifest, schema)
- [ ] SQLite/PostgreSQL database

#### Phase 3: Client Library (Week 5-6)
- [ ] CLI tool skeleton
- [ ] `toolstore update` - Download index
- [ ] `toolstore search` - Local search (SQLite FTS)
- [ ] `toolstore info` - Show tool details
- [ ] Index manager and caching

#### Phase 4: Execution Engine (Week 7-8)
- [ ] API tool executor (HTTP client)
- [ ] HTTP GET/POST support
- [ ] Response parsing and validation
- [ ] Error handling and retries
- [ ] `toolstore use` command
- [ ] ⚠️ No authentication (V1 limitation)

#### Phase 5: MCP Integration (Week 9-10)
- [ ] MCP server process manager
- [ ] JSON-RPC client
- [ ] Auto-start MCP servers
- [ ] Keep-alive and cleanup
- [ ] MCP tool definitions in index

#### Phase 6: Personal Registry (Week 11-12)
- [ ] `toolstore add` - Add custom tools
- [ ] Local registry file (~/.toolstore/local-tools.json)
- [ ] Merge with public index
- [ ] Search across both registries
- [ ] Configuration management

#### Phase 7: Web Interface (Week 13-14)
- [ ] Basic web interface for browsing
- [ ] Tool detail pages
- [ ] Search functionality
- [ ] User profiles
- [ ] Tool submission form

#### Phase 8: Agent Integration (Week 15-16)
- [ ] ToolStore as MCP server
- [ ] Expose search/execute as MCP tools
- [ ] HTTP API for agent integration
- [ ] JSON-RPC interface
- [ ] Agent integration examples (LangChain, AutoGPT, etc.)

#### Phase 9: Production Ready (Week 17-18)
- [ ] CDN integration for index distribution
- [ ] Delta updates for index
- [ ] Compression optimization
- [ ] Rate limiting
- [ ] Monitoring and logging

#### Phase 10: Community Features (Week 19-20)
- [ ] Tool ratings and reviews
- [ ] Download statistics
- [ ] Trending tools
- [ ] Verified publishers program
- [ ] Documentation and examples gallery

---

### V2: Authentication & Sandboxed Tools (Future)

#### Phase 11: Authentication Support
- [ ] Credential storage (encrypted)
- [ ] API key injection
- [ ] OAuth 2.0 flows
- [ ] JWT token management
- [ ] Per-tool credential configuration
- [ ] Keyring integration (OS-level)
- [ ] Credential rotation and expiry

#### Phase 12: Sandbox Foundation
- [ ] Docker integration
- [ ] Container lifecycle management
- [ ] Sandbox tool definitions
- [ ] Auto-pull Docker images
- [ ] Basic sandbox execution

#### Phase 13: Sandbox Manager
- [ ] Auto-start sandboxes on first use
- [ ] Keep-alive strategy (5 min idle)
- [ ] Resource limits (memory, CPU, timeout)
- [ ] Multi-sandbox support
- [ ] `toolstore sandboxes` command

#### Phase 14: Security & Isolation
- [ ] Network isolation options
- [ ] Filesystem restrictions
- [ ] Resource monitoring
- [ ] Auto-cleanup
- [ ] Security scanning for Docker images

#### Phase 15: Developer Experience
- [ ] Dockerfile-based tool publishing
- [ ] Local testing workflow
- [ ] Sandbox debugging tools
- [ ] Performance optimization
- [ ] Documentation and guides

#### Phase 16: Cloud Sandboxes (Optional)
- [ ] ToolStore Cloud sandbox hosting
- [ ] Serverless-style execution
- [ ] Pay-per-use pricing
- [ ] Auto-scaling
- [ ] Hybrid local/cloud execution

---

### V3: Advanced Features (Long-term)

#### Phase 17: Enhanced Discovery
- [ ] AI-powered semantic search
- [ ] Natural language tool queries
- [ ] Tool recommendations
- [ ] Similar tools suggestions
- [ ] Curated collections

#### Phase 18: Tool Composition
- [ ] Chain tools together
- [ ] Workflow definitions
- [ ] Tool dependencies
- [ ] Parallel execution
- [ ] Error handling in chains

#### Phase 19: Enterprise Features
- [ ] Private registries
- [ ] SSO integration
- [ ] Audit logs
- [ ] Team management
- [ ] SLA guarantees

#### Phase 20: Ecosystem Growth
- [ ] Agent framework integrations (LangChain, AutoGPT, CrewAI)
- [ ] IDE plugins (cursor integration, etc.)
- [ ] CI/CD integrations
- [ ] Additional protocols (GraphQL, gRPC)
- [ ] Marketplace features

#### Phase 21: Advanced Execution
- [ ] Async/streaming tool execution
- [ ] Long-running tool support
- [ ] Webhook notifications
- [ ] A/B testing for tool versions
- [ ] Cost optimization features

## Success Metrics

### Adoption Metrics
- Number of published packages
- Number of registered developers
- Total downloads
- Active weekly users (agents + developers)
- GitHub stars / community engagement

### Quality Metrics
- Average package quality score
- Percentage of packages with documentation
- Percentage of packages with tests
- Average time to find relevant tool (search quality)

### Technical Metrics
- Package installation success rate
- Dependency resolution success rate
- API uptime and latency
- CDN cache hit rate

### Ecosystem Health
- Number of packages updated in last 6 months
- Diversity of tool categories
- MCP compatibility coverage
- Integration with major agent frameworks

## Open Questions

### Technical (V1)
1. **Index update frequency**: Daily auto-update or manual? Delta or full?
2. **Index compression**: gzip, brotli, or both?
3. **Local search**: SQLite FTS5 or custom indexing?
4. **MCP process management**: Keep-alive duration? Memory limits?
5. **Authentication storage**: OS keyring, encrypted file, or config?
6. **Rate limiting**: Client-side or server-side for API tools?

### Technical (V2)
7. **Sandbox lifecycle**: Keep-alive duration? Max concurrent sandboxes?
8. **Docker alternatives**: Support Podman, containerd?
9. **Cloud sandboxes**: Serverless (Lambda) or container-based (ECS)?
10. **Sandbox caching**: Keep images locally? Update strategy?

### Infrastructure
11. **Hosting**: Self-hosted, AWS, Cloudflare, or hybrid?
12. **Database**: PostgreSQL (relational) or focus on index generation?
13. **CDN**: Cloudflare, AWS CloudFront, or GitHub Pages for index?
14. **Storage**: S3 for index only? Docker images on Docker Hub?
15. **Costs**: Can we keep V1 MVP costs under $50/month?

### Business/Community
16. **Funding**: Donations (GitHub Sponsors), grants, or freemium?
17. **Moderation**: Manual review for all tools or automated + flagging?
18. **Verification**: Paid verification or community-based?
19. **Naming**: Enforce @username/toolname or allow flat namespace?
20. **License**: MIT or Apache 2.0 for ToolStore itself?

### Integration & Ecosystem
21. **MCP servers**: Should we maintain a list of existing MCP servers to package?
22. **API standards**: Support only OpenAPI or also GraphQL, gRPC?
23. **Auth providers**: Support OAuth flows? Which providers?
24. **Federation**: Allow private ToolStore instances that sync with public?
25. **Agent frameworks**: Priority integrations (LangChain, AutoGPT, CrewAI)?

### User Experience
26. **Configuration**: Single config file or multiple? JSON or YAML?
27. **API keys**: Per-tool or global credential manager?
28. **Updates**: Auto-update client or manual? Version pinning?
29. **Telemetry**: Collect anonymous usage stats? Opt-in or opt-out?
30. **Documentation**: Separate docs site or inline CLI help?

---

## Architecture Summary

**V1 (MVP) - API-Only Tools:**
```
Agent
  ↓
ToolStore Client (Local)
  ├── Index (downloaded, ~5-10 MB)
  │   ├── API tool definitions (80%)
  │   └── MCP server definitions (20%)
  ├── Personal Registry (user's tools)
  └── Execution Engine
      ├── HTTP client (for API tools)
      └── MCP client (for MCP servers)
  ↓
External APIs / MCP Servers
```

**V2 - Sandboxed Tools:**
```
Agent
  ↓
ToolStore Client
  ↓
Sandbox Manager
  ↓
Docker Containers (auto-managed)
```

---

## Key Innovations

1. **Index-Based Discovery**: Full tool definitions in local index
2. **No Installation**: API tools work immediately
3. **MCP Integration**: Native support for MCP servers
4. **Personal Registry**: Mix public + private tools seamlessly
5. **Agent-First**: Designed for autonomous agent use
6. **V2 Sandboxes**: Human-free tool installation (future)

---

**Status**: Planning Phase Complete → Ready for Implementation  
**Last Updated**: November 24, 2025  
**Next Steps**: 
1. Choose tech stack (recommend: Python + FastAPI + PostgreSQL)
2. Create detailed specifications (tool format, API endpoints, index structure)
3. Set up repository structure
4. Begin Phase 1: Foundation & Specifications

