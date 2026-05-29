"""web-artifacts-builder-toolkit - Build complex, multi-component HTML artifacts using modern frontend patterns — React, Tailwind CSS, shadcn/ui components, and interactive web apps. Use when the user wants a complex web application, interactive tool, or sophisticated single-page artifact.
================================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for web-artifacts-builder.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "web-artifacts-builder-toolkit",
        "guidance": "See doc.md for full web-artifacts-builder guidance.",
        "topic": topic if topic else None,
    }
