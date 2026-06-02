"""ToolStore Web UI — local management SPA server.

Part of the ``toolstore`` package. The core ``toolstore`` module does
*not* import from here; this subpackage depends on the core, never the
other way around.

Start it::

    python -m toolstore.webui.server --port 8765
"""

from .server import ManagementServer

__all__ = ["ManagementServer"]
