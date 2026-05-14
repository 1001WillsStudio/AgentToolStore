"""
Agent Skills support for ToolStore.

Implements the agentskills.io open standard:
- Parses SKILL.md files (YAML frontmatter + Markdown body)
- Validates against the spec
- Manages skill directories
- Registers skills as first-class tools (type: "skill")
- Supports progressive disclosure (metadata → instructions → resources)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Any, Optional


# ---------------------------------------------------------------------------
# YAML frontmatter parser (lightweight, no PyYAML dependency needed for
# simple key-value YAML used in SKILL.md)
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Allowed fields per the agentskills.io spec
_ALLOWED_FRONTMATTER = {
    "name", "description", "license", "compatibility",
    "metadata", "allowed-tools",
}


def _parse_yaml_simple(text: str) -> Dict[str, Any]:
    """Parse a flat YAML mapping (keys: values only, no nesting beyond
    the metadata dict)."""
    result: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_nested: Dict[str, str] = {}

    for line in text.split("\n"):
        # Skip empty lines and comments
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Nested under 'metadata:'
        if line.startswith("  ") and current_key == "metadata":
            m = re.match(r"  (\w[\w-]*):\s*(.*)", line)
            if m:
                current_nested[m.group(1)] = m.group(2).strip()
            continue

        # Flush nested dict
        if current_key == "metadata" and current_nested:
            result["metadata"] = dict(current_nested)
            current_nested = {}
            current_key = None

        # Top-level key: value
        m = re.match(r"^(\w[\w-]*):\s*(.*)", stripped)
        if m:
            key = m.group(1)
            value = m.group(2).strip().strip('"').strip("'")
            if key == "metadata":
                current_key = key
                current_nested = {}
            else:
                result[key] = value

    # Flush any trailing nested
    if current_key == "metadata" and current_nested:
        result["metadata"] = dict(current_nested)

    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_skill_name(name: str) -> List[str]:
    """Validate a skill name against the agentskills.io spec. Returns a
    list of error messages (empty = valid)."""
    errors = []
    if not name:
        errors.append("name is required")
        return errors
    if len(name) > 64:
        errors.append(f"name too long ({len(name)} > 64)")
    if not _NAME_RE.match(name):
        errors.append(f"name {name!r} must be lowercase letters, numbers, "
                       "single hyphens only")
    return errors


def validate_skill_description(desc: str) -> List[str]:
    errors = []
    if not desc or not desc.strip():
        errors.append("description is required and must be non-empty")
    elif len(desc) > 1024:
        errors.append(f"description too long ({len(desc)} > 1024)")
    return errors


# ---------------------------------------------------------------------------
# SKILL.md parser
# ---------------------------------------------------------------------------

class SkillDefinition:
    """Parsed representation of a Skill."""

    def __init__(self, skill_dir: Path):
        self.skill_dir = Path(skill_dir).resolve()
        self.skill_file = self.skill_dir / "SKILL.md"
        self.name: str = ""
        self.description: str = ""
        self.license: str = ""
        self.compatibility: str = ""
        self.metadata: Dict[str, str] = {}
        self.allowed_tools: str = ""
        self.body: str = ""
        self.errors: List[str] = []
        self._loaded = False

    def load(self) -> bool:
        """Parse and validate SKILL.md. Returns True if valid."""
        self._loaded = True
        if not self.skill_file.exists():
            self.errors.append(f"SKILL.md not found at {self.skill_file}")
            return False

        raw = self.skill_file.read_text(encoding="utf-8")

        # Extract frontmatter
        fm_match = _FRONTMATTER_RE.match(raw)
        if not fm_match:
            self.errors.append("Missing or malformed YAML frontmatter "
                               "(must start with --- ... ---)")
            return False

        fm_text = fm_match.group(1)
        self.body = raw[fm_match.end():].strip()

        # Parse frontmatter
        fm = _parse_yaml_simple(fm_text)

        # Unknown fields
        for key in fm:
            if key not in _ALLOWED_FRONTMATTER:
                self.errors.append(f"Unknown frontmatter field: {key!r}")

        self.name = fm.get("name", "")
        self.description = fm.get("description", "")
        self.license = fm.get("license", "")
        self.compatibility = fm.get("compatibility", "")
        self.metadata = fm.get("metadata", {})
        self.allowed_tools = fm.get("allowed-tools", "")

        # Validate required fields
        self.errors.extend(validate_skill_name(self.name))
        self.errors.extend(validate_skill_description(self.description))

        # Check directory name matches
        if self.name and self.skill_dir.name != self.name:
            self.errors.append(
                f"Directory name {self.skill_dir.name!r} does not match "
                f"skill name {self.name!r}")

        return len(self.errors) == 0

    def list_files(self) -> List[Path]:
        """List all additional files bundled with the skill (excluding SKILL.md)."""
        files = []
        if not self.skill_dir.is_dir():
            return files
        for f in self.skill_dir.rglob("*"):
            if f.is_file() and f.name != "SKILL.md":
                files.append(f.relative_to(self.skill_dir))
        return sorted(files)

    def to_tool_definition(self) -> Dict[str, Any]:
        """Convert to a ToolStore-compatible tool definition (type: skill)."""
        return {
            "name": self.name,
            "type": "skill",
            "description": self.description,
            "skill_dir": str(self.skill_dir),
            "license": self.license,
            "compatibility": self.compatibility,
            "metadata": self.metadata,
            "allowed_tools": self.allowed_tools,
            "source": "skill",
            "schema": {
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "script": {
                            "type": "string",
                            "description": "Script to run from scripts/ dir (for action='run')",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["load", "files", "file", "run"],
                            "description": "load = read full SKILL.md, "
                                           "files = list bundled files, "
                                           "file = read a specific file",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Relative path of file to read "
                                           "(required for action='file')",
                        },
                    },
                    "required": ["action"],
                },
            },
        }


# ---------------------------------------------------------------------------
# Skill manager
# ---------------------------------------------------------------------------

class SkillManager:
    """Manage skill directories: scan, load, validate, register."""

    def __init__(self, skill_dirs: List[str] = None):
        self._skill_dirs: List[Path] = [Path(d) for d in (skill_dirs or [])]
        self._skills: Dict[str, SkillDefinition] = {}

    def add_skill_dir(self, path: str) -> None:
        p = Path(path).expanduser().resolve()
        if p not in self._skill_dirs:
            self._skill_dirs.append(p)

    def scan(self) -> List[SkillDefinition]:
        """Scan all configured directories for skills (directories
        containing a SKILL.md file). Parses and validates each."""
        found: List[SkillDefinition] = []
        seen = set()

        for base in self._skill_dirs:
            if not base.is_dir():
                continue
            for skill_file in base.rglob("SKILL.md"):
                skill_dir = skill_file.parent
                key = str(skill_dir.resolve())
                if key in seen:
                    continue
                seen.add(key)
                sd = SkillDefinition(skill_dir)
                if sd.load():
                    self._skills[sd.name] = sd
                    found.append(sd)
        return found

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name)

    def get_skill_body(self, name: str) -> Optional[str]:
        """Return the full SKILL.md body text for a loaded skill."""
        sd = self._skills.get(name)
        if not sd:
            return None
        # Re-read from disk to get fresh content
        if sd.skill_file.exists():
            raw = sd.skill_file.read_text(encoding="utf-8")
            fm_match = _FRONTMATTER_RE.match(raw)
            if fm_match:
                return raw[fm_match.end():].strip()
        return sd.body

    def get_skill_file(self, skill_name: str, file_path: str) -> Optional[str]:
        """Read a bundled file from a skill directory."""
        sd = self._skills.get(skill_name)
        if not sd:
            return None
        target = (sd.skill_dir / file_path).resolve()
        # Ensure it's within the skill dir (basic traversal guard)
        if not str(target).startswith(str(sd.skill_dir)):
            return None
        if target.is_file():
            return target.read_text(encoding="utf-8")
        return None

    def run_skill_script(self, skill_name: str, script: str) -> str:
        """Execute a script from the skill's scripts/ directory.

        Returns stdout of the script as a string, or an error message.
        """
        import subprocess
        sd = self._skills.get(skill_name)
        if not sd:
            return f"Error: Skill '{skill_name}' not found"
        target = (sd.skill_dir / "scripts" / script).resolve()
        if not str(target).startswith(str(sd.skill_dir)):
            return "Error: Script path escapes skill directory"
        if not target.is_file():
            return f"Error: Script '{script}' not found in skill '{skill_name}'"
        try:
            result = subprocess.run(
                [str(target)], capture_output=True, text=True, timeout=30,
                cwd=str(sd.skill_dir)
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output or "(script produced no output)"
        except subprocess.TimeoutExpired:
            return "Error: Script timed out (30s)"
        except Exception as exc:
            return f"Error running script: {str(exc)}"

    def to_tool_definitions(self) -> List[Dict[str, Any]]:
        """Convert all loaded skills to ToolStore tool definitions."""
        return [sd.to_tool_definition() for sd in self._skills.values()]

    def list_skill_names(self) -> List[str]:
        return sorted(self._skills.keys())


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_skill_manager: Optional[SkillManager] = None


def get_skill_manager(skill_dirs: List[str] = None) -> SkillManager:
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager(skill_dirs or [])
    elif skill_dirs:
        for d in skill_dirs:
            _skill_manager.add_skill_dir(d)
    return _skill_manager
