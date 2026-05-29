"""theme-factory-toolkit - Apply and manage visual themes for web artifacts and UI components — color schemes, typography pairs, and design tokens. Use when the user wants to change themes, apply a visual style, or needs theme options for their web project.
========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for theme-factory.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "theme-factory-toolkit",
        "guidance": "See doc.md for full theme-factory guidance.",
        "topic": topic if topic else None,
    }
