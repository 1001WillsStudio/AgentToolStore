"""slack-gif-creator-toolkit - Create animated GIFs optimized for Slack — including text animations, meme-style GIFs, loading spinners, and reaction GIFs. Use when the user asks for a GIF, animated image for Slack, or wants to create a short looping animation.
============================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for slack-gif-creator.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "slack-gif-creator-toolkit",
        "guidance": "See doc.md for full slack-gif-creator guidance.",
        "topic": topic if topic else None,
    }
