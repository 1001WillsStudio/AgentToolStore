"""canvas-design-toolkit - Create beautiful visual art in .png and .pdf formats using design philosophy — posters, artwork, covers, static designs. Use when the user asks to create a poster, design, artwork, cover image, or any static visual design output.
========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for canvas-design.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "canvas-design-toolkit",
        "guidance": "See doc.md for full canvas-design guidance.",
        "topic": topic if topic else None,
    }
