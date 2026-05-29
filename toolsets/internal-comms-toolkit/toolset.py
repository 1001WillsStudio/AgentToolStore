"""internal-comms-toolkit - Write professional internal communications — status reports, company newsletters, project updates, leadership comms, team announcements, FAQs, and talking points. Use when the user needs to write or draft internal communications for their organization.
=========================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for internal-comms.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "internal-comms-toolkit",
        "guidance": "See doc.md for full internal-comms guidance.",
        "topic": topic if topic else None,
    }
