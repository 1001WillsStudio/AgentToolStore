# mcp-builder

---
name: mcp-builder
description: Guide for creating high-quality MCP (Model Context Protocol) servers that enable AI agents to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, in Python (FastMCP) or Node/TypeScript.
---

# MCP Server Builder

Create MCP (Model Context Protocol) servers that enable AI agents to interact with external services.

## Overview

MCP servers expose tools, resources, and prompts that agents use to interact with external systems. The quality of an MCP server is measured by how well it enables agents to accomplish real-world tasks.

## The Build Process

### Phase 1: Research and Planning

#### 1.1 Understand MCP Design Principles

- **API Coverage vs. Workflow Tools**: Balance comprehensive endpoint coverage with specialized workflow tools. When uncertain, prioritize comprehensive API coverage.
- **Tool Naming**: Use clear, descriptive, action-oriented names with consistent prefixes (e.g., `github_create_issue`, `github_list_repos`)
- **Context Management**: Design tools that return focused, relevant data. Support filtering and pagination.
- **Actionable Errors**: Error messages should guide agents toward solutions with specific suggestions.

#### 1.2 Study the API

Review the target service's API:
- Key endpoints and their purposes
- Authentication requirements (API keys, OAuth, etc.)
- Data models and relationships
- Rate limits and quotas
- Pagination patterns

#### 1.3 Plan Tool Coverage

List all tools to implement, starting with the most common operations. For each tool, define:
- Name, description, and purpose
- Input parameters and types
- Output format and structure
- Whether it's read-only, destructive, or idempotent

### Phase 2: Implementation

#### 2.1 Set Up Project

**Python (FastMCP recommended):**
```python
from fastmcp import FastMCP

mcp = FastMCP("service-name")

@mcp.tool
async def service_action(param1: str, param2: int = 10) -> str:
    """Clear description of what this tool does."""
    # Implementation
    return result
```

**TypeScript (MCP SDK):**
```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

const server = new McpServer({ name: "service-name" });

server.registerTool(
  "service_action",
  {
    description: "Clear description of what this tool does.",
    inputSchema: { param1: z.string(), param2: z.number().default(10) }
  },
  async ({ param1, param2 }) => {
    // Implementation
    return { content: [{ type: "text", text: result }] };
  }
);
```

#### 2.2 Implement Core Infrastructure

Create shared utilities:
- API client with authentication
- Error handling helpers
- Response formatting
- Pagination support

#### 2.3 Implement Tools

For each tool:
- **Input Schema**: Use Zod (TS) or Pydantic (Python) with constraints and examples
- **Output Schema**: Define structured output where possible
- **Description**: Concise but complete — agents use this to decide which tool to call
- **Implementation**: Async I/O, proper error handling, pagination support
- **Annotations**: Set `readOnlyHint`, `destructiveHint`, `idempotentHint` appropriately

### Phase 3: Review and Test

#### Code Quality Checklist
- [ ] No duplicated code (DRY principle)
- [ ] Consistent error handling
- [ ] Full type coverage
- [ ] Clear tool descriptions with examples
- [ ] Pagination for list endpoints
- [ ] Input validation on all parameters

#### Testing
- Build/compile without errors
- Test with MCP Inspector
- Verify each tool handles edge cases (empty results, errors, large datasets)

### Phase 4: Create Evaluations

Create 10 realistic, complex evaluation questions that require multiple tool calls to answer. Each question should be:
- **Independent**: Not dependent on other questions
- **Read-only**: Only non-destructive operations
- **Complex**: Requiring multiple tool calls and exploration
- **Verifiable**: Single, clear answer
- **Stable**: Answer won't change over time

## Transport Selection

- **Streamable HTTP**: For remote servers — simpler to scale and maintain
- **stdio**: For local servers — direct process communication

## Guidelines

- **Comprehensive coverage**: Prioritize covering the full API over convenience wrappers
- **Descriptive tool names**: Names should make the tool's purpose obvious at a glance
- **Structured output**: Use JSON/Markdown for readability
- **Error messages**: Always include actionable next steps in error responses
- **Pagination**: Support cursor or offset-based pagination for list endpoints
- **Documentation**: Include setup instructions and example usage
