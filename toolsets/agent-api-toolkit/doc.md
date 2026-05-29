# agent-api

---
name: agent-api
description: Build applications powered by AI agent APIs — including prompt design, tool use, streaming, structured output, and best practices for production deployment. Use when the user wants to build an app with an AI agent API, integrate AI capabilities, or design prompts and tools for agent-based applications.
---

# Agent API Integration

Build applications powered by AI agent APIs.

## Overview

This skill covers building applications that use AI agent APIs — from simple prompts to complex agentic workflows with tool use, structured output, and streaming.

## Core Concepts

### Prompt Design

1. **Be specific**: Clearly state what you want and how you want it
2. **Provide context**: Give the agent relevant background
3. **Define output format**: Specify structure when consistency matters
4. **Use examples**: Few-shot prompting for consistent behavior
5. **Set constraints**: Boundaries and rules for the response

```python
# Good prompt structure
system_prompt = """You are a code reviewer. When reviewing code:

1. First, identify the primary purpose of the code
2. Check for correctness (bugs, logic errors)
3. Check for style (naming, formatting, clarity)
4. Suggest improvements with specific examples
5. Rate the code on a scale of 1-10

Be constructive and specific. Explain WHY each suggestion matters."""

user_message = f"Please review this code:\n\n{code}"
```

### Tool Use

Design tools that agents can call:

```python
tools = [
    {
        "name": "search_database",
        "description": "Search the customer database by name, email, or ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "field": {
                    "type": "string",
                    "enum": ["name", "email", "id"],
                    "description": "Which field to search"
                }
            },
            "required": ["query"]
        }
    }
]
```

Key tool design principles:
- **Clear descriptions**: The agent reads these to decide when to call each tool
- **Explicit parameters**: Every parameter should have a description
- **Narrow scope**: Each tool does one thing well
- **Error handling**: Return clear error messages the agent can act on

### Streaming

Stream responses for real-time user feedback:

```python
# Streaming pattern
async for event in agent.stream(messages, tools=tools):
    if event.type == "content_block_delta":
        yield event.delta.text
    elif event.type == "tool_use":
        # Execute tool and provide result
        result = execute_tool(event.tool_name, event.input)
        yield format_tool_result(result)
```

### Structured Output

Request structured JSON output when you need machine-parseable responses:

```python
response = agent.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Extract entities from this text..."}],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "entity_extraction",
            "schema": {
                "type": "object",
                "properties": {
                    "people": {"type": "array", "items": {"type": "string"}},
                    "organizations": {"type": "array", "items": {"type": "string"}},
                    "dates": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["people", "organizations", "dates"]
            }
        }
    }
)
```

## Application Patterns

### Simple Bot
- User input → System prompt + User message → Response
- Add conversation history for multi-turn interactions

### RAG (Retrieval-Augmented Generation)
- User query → Search knowledge base → Augment prompt with results → Response
- Good for: documentation Q&A, knowledge bases, company wikis

### Agentic Workflow
- User request → Plan → Execute tools → Evaluate → Repeat → Final response
- Good for: complex multi-step tasks, research, data analysis

### Multi-Agent
- Orchestrator agent → Dispatches to specialized sub-agents → Aggregates results
- Good for: complex projects with distinct phases, parallel subtasks

## Best Practices

### Prompt Engineering
- **Role assignment**: "You are an expert X..."
- **Few-shot examples**: Show 2-3 examples of desired behavior
- **Chain of thought**: "Think step by step..."
- **Output formatting**: "Return your answer as JSON with the following structure..."

### Error Handling
- Handle API errors gracefully (retries, fallbacks)
- Validate agent outputs before using them
- Set timeouts for long-running agent tasks

### Production Concerns
- **Rate limiting**: Implement backoff and queuing
- **Cost tracking**: Monitor token usage per request
- **Caching**: Cache common responses where appropriate
- **Logging**: Log prompts, responses, and tool calls for debugging
- **Safety**: Validate outputs before displaying to users

## Guidelines

- **Start simple**: Get a basic prompt working before adding tools and complexity
- **Iterate on prompts**: Prompt design is iterative — test and refine
- **Design tools for the agent**: Tools should be easy for an agent to understand and use
- **Handle errors gracefully**: The agent will make mistakes; build resilient systems
- **Monitor and observe**: Track what the agent does so you can improve it
