"""webapp-testing-toolkit - Test local web applications using browser automation (Playwright) — verify functionality, debug UI behavior, capture screenshots, and view browser logs. Use when the user wants to test a web app, verify frontend behavior, debug UI issues, or automate browser interactions.
=========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for webapp-testing.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "webapp-testing-toolkit",
        "guidance": "See doc.md for full webapp-testing guidance.",
        "topic": topic if topic else None,
    }
