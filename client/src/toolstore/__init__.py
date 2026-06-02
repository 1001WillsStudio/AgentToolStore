"""ToolStore - Universal tool manager for AI agents."""

__version__ = "2.1.6"

from .management.server import ManagementServer
from .native_tool import (
    get_secondary_tool_names,
    get_primary_tool_names,
    get_primary_tool_schemas,
    get_primary_tool_prompt,
    execute_tool_direct,
    prefetch_primary_tools,
)
from .toolset import tool, get_tool, get_tool_names, clear_registry
from .toolset_manager import ToolsetManager, ToolsetDefinition, get_toolset_manager

__all__ = [
    "ManagementServer",
    "tool",
    "get_tool",
    "get_tool_names",
    "clear_registry",
    "ToolsetManager",
    "ToolsetDefinition",
    "get_toolset_manager",
    "get_secondary_tool_names",
    "get_primary_tool_names",
    "get_primary_tool_schemas",
    "get_primary_tool_prompt",
    "execute_tool_direct",
    "prefetch_primary_tools",
    "__version__",
]
