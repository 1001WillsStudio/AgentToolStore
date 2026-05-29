"""frontend-design-toolkit - Create production-grade frontend interfaces — web pages, dashboards, landing pages, UI components with HTML/CSS/JS. Use when the user asks to build a UI, create a webpage, design a dashboard, make a landing page, or build any frontend interface.
==========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for frontend-design.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "frontend-design-toolkit",
        "guidance": "See doc.md for full frontend-design guidance.",
        "topic": topic if topic else None,
    }
