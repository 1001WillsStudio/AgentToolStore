"""ToolStore Web UI — local management server.

Start it::

    toolstore-webui --port 8765
    python -m toolstore_webui.server
"""

from .server import ManagementServer

__all__ = ["ManagementServer"]
