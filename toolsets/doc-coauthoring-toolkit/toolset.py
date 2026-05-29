"""doc-coauthoring-toolkit - Co-author structured documents collaboratively — proposals, design docs, decision memos, technical specifications, and similar structured content. Use when the user wants to write a document together, needs a structured draft, or mentions writing proposals, specs, or formal documents.
==========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for doc-coauthoring.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "doc-coauthoring-toolkit",
        "guidance": "See doc.md for full doc-coauthoring guidance.",
        "topic": topic if topic else None,
    }
