"""
toolset.py — the @tool decorator that toolset code files import.

Agent-centric alternative to skills.  One doc + one code file.  The agent
calls tool_store(action="execute", tool_name="...") and it just runs.

Usage inside a toolset code file::

    from toolstore.toolset import tool

    @tool
    def get_weather(location: str, units: str = "metric"):
        '''Get current weather for a location.'''
        import httpx
        ...

Only functions decorated with @tool are callable by agents.  Everything
else in the module is private helper code.
"""

from __future__ import annotations

from typing import Callable, Any

# Per-module registry — cleared before each toolset load so different
# toolsets don't bleed into each other.
_REGISTRY: dict[str, Callable[..., Any]] = {}


def tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: mark a function as an agent-callable toolset entry point.

    The function name becomes the binding name.  The docstring becomes the
    binding description.  The signature (type hints + defaults) defines the
    input schema that the agent sees.
    """
    _REGISTRY[fn.__name__] = fn
    fn._is_toolset_tool = True  # type: ignore[attr-defined]
    return fn


def get_tool(name: str) -> Callable[..., Any] | None:
    """Return a registered @tool function by name, or None."""
    return _REGISTRY.get(name)


def get_tool_names() -> list[str]:
    """Return the names of all registered @tool functions."""
    return list(_REGISTRY.keys())


def clear_registry() -> None:
    """Clear the registry (called between loading different toolsets)."""
    _REGISTRY.clear()
