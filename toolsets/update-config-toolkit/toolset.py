"""update-config-toolkit - View, modify, and manage configuration settings. Use when the user wants to change settings, update preferences, toggle features, or view current configuration values.
========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for update-config.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "update-config-toolkit",
        "guidance": "See doc.md for full update-config guidance.",
        "topic": topic if topic else None,
    }
