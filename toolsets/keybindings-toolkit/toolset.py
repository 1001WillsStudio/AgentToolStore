"""keybindings-toolkit - View, customize, and manage keyboard shortcuts and keybindings. Use when the user wants to see available shortcuts, change keybindings, add custom shortcuts, or troubleshoot keyboard shortcut issues.
======================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for keybindings.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "keybindings-toolkit",
        "guidance": "See doc.md for full keybindings guidance.",
        "topic": topic if topic else None,
    }
