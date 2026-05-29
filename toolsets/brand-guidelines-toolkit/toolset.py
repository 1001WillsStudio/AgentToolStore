"""brand-guidelines-toolkit - Apply official brand colors, typography, and visual identity to any design output. Use when the user mentions brand, branding, brand colors, brand guidelines, company style, or wants designs that match specific brand identity standards.
============================"""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for brand-guidelines.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "brand-guidelines-toolkit",
        "guidance": "See doc.md for full brand-guidelines guidance.",
        "topic": topic if topic else None,
    }
