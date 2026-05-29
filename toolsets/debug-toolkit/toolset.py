"""debug-toolkit - Systematic debugging and troubleshooting for code issues, test failures, build errors, runtime exceptions, and unexpected behavior. Use when diagnosing bugs, investigating test failures, analyzing error logs, fixing build breaks, or troubleshooting any malfunction.
================="""

from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def get_guidance(*, topic: str = "") -> dict:
    """Return best practices for debug.

    Args:
        topic: Optional sub-topic.
    Returns:
        dict with guidelines.
    """
    return {
        "toolset": "debug-toolkit",
        "guidance": "See doc.md for full debug guidance.",
        "topic": topic if topic else None,
    }
