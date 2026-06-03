"""
toolset.py — the @tool decorator that toolset code files import.

Agent-centric alternative to skills.  One doc + one code file.  The agent
calls tool_store(action="execute", tool_name="...") and it just runs.

Usage inside a toolset code file::

    from toolstore.toolset import tool

    @tool
    def get_weather(*, location: str, units: str = "metric") -> dict:
        '''Get current weather for a location.

        Args:
            location: City name or ZIP code.
            units:    "metric" or "imperial".
        '''
        import httpx
        ...

Only functions decorated with @tool are callable by agents.  Everything
else in the module is private helper code.

The decorator also enables schema auto‑generation — publishing to the
ToolStore registry derives the OpenAI function‑calling JSON from
type hints and docstrings, no manual JSON needed.
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, get_type_hints

import logging
logger = logging.getLogger(__name__)

# Per‑module registry — cleared before each toolset load.
_REGISTRY: dict[str, Callable[..., Any]] = {}

# ── Python type → JSON Schema type ────────────────────────────────────

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


def _py_to_json_type(py_type: type) -> str:
    """Map a Python type to a JSON Schema type string."""
    origin = getattr(py_type, "__origin__", None)
    if origin is not None:
        # typing.List[X], typing.Optional[X], etc.
        args = getattr(py_type, "__args__", ())
        if origin is list:
            return "array"
        if origin is dict:
            return "object"
        # Optional[X] → Union[X, None] → use the non‑None arg
        if origin is type(None).__class__.__base__ or str(origin).endswith("Union"):
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return _py_to_json_type(non_none[0])
        return "string"
    return _TYPE_MAP.get(py_type, "string")


def tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: mark a function as an agent‑callable toolset entry point.

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


# ── Schema auto‑generation ─────────────────────────────────────────────

def generate_definition(fn: Callable[..., Any]) -> dict:
    """Generate an OpenAI function‑calling definition from a @tool function.

    Reads:
      • fn.__name__       → definition.name
      • fn.__doc__        → definition.description
      • fn.__annotations__ → definition.parameters.properties
      • docstring ``Args:`` section → per‑parameter descriptions
      • default values     → parameters.required (excludes those with defaults)

    Returns a dict ready for the ToolStore publish endpoint's ``definition``
    field.
    """
    hints = _safe_get_type_hints(fn)
    sig = inspect.signature(fn)

    # Docstring: first paragraph = description
    doc = inspect.getdoc(fn) or ""
    desc_parts = doc.split("\n\n")
    description = desc_parts[0].strip() if desc_parts else fn.__name__

    # Parse ``Args:`` block from docstring for per‑param descriptions
    param_descriptions = _parse_docstring_args(doc)
    if not param_descriptions:
        param_descriptions = _parse_google_args(doc)

    properties = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        if param_name.startswith("_"):
            continue

        py_type = hints.get(param_name, str)
        json_type = _py_to_json_type(py_type)

        prop: dict[str, Any] = {"type": json_type}
        description_text = param_descriptions.get(param_name, "")
        if description_text:
            prop["description"] = description_text

        # Handle Optional — mark nullable
        if _is_optional(py_type):
            prop["nullable"] = True

        properties[param_name] = prop

        # Required = no default value AND not Optional
        if param.default is inspect.Parameter.empty and not _is_optional(py_type):
            required.append(param_name)

    return {
        "name": fn.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _safe_get_type_hints(fn: Callable[..., Any]) -> dict[str, type]:
    """Get type hints, swallowing any errors from forward refs."""
    try:
        return get_type_hints(fn)
    except Exception:
        logger.debug("Suppressed exception in toolset.py", exc_info=True)
        return fn.__annotations__ or {}


def _parse_docstring_args(doc: str) -> dict[str, str]:
    """Parse Sphinx‑style ``Args:`` section from docstring.

    Matches::

        Args:
            param_name: Description text.
            param_name2: More text that may
                         span multiple lines.
    """
    result: dict[str, str] = {}
    lines = doc.split("\n")
    in_args = False
    current_param: str | None = None
    current_desc: list[str] = []

    for line in lines:
        stripped = line.strip()

        if re.match(r"^Args\s*:", stripped):
            in_args = True
            continue
        if in_args and re.match(r"^(Returns|Raises|Yields|Notes|Examples)\s*:", stripped):
            break
        if in_args and stripped == "":
            if current_param:
                result[current_param] = " ".join(current_desc).strip()
                current_param = None
                current_desc = []
            continue

        if in_args:
            # Check for "param_name:" pattern (not indented continuation)
            m = re.match(r"^(\w[\w\d_]*)\s*:\s*(.*)", stripped)
            if m:
                if current_param:
                    result[current_param] = " ".join(current_desc).strip()
                current_param = m.group(1)
                current_desc = [m.group(2).strip()] if m.group(2).strip() else []
            elif current_param and stripped:
                # Continuation of previous param description
                current_desc.append(stripped)

    if current_param:
        result[current_param] = " ".join(current_desc).strip()

    return result


def _parse_google_args(doc: str) -> dict[str, str]:
    """Fallback: parse Google‑style ``Args:`` where params are indented.::

        Args:
            param_name (type): Description.
    """
    result: dict[str, str] = {}
    pattern = re.compile(r"^\s*(\w[\w\d_]*)\s*(?:\([^)]*\))?\s*:\s*(.*)")
    lines = doc.split("\n")
    in_args = False

    for line in lines:
        if re.match(r"^\s*Args\s*:", line):
            in_args = True
            continue
        if in_args and re.match(r"^\s*(Returns|Raises|Yields)\s*:", line):
            break
        if in_args:
            m = pattern.match(line)
            if m:
                result[m.group(1)] = m.group(2).strip()

    return result


def _is_optional(py_type: type) -> bool:
    """Return True if the type is Optional[X] (Union[X, None])."""
    origin = getattr(py_type, "__origin__", None)
    if origin is None:
        return False
    # Check if it's a Union containing NoneType
    args = getattr(py_type, "__args__", ())
    if len(args) == 2 and type(None) in args:
        return True
    return False
