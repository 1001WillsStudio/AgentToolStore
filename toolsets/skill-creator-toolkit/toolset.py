"""skill-creator-toolkit - Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit or optimize an existing skill, run evals to test a skill, benchmark skill performance, or optimize a skill's description for better triggering accuracy.
========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for skill-creator.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "skill-creator-toolkit",
        "guidance": "See doc.md for full skill-creator guidance.",
        "topic": topic if topic else None,
    }
