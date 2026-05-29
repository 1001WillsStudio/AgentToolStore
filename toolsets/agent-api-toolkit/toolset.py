"""agent-api-toolkit - Build applications powered by AI agent APIs — including prompt design, tool use, streaming, structured output, and best practices for production deployment. Use when the user wants to build an app with an AI agent API, integrate AI capabilities, or design prompts and tools for agent-based applications.
====================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for agent-api.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "agent-api-toolkit",
        "guidance": "See doc.md for full agent-api guidance.",
        "topic": topic if topic else None,
    }
