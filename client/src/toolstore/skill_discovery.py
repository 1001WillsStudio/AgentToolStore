"""
Recursive skill discovery engine.

Walks a directory tree and discovers all skills (directories containing
SKILL.md), parses them, and returns structured results including
hierarchy/category information derived from path structure.

Supports three layout patterns:

    Case A — single skill (root itself is a skill):
        /some/skill-name/SKILL.md → one skill

    Case B — flat skill collection:
        /some/skills/
            ├── pdf-processing/SKILL.md
            ├── code-review/SKILL.md
            └── webapp-testing/SKILL.md

    Case C — nested / categorized skill collection:
        /some/skills/
            ├── debug/SKILL.md
            ├── design/SKILL.md
            ├── development/
            │   ├── agent-api/SKILL.md
            │   ├── mcp-builder/SKILL.md
            │   └── webapp-testing/SKILL.md
            └── documents/SKILL.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from toolstore.skill_manager import SkillDefinition


@dataclass
class DiscoveredSkill:
    """A single skill discovered in a directory tree."""

    skill_def: "SkillDefinition"
    rel_path: Path   # relative path from the scan root
    category: str    # derived from parent directory hierarchy ("" for root-level)

    @property
    def name(self) -> str:
        return self.skill_def.name

    @property
    def description(self) -> str:
        return self.skill_def.description

    @property
    def is_valid(self) -> bool:
        return len(self.skill_def.errors) == 0

    @property
    def errors(self) -> List[str]:
        return self.skill_def.errors


@dataclass
class DiscoveryResult:
    """Complete result of a skill discovery scan."""

    root_path: Path
    skills: List[DiscoveredSkill] = field(default_factory=list)
    scan_errors: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # convenience accessors
    # ------------------------------------------------------------------

    @property
    def valid_skills(self) -> List[DiscoveredSkill]:
        return [s for s in self.skills if s.is_valid]

    @property
    def invalid_skills(self) -> List[DiscoveredSkill]:
        return [s for s in self.skills if not s.is_valid]

    @property
    def total(self) -> int:
        return len(self.skills)

    @property
    def valid_count(self) -> int:
        return len(self.valid_skills)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_skills)

    # ------------------------------------------------------------------
    # grouping
    # ------------------------------------------------------------------

    def by_category(self) -> Dict[str, List[DiscoveredSkill]]:
        """Group skills by their derived category tag.

        Returns a dict mapping category → skills (preserves insertion
        order from Python 3.7+).
        """
        cats: Dict[str, List[DiscoveredSkill]] = {}
        for ds in self.skills:
            cat = ds.category or "(root)"
            cats.setdefault(cat, []).append(ds)
        return cats

    # ------------------------------------------------------------------
    # formatting
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """One-line summary suitable for progress output."""
        return (
            f"Discovered {self.total} skill(s) — "
            f"{self.valid_count} valid, "
            f"{self.invalid_count} invalid"
        )

    def tree(self) -> str:
        """Pretty-printed tree of discovered skills grouped by category."""
        lines = [f"📁 {self.root_path}", f"   {self.summary()}", ""]
        by_cat = self.by_category()
        for cat, skills in by_cat.items():
            cat_icon = "📂" if cat == "(root)" else "📂"
            lines.append(f"  {cat_icon} {cat}/")
            for ds in skills:
                icon = "✅" if ds.is_valid else "⚠️"
                lines.append(f"    {icon} {ds.name}")
                if not ds.is_valid:
                    for err in ds.errors:
                        lines.append(f"       ❌ {err}")
        return "\n".join(lines)

    def report(self) -> str:
        """Full report with validation details and error messages."""
        parts = [f"## Skill Discovery Report", f"", f"Scan root: `{self.root_path}`", f""]
        parts.append(f"**{self.summary()}**")
        parts.append("")

        # Valid skills table
        if self.valid_skills:
            parts.append("### ✅ Valid Skills")
            parts.append("")
            parts.append("| Name | Category | Description |")
            parts.append("|------|----------|-------------|")
            for ds in self.valid_skills:
                desc = ds.description[:80].replace("\n", " ")
                cat = ds.category or "—"
                parts.append(f"| `{ds.name}` | `{cat}` | {desc} |")
            parts.append("")

        # Invalid skills
        if self.invalid_skills:
            parts.append("### ⚠️ Invalid Skills")
            parts.append("")
            for ds in self.invalid_skills:
                parts.append(f"**`{ds.name or ds.rel_path}`**")
                for err in ds.errors:
                    parts.append(f"- ❌ {err}")
                parts.append("")

        # Scan errors (permission denied, etc.)
        if self.scan_errors:
            parts.append("### 🔴 Scan Errors")
            parts.append("")
            for err in self.scan_errors:
                parts.append(f"- {err}")
            parts.append("")

        return "\n".join(parts)


# ======================================================================
# Public API
# ======================================================================

def discover_skills(root: str | Path, *, recursive: bool = True) -> DiscoveryResult:
    """Walk a directory tree and discover all skills.

    A *skill* is any directory that contains a ``SKILL.md`` file.  The
    scan automatically detects whether *root* itself is a skill (Case A)
    or a container of multiple skills (Cases B / C).

    Parameters
    ----------
    root:
        Path to scan.  May be a single skill directory or a tree
        containing many skills.
    recursive:
        When ``True`` (the default) sub-directories are walked
        recursively.  Set to ``False`` for a shallow (single-level)
        scan.

    Returns
    -------
    DiscoveryResult
        Structured result containing every discovered skill and any
        errors encountered during the scan.
    """
    from toolstore.skill_manager import SkillDefinition

    root_path = Path(root).expanduser().resolve()
    result = DiscoveryResult(root_path=root_path)

    if not root_path.is_dir():
        result.scan_errors.append(f"Path does not exist or is not a directory: {root_path}")
        return result

    # --- Case A: root is itself a skill -----------------------------------
    if (root_path / "SKILL.md").exists():
        sd = SkillDefinition(root_path)
        sd.load()
        result.skills.append(DiscoveredSkill(
            skill_def=sd,
            rel_path=Path(root_path.name),
            category="",
        ))
        return result

    # --- Cases B / C: root is a container ---------------------------------
    _walk_for_skills(root=root_path, current=root_path,
                     result=result, recursive=recursive)

    return result


def discover_skills_batch(
    *paths: str | Path,
    recursive: bool = True,
) -> Dict[str, DiscoveryResult]:
    """Run :func:`discover_skills` against multiple paths.

    Returns a dict mapping each path → its ``DiscoveryResult``.
    """
    return {str(p): discover_skills(p, recursive=recursive) for p in paths}


# ======================================================================
# Internal helpers
# ======================================================================

def _walk_for_skills(
    *,
    root: Path,
    current: Path,
    result: DiscoveryResult,
    recursive: bool,
) -> None:
    """Recursively walk *current*, appending discovered skills to *result*."""
    try:
        entries = sorted(current.iterdir())
    except PermissionError:
        result.scan_errors.append(f"Permission denied: {current}")
        return

    subdirs = [e for e in entries if e.is_dir() and not e.name.startswith(".")]

    for subdir in subdirs:
        if (subdir / "SKILL.md").exists():
            _ingest_skill_dir(subdir, root, result)

        if recursive:
            _walk_for_skills(root=root, current=subdir,
                             result=result, recursive=True)


def _ingest_skill_dir(skill_dir: Path, root: Path, result: DiscoveryResult) -> None:
    """Parse *skill_dir* as a skill and append to *result*."""
    from toolstore.skill_manager import SkillDefinition

    sd = SkillDefinition(skill_dir)
    sd.load()

    rel = skill_dir.relative_to(root)
    category = str(rel.parent) if str(rel.parent) != "." else ""

    result.skills.append(DiscoveredSkill(
        skill_def=sd,
        rel_path=rel,
        category=category,
    ))
