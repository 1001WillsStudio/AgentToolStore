# Changelog

All notable changes to the ToolStore client will be documented in this file.

## [0.2.0] — 2026-05-30

### Added
- **MCP Client**: Full MCP client supporting stdio, SSE, and streamable-HTTP transports
- **MCP Server**: Expose ToolStore as an MCP server (`toolstore serve`)
- **Agent Skills**: Full Agent Skills integration (discover, install, publish, validate)
- **Toolset Manager**: AST-based discovery, local execution, and registry publishing
- **Management UI**: Web dashboard for Tools, MCP Servers, Skills, and Toolsets
- **Secondary Tools**: Compact name-only tool listing for agent system prompts
- **Docker Pool**: Container-based tool execution with approval-mode permissions
- **CLI**: Complete CLI with `update`, `search`, `use`, `info`, `login`, `publish`, `delete`, `export`, `serve`, `skill`, `toolset`, `mcp-server`, `docker` commands
- **`@tool` decorator**: Auto-generate OpenAI function-calling schemas from type hints
- **Local execution**: Run toolsets directly from local directories (no registry required)
- **Config manager**: Persistent settings with env-var override support
- **Index manager**: Local registry index caching with update-from-remote

### Changed
- Complete rewrite from v1.x; see [client/README.md](README.md) for full API documentation

### Fixed
- N/A (first stable v2 release)
