"""stuck-toolkit - Help the agent and user get unstuck when progress has stalled — repeated failures, circular reasoning, unclear next steps, or confusion about what to do. Use when the agent is stuck in a loop, repeatedly failing, or the user expresses frustration about lack of progress.
================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for stuck.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "stuck-toolkit",
        "guidance": "See doc.md for full stuck guidance.",
        "topic": topic if topic else None,
    }
