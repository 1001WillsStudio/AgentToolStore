"""mcp-builder-toolkit - Guide for creating high-quality MCP (Model Context Protocol) servers that enable AI agents to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, in Python (FastMCP) or Node/TypeScript.
======================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for mcp-builder.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "mcp-builder-toolkit",
        "guidance": "See doc.md for full mcp-builder guidance.",
        "topic": topic if topic else None,
    }
