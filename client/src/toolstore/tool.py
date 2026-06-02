"""
Tool class hierarchy — ABC with polymorphic dispatch.

Replaces the scattered ``if tool_type == "toolset" / "mcp_toolset" / …``
branches with a unified ``Tool`` abstract base class and three concrete
subclasses.  Every tool can produce its own OpenAI schema, prompt line,
and execute itself.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from toolstore.index_manager import IndexManager
from toolstore.mcp_client import get_client
from toolstore.schema_converter import toolstore_to_openai, flatten_mcp_content
from toolstore.skill_manager import get_skill_manager

if TYPE_CHECKING:
    from toolstore.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# _read_doc — reusable helper
# ---------------------------------------------------------------------------

def _read_doc(doc_path: Path) -> str:
    """Read the full body of a toolset's ``doc.md``.

    Skips the ``# Title`` line, then returns everything until the first
    ``---`` or ``##``, preserving line breaks.  Blank lines inside the
    body are kept.  Returns an empty string if the file doesn't exist.
    """
    if not doc_path.exists():
        return ""

    try:
        text = doc_path.read_text(encoding="utf-8")
    except Exception:
        return ""

    lines = text.split("\n")
    out: List[str] = []
    started = False

    for line in lines:
        stripped = line.strip()

        # Skip the title line
        if not started and stripped.startswith("#"):
            started = True
            continue

        # Stop at section headers or horizontal rules
        if stripped.startswith("##") or stripped == "---":
            break

        if started:
            out.append(stripped)

    # Trim trailing blank lines
    while out and not out[-1]:
        out.pop()

    return "\n".join(out)


def _build_signature(name: str, params: Dict[str, Any]) -> str:
    """Format a function signature like ``get_weather(location: str, units: str = "metric")``."""
    parts: List[str] = []
    for pn, pi in params.items():
        pt = pi.get("type", "string")
        if pi.get("required"):
            parts.append(f"{pn}: {pt}")
        else:
            default = pi.get("default", "None")
            parts.append(f"{pn}: {pt} = {default!r}")
    return f"{name}({', '.join(parts)})"


# ---------------------------------------------------------------------------
# Tool ABC
# ---------------------------------------------------------------------------

class Tool(ABC):
    """Abstract base for all tool types in the ToolStore ecosystem.

    Subclasses
    ----------
    * :class:`ToolsetTool` — directory‑based toolset with ``@tool`` bindings
    * :class:`MCPTool` — external MCP server tool
    * :class:`SkillTool` — SKILL.md‑based agent skill
    """

    def __init__(self, name: str):
        self.name = name
        self._raw: Dict[str, Any] = {}  # original dict for format_display

    # ── abstract interface ───────────────────────────────────────────

    @abstractmethod
    def to_openai_schema(self) -> dict:
        """Return an OpenAI function‑calling schema dict."""
        ...

    @abstractmethod
    def to_prompt_line(self) -> str:
        """Return a single‑line description for the system prompt."""
        ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return its result as a string."""
        ...

    @abstractmethod
    def format_display(self) -> str:
        """Return a formatted display block for the context manager.

        Used by AuroraCoder's toolset context tracker to show
        per‑tool details in the ``<====TOOLSTORE_START====>`` block.
        """
        ...

    # ── optional override ─────────────────────────────────────────────

    def toolset_doc(self) -> str:
        """Return the full doc.md body for toolset‑grouped tools.

        Only meaningful for :class:`ToolsetTool`.  Other subclasses
        return an empty string.
        """
        return ""

    # ── factory ───────────────────────────────────────────────────────

    @staticmethod
    def from_dict(
        d: Dict[str, Any],
        *,
        config_manager: ConfigManager | None = None,
        index_manager: IndexManager | None = None,
    ) -> Tool:
        """Build the right subclass from a raw tool dict."""
        tool_type = d.get("type", "unknown")

        if tool_type == "toolset":
            inst = ToolsetTool.from_dict(d)
        elif tool_type in ("mcp", "mcp_toolset"):
            inst = MCPTool.from_dict(d)
        elif tool_type == "skill":
            inst = SkillTool.from_dict(d)
        else:
            raise ValueError(f"Unknown tool type: {tool_type!r}")

        inst._raw = d
        return inst


# ---------------------------------------------------------------------------
# ToolsetTool
# ---------------------------------------------------------------------------

class ToolsetTool(Tool):
    """A directory‑based toolset with a ``toolset.py`` and ``@tool`` bindings.

    This is the primary execution path — the toolset code is loaded inline
    without starting a subprocess.
    """

    def __init__(
        self,
        name: str,
        directory: str = "",
        bindings: Dict[str, Any] | None = None,
        code: str = "",
        code_base64: str = "",
        requirements: List[str] | None = None,
        description: str = "",
    ):
        super().__init__(name)
        self.directory = directory
        self.bindings = bindings or {}
        self.code = code
        self.code_base64 = code_base64
        self.requirements = requirements or []
        self.description = description

    # ── factory ───────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ToolsetTool:
        return cls(
            name=d.get("name", ""),
            directory=d.get("directory", d.get("toolset_dir", "")),
            bindings=d.get("bindings", {}),
            code=d.get("code", ""),
            code_base64=d.get("code_base64", ""),
            requirements=d.get("requirements", []),
            description=d.get("description", d.get("doc", "")),
        )

    # ── doc ────────────────────────────────────────────────────────

    def toolset_doc(self) -> str:
        """Return the full doc.md body (minus the title line)."""
        if not self.directory:
            return ""
        doc_path = Path(self.directory) / "doc.md"
        return _read_doc(doc_path)

    # ── OpenAI schema ─────────────────────────────────────────────

    def to_openai_schema(self) -> dict:
        """Return an OpenAI schema for the *first* binding.

        For the full set of function schemas from a toolset (one per
        binding), use :func:`_load_primary_toolset_schemas` instead.
        """

        return toolstore_to_openai({
            "name": self.name,
            "type": "toolset",
            "description": self.toolset_doc() or self.name,
            "bindings": self.bindings,
        })

    # ── prompt line ───────────────────────────────────────────────

    def to_prompt_line(self) -> str:
        """Return ``### name\n\ndoc.md body\n- binding\n- binding`` block."""
        doc = self.toolset_doc()
        header = f"### {self.name}"
        fn_lines = [f"- {fn}" for fn in sorted(self.bindings.keys())]

        parts = [header]
        if doc:
            parts.append(doc)
        parts.extend(fn_lines)
        return "\n".join(parts)

    # ── execute ───────────────────────────────────────────────────

    def execute(self, **kwargs: Any) -> str:
        """Execute a ``@tool`` function from this toolset inline.

        Self‑contained — no circular import into :mod:`native_tool`.
        """

        kwargs = dict(kwargs)
        function_name = kwargs.pop("function", None)

        # ── resolve the function name ──────────────────────────
        if not function_name:
            if len(self.bindings) == 1:
                function_name = next(iter(self.bindings))
            else:
                names = list(self.bindings.keys()) if self.bindings else []
                return (
                    "Error: 'function' argument required. "
                    f"Available functions: {', '.join(names) or '(none)'}"
                )

        if function_name not in self.bindings:
            names = list(self.bindings.keys())
            return (
                f"Error: Unknown function '{function_name}'. "
                f"Available: {', '.join(names)}"
            )

        # ── validate / decode code ─────────────────────────────
        code = self.code
        if self.code_base64 and not code:
            try:
                code = base64.b64decode(self.code_base64).decode("utf-8")
            except Exception as exc:
                return f"Error decoding code_base64: {exc}"

        if not code and self.directory:
            ts_file = Path(self.directory) / "toolset.py"
            if ts_file.exists():
                code = ts_file.read_text(encoding="utf-8")

        if not code:
            return "Error: toolset has no code to execute"

        # ── pip‑install guard ──────────────────────────────────
        if self.requirements:
            reqs = (
                self.requirements.split("\n")
                if isinstance(self.requirements, str)
                else self.requirements
            )
            return (
                "Error: This toolset requires packages that aren't installed: "
                f"{', '.join(reqs)}.\n"
                f"Install them first: pip install {' '.join(reqs)}"
            )

        # ── load & call ────────────────────────────────────────
        with tempfile.TemporaryDirectory(prefix="toolset_") as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "toolset.py").write_text(code, encoding="utf-8")
            mod_name = f"_toolset_{function_name}"
            spec = importlib.util.spec_from_file_location(mod_name, tmp / "toolset.py")
            if spec is None or spec.loader is None:
                return "Error: failed to create module spec for toolset.py"
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            fn = getattr(mod, function_name, None)
            if fn is None:
                return f"Error: Function '{function_name}' not found in toolset code"
            try:
                result = fn(**kwargs)
                return json.dumps(result, default=str, indent=2)
            except Exception as exc:
                return f"Error executing '{function_name}': {exc}"

    # ── format_display ────────────────────────────────────────────

    def format_display(self) -> str:
        """Return a formatted display: doc summary + binding signatures."""
        lines: List[str] = []
        doc = self.description or self.toolset_doc()
        if doc.strip():
            lines.append(doc.strip())

        if self.bindings:
            if lines:
                lines.append("")
            lines.append("Bindings:")
            for fn_name, info in sorted(self.bindings.items()):
                params = info.get("parameters", {})
                sig = _build_signature(fn_name, params)
                desc = info.get("description", "")
                suffix = f" — {desc}" if desc else ""
                lines.append(f"  {sig}{suffix}")

        return "\n".join(lines) if lines else self.name


# ---------------------------------------------------------------------------
# MCPTool
# ---------------------------------------------------------------------------

class MCPTool(Tool):
    """An external MCP‑server tool reached via the MCP client."""

    def __init__(
        self,
        name: str,
        server_id: str = "",
        description: str = "",
    ):
        super().__init__(name)
        self.server_id = server_id
        self.description = description

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> MCPTool:
        server = d.get("mcp_server", d.get("source", ""))
        if isinstance(server, str) and server.startswith("mcp:"):
            server = server[4:]
        return cls(
            name=d.get("name", ""),
            server_id=server,
            description=d.get("description", ""),
        )

    def to_openai_schema(self) -> dict:
        return toolstore_to_openai({
            "name": self.name,
            "type": "mcp",
            "description": self.description,
            "mcp_server": self.server_id,
        })

    def to_prompt_line(self) -> str:
        return f"- {self.name}"

    def execute(self, **kwargs: Any) -> str:
        """Execute an MCP tool via the connection pool.

        Self‑contained — reads server config from IndexManager.
        """

        function_name = kwargs.pop("function", self.name)

        im = IndexManager()
        im._load_local()
        servers = im._local_mcp
        config = servers.get(self.server_id)
        if not config:
            return f"Error: MCP server '{self.server_id}' not found in config."

        try:
            client = get_client(self.server_id, config)
            result = client.call_tool(function_name, kwargs)
            content = result.get("content", [])
            if result.get("isError"):
                return "[TOOL ERROR] " + flatten_mcp_content(content)
            return flatten_mcp_content(content)
        except Exception as exc:
            return f"Error executing MCP tool: {str(exc)}"

    # ── format_display ────────────────────────────────────────────

    def format_display(self) -> str:
        """MCP tool display: server name + transport."""
        transport = self._raw.get("transport", "stdio")
        return f"MCP server — connected via {transport}\n\n{self.name}" + (
            f" — {self.description}" if self.description else ""
        )


# ---------------------------------------------------------------------------
# SkillTool
# ---------------------------------------------------------------------------

class SkillTool(Tool):
    """A SKILL.md‑based agent skill."""

    def __init__(
        self,
        name: str,
        skill_dir: str = "",
        description: str = "",
    ):
        super().__init__(name)
        self.skill_dir = skill_dir
        self.description = description

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> SkillTool:
        return cls(
            name=d.get("name", ""),
            skill_dir=d.get("directory", d.get("skill_dir", "")),
            description=d.get("description", ""),
        )

    def to_openai_schema(self) -> dict:
        return toolstore_to_openai({
            "name": self.name,
            "type": "skill",
            "description": self.description,
            "skill_dir": self.skill_dir,
        })

    def to_prompt_line(self) -> str:
        return f"- {self.name}"

    def execute(self, **kwargs: Any) -> str:
        """Execute a skill: load body, list/read files, or run a script.

        Self‑contained — no circular import into :mod:`exec_tools`.
        """
        from toolstore.native_tool import config_manager

        skill_name = self.name
        if skill_name.startswith("skill:"):
            skill_name = skill_name[len("skill:"):]
        skill_action = kwargs.get("action", "load")

        sm = get_skill_manager(config_manager.get_skill_dirs())
        if not sm.get_skill(skill_name):
            sm.scan()

        if skill_action == "load":
            body = sm.get_skill_body(skill_name)
            if body is None:
                return f"Error: Skill '{skill_name}' not loaded."
            return body

        elif skill_action == "files":
            sd = sm.get_skill(skill_name)
            if not sd:
                return f"Error: Skill '{skill_name}' not found."
            flist = [str(f) for f in sd.list_files()]
            return "\n".join(flist) if flist else "(no additional files bundled)"

        elif skill_action == "file":
            file_path = kwargs.get("file_path", "")
            if not file_path:
                return "Error: 'file_path' is required for action='file'."
            content = sm.get_skill_file(skill_name, file_path)
            if content is None:
                return f"Error: File '{file_path}' not found in skill '{skill_name}'."
            return content

        elif skill_action == "run":
            script = kwargs.get("script", "")
            if not script:
                return "Error: 'script' argument is required for action='run'."
            return sm.run_skill_script(skill_name, script)

        else:
            return f"Error: Unknown skill action '{skill_action}'. Use 'load', 'files', or 'file'."

    # ── format_display ────────────────────────────────────────────

    def format_display(self) -> str:
        """Skill display: body / description + bundled files."""
        body = self._raw.get("body", "") or self.description
        files: list = self._raw.get("skill_files_list", [])

        lines = [body.strip()] if body and body.strip() else []
        if files:
            if lines:
                lines.append("")
            lines.append("Bundled files:")
            for fname in files:
                lines.append(f"  {fname}")

        return "\n".join(lines) if lines else (self.description or self.name)
