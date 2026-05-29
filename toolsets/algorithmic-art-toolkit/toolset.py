"""algorithmic-art-toolkit - Create generative and algorithmic art using code — p5.js, canvas, SVG, or other creative coding frameworks. Use when users ask for generative art, creative coding, algorithmic designs, flow fields, particle systems, or code-based visual art.
==========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for algorithmic-art.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "algorithmic-art-toolkit",
        "guidance": "See doc.md for full algorithmic-art guidance.",
        "topic": topic if topic else None,
    }
