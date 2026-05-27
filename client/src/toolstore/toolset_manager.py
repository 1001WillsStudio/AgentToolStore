"""
ToolsetManager — discovers toolsets on disk, parses them, and feeds the index.

A *toolset* is a directory containing exactly two meaningful files::

    my-toolset/
    ├── doc.md        # agent-facing documentation (plain Markdown)
    └── toolset.py    # Python code with @tool-decorated entry points

The directory name is the tool name.  ``doc.md`` becomes the tool
description.  ``toolset.py`` is parsed with the ``ast`` module so we can
extract ``@tool`` function signatures without importing or executing
anything.

Unlike skills, toolsets are **agent-centric**: the agent calls
``tool_store(action="execute", tool_name="...")`` and it just runs.  There
is no progressive-disclosure dance.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Optional, Any


class ToolsetDefinition:
    """Parsed representation of one toolset on disk."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.name = self.directory.name
        self.doc: str = ""
        self.functions: Dict[str, Dict[str, Any]] = {}  # name -> {desc, params}
        self._valid = False
        self._errors: List[str] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Read *doc.md* and parse *toolset.py*.

        Returns ``True`` if the toolset is valid (has at least one
        ``@tool``-decorated function).
        """
        self._errors.clear()

        # -- doc.md ---------------------------------------------------
        doc_path = self.directory / "doc.md"
        if doc_path.exists():
            try:
                self.doc = doc_path.read_text(encoding="utf-8").strip()
            except Exception as exc:
                self._errors.append(f"Failed to read doc.md: {exc}")
        # doc.md is optional — fine if missing

        # -- toolset.py -----------------------------------------------
        code_path = self.directory / "toolset.py"
        if not code_path.exists():
            self._errors.append("Missing toolset.py")
            return False

        try:
            source = code_path.read_text(encoding="utf-8")
        except Exception as exc:
            self._errors.append(f"Failed to read toolset.py: {exc}")
            return False

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            self._errors.append(f"Syntax error in toolset.py: {exc}")
            return False

        self.functions = self._extract_tool_functions(tree)
        if not self.functions:
            self._errors.append(
                "No @tool-decorated functions found in toolset.py"
            )
            return False

        self._valid = True
        return True

    # ------------------------------------------------------------------
    # AST extraction
    # ------------------------------------------------------------------

    def _extract_tool_functions(
        self, tree: ast.Module,
    ) -> Dict[str, Dict[str, Any]]:
        """Walk the AST and find every top-level function decorated with
        ``@tool``, extracting name, docstring, and parameter info."""
        result: Dict[str, Dict[str, Any]] = {}

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            # Check if any decorator is ``tool`` (bare) or ``toolstore.tool``
            if not self._has_tool_decorator(node):
                continue

            name = node.name
            desc = ast.get_docstring(node) or ""
            params = self._extract_params(node)

            result[name] = {
                "description": desc,
                "parameters": params,
            }

        return result

    @staticmethod
    def _has_tool_decorator(func_node: ast.FunctionDef) -> bool:
        for dec in func_node.decorator_list:
            # @tool
            if isinstance(dec, ast.Name) and dec.id == "tool":
                return True
            # @toolstore.tool  (qualified)
            if (
                isinstance(dec, ast.Attribute)
                and dec.attr == "tool"
                and isinstance(dec.value, ast.Name)
                and dec.value.id == "toolstore"
            ):
                return True
        return False

    @staticmethod
    def _extract_params(
        func_node: ast.FunctionDef,
    ) -> Dict[str, Dict[str, Any]]:
        """Extract parameter names, types, defaults, and required flags
        from a function signature using only the AST."""
        params: Dict[str, Dict[str, Any]] = {}
        args = func_node.args

        # Regular args (excluding *args, **kwargs)
        all_arg_names = [a.arg for a in args.args]
        all_annotations: Dict[str, Optional[str]] = {}

        for i, arg in enumerate(args.args):
            ann = None
            if arg.annotation:
                ann = ast.unparse(arg.annotation)
            all_annotations[arg.arg] = ann

        # Defaults are aligned to the *last* N positional args
        defaults: List[Any] = [None] * (
            len(all_arg_names) - len(args.defaults)
        )
        for d in args.defaults:
            try:
                # ast.literal_eval works for strings / numbers / None / booleans
                defaults.append(ast.literal_eval(d))
            except (ValueError, TypeError):
                defaults.append(ast.unparse(d))

        for i, arg_name in enumerate(all_arg_names):
            ann = all_annotations.get(arg_name)
            has_default = defaults[i] is not None  # None could be a real default

            param_type = "string"
            if ann:
                ann_lower = ann.lower()
                if ann_lower in ("int", "integer"):
                    param_type = "integer"
                elif ann_lower in ("float", "number"):
                    param_type = "number"
                elif ann_lower in ("bool", "boolean"):
                    param_type = "boolean"
                elif ann_lower in ("list", "dict", "any"):
                    param_type = "object"

            entry: Dict[str, Any] = {
                "type": param_type,
                "required": defaults[i] is None,  # no default → required
            }
            if defaults[i] is not None:
                entry["default"] = defaults[i]

            params[arg_name] = entry

        return params

    # ------------------------------------------------------------------
    # Tool definition for the index
    # ------------------------------------------------------------------

    def to_tool_definition(self) -> Dict[str, Any]:
        """Produce the standard ToolStore tool-definition dict consumed
        by the index manager and schema converter."""
        if not self._valid:
            raise RuntimeError(
                f"Toolset '{self.name}' is not valid: {'; '.join(self._errors)}"
            )

        # Build a flat input schema that exposes all function parameters.
        # The "function" field selects which @tool function to call.
        fn_names = list(self.functions.keys())
        properties: Dict[str, Any] = {
            "function": {
                "type": "string",
                "enum": fn_names,
                "description": "Which function to call in this toolset",
            }
        }

        # Merge parameters from all functions into the flat schema.
        # If two functions have the same parameter name with different
        # types, the last one wins (occurs rarely in practice).
        for fn_name, fn_info in self.functions.items():
            for pname, pinfo in fn_info.get("parameters", {}).items():
                if pname not in properties:
                    properties[pname] = {
                        "type": pinfo.get("type", "string"),
                        "description": f"({fn_name}) {pinfo.get('description', '')}",
                    }
                # Don't overwrite if already set by another function

        # Only "function" is required — per-function params are validated
        # at call time by Python's own signature checking.
        required: List[str] = ["function"]

        return {
            "name": self.name,
            "type": "toolset",
            "description": self.doc.split("\n")[0] if self.doc else self.name,
            "source": "toolset",
            "toolset_dir": str(self.directory),
            "doc": self.doc,
            "bindings": self.functions,
            "schema": {
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            },
        }

    @property
    def is_valid(self) -> bool:
        return self._valid

    @property
    def errors(self) -> List[str]:
        return list(self._errors)


# ---------------------------------------------------------------------------
# ToolsetManager — scans directories, maintains loaded definitions
# ---------------------------------------------------------------------------


class ToolsetManager:
    """Scans configured directories and maintains an in-memory registry of
    all discovered toolsets."""

    def __init__(self, directories: List[str] | None = None) -> None:
        self._directories: List[Path] = [Path(d) for d in (directories or [])]
        self._toolsets: Dict[str, ToolsetDefinition] = {}

    # -- directories -------------------------------------------------------

    @property
    def directories(self) -> List[Path]:
        return list(self._directories)

    def set_directories(self, paths: List[str]) -> None:
        self._directories = [Path(p) for p in paths]

    def add_directory(self, path: str) -> None:
        p = Path(path)
        if p not in self._directories:
            self._directories.append(p)

    def remove_directory(self, path: str) -> None:
        p = Path(path)
        if p in self._directories:
            self._directories.remove(p)

    # -- scanning ----------------------------------------------------------

    def scan(self) -> int:
        """Walk all configured directories looking for toolset directories.

        A directory is a *toolset* if it contains a ``toolset.py`` file.

        Returns the number of newly discovered (or updated) toolsets.
        """
        count = 0

        for base_dir in self._directories:
            if not base_dir.is_dir():
                continue

            for entry in base_dir.iterdir():
                if not entry.is_dir():
                    continue
                code_path = entry / "toolset.py"
                if not code_path.exists():
                    continue

                # Already loaded? Skip unless the file is newer
                existing = self._toolsets.get(entry.name)
                if existing is not None:
                    # Quick check: has toolset.py been modified?
                    try:
                        mtime = code_path.stat().st_mtime
                    except OSError:
                        continue
                    # We can't easily track mtimes of loaded definitions,
                    # so just reload unconditionally for now.
                    pass

                td = ToolsetDefinition(entry)
                if td.load():
                    self._toolsets[entry.name] = td
                    count += 1

        return count

    # -- lookup ------------------------------------------------------------

    def get(self, name: str) -> Optional[ToolsetDefinition]:
        return self._toolsets.get(name)

    def get_all(self) -> List[ToolsetDefinition]:
        return list(self._toolsets.values())

    def get_all_tool_definitions(self) -> List[Dict[str, Any]]:
        defs: List[Dict[str, Any]] = []
        for td in self._toolsets.values():
            if td.is_valid:
                defs.append(td.to_tool_definition())
        return defs

    # -- reload a single toolset -------------------------------------------

    def reload(self, name: str) -> bool:
        """Force-reload a single toolset from disk.  Returns ``True`` if
        the toolset was found and successfully reloaded."""
        for base_dir in self._directories:
            candidate = base_dir / name
            if candidate.is_dir() and (candidate / "toolset.py").exists():
                td = ToolsetDefinition(candidate)
                ok = td.load()
                if ok:
                    self._toolsets[name] = td
                return ok
        return False


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_toolset_manager: Optional[ToolsetManager] = None


def get_toolset_manager(
    directories: List[str] | None = None,
) -> ToolsetManager:
    """Return (or lazily create) the singleton ToolsetManager."""
    global _toolset_manager
    if _toolset_manager is None:
        _toolset_manager = ToolsetManager(directories or [])
    elif directories:
        _toolset_manager.set_directories(directories)
    return _toolset_manager
