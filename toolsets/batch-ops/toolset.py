"""
batch‑ops — Bulk file operations: rename, find‑replace, and file stats.
===========================================================================

Pure‑stdlib utilities for batch processing files and directories —
the repetitive tasks agents do across multiple files.
"""

import os
import re
import shutil
from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


# ── batch_rename ───────────────────────────────────────────────────────

@tool
def batch_rename(*, directory: str, pattern: str,
                 replacement: str, dry_run: bool = True,
                 recursive: bool = False) -> dict:
    """Rename files matching a regex pattern, with dry‑run preview.

    Args:
        directory:   Path to the directory.
        pattern:     Regex pattern to match in filenames.
        replacement: Replacement string (can use \\1, \\2 for groups).
        dry_run:     If True, only shows what would change (default True).
        recursive:   If True, descend into subdirectories.

    Returns:
        dict with "changes" list of {old_name, new_name} and "count".
    """
    p = Path(directory).expanduser().resolve()
    if not p.is_dir():
        return {"error": f"Not a directory: {p}"}

    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return {"error": f"Invalid regex: {exc}"}

    changes = []
    glob_fn = p.rglob if recursive else p.glob

    for fpath in glob_fn("*"):
        if not fpath.is_file():
            continue
        old_name = fpath.name
        new_name = compiled.sub(replacement, old_name)
        if new_name != old_name:
            new_path = fpath.parent / new_name
            if new_path.exists():
                changes.append({"old_name": old_name, "new_name": new_name,
                                "error": "target exists"})
            else:
                changes.append({"old_name": old_name, "new_name": new_name})
                if not dry_run:
                    fpath.rename(new_path)

    return {"changes": changes, "count": len(changes),
            "dry_run": dry_run, "directory": str(p)}


# ── batch_find_replace ─────────────────────────────────────────────────

@tool
def batch_find_replace(*, directory: str, pattern: str,
                       find_text: str, replace_text: str,
                       dry_run: bool = True,
                       recursive: bool = False) -> dict:
    """Find‑and‑replace across multiple text files in a directory.

    Args:
        directory:    Path to the directory.
        pattern:      Glob pattern for files (e.g. "*.py", "*.md").
        find_text:    Text to find (literal, not regex).
        replace_text: Replacement text.
        dry_run:      If True, only reports what would change.
        recursive:    If True, descend into subdirectories.

    Returns:
        dict with "changes" list of {file, matches} and "total_files", "total_matches".
    """
    p = Path(directory).expanduser().resolve()
    if not p.is_dir():
        return {"error": f"Not a directory: {p}"}

    glob_fn = p.rglob if recursive else p.glob
    changes = []
    total_files = 0
    total_matches = 0

    for fpath in glob_fn(pattern):
        if not fpath.is_file():
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        count = content.count(find_text)
        if count > 0:
            total_files += 1
            total_matches += count
            changes.append({"file": str(fpath.relative_to(p)), "matches": count})
            if not dry_run:
                new_content = content.replace(find_text, replace_text)
                fpath.write_text(new_content, encoding="utf-8")

    return {"changes": changes, "total_files": total_files,
            "total_matches": total_matches, "dry_run": dry_run,
            "directory": str(p)}


# ── batch_stats ────────────────────────────────────────────────────────

@tool
def batch_stats(*, directory: str, pattern: str = "*",
                recursive: bool = False) -> dict:
    """Get aggregate file statistics for a directory.

    Args:
        directory: Path to the directory.
        pattern:   Glob pattern (default "*" = all files).
        recursive: If True, include subdirectories.

    Returns:
        dict with: file_count, total_size_bytes, extensions ({ext: count}),
                   largest_file, smallest_file
    """
    p = Path(directory).expanduser().resolve()
    if not p.is_dir():
        return {"error": f"Not a directory: {p}"}

    glob_fn = p.rglob if recursive else p.glob
    files = []
    for fpath in glob_fn(pattern):
        if fpath.is_file():
            files.append(fpath)

    if not files:
        return {"file_count": 0, "total_size_bytes": 0, "extensions": {},
                "largest_file": None, "smallest_file": None,
                "directory": str(p)}

    sizes = [(f, f.stat().st_size) for f in files]
    largest = max(sizes, key=lambda x: x[1])
    smallest = min(sizes, key=lambda x: x[1])

    extensions = {}
    for fpath, _ in sizes:
        ext = fpath.suffix.lower() or "(none)"
        extensions[ext] = extensions.get(ext, 0) + 1

    return {
        "file_count": len(files),
        "total_size_bytes": sum(s for _, s in sizes),
        "extensions": extensions,
        "largest_file": {"name": largest[0].name, "size_bytes": largest[1]},
        "smallest_file": {"name": smallest[0].name, "size_bytes": smallest[1]},
        "directory": str(p),
    }


# ── batch_copy ─────────────────────────────────────────────────────────

@tool
def batch_copy(*, source_dir: str, dest_dir: str,
               pattern: str = "*", recursive: bool = False,
               overwrite: bool = False) -> dict:
    """Copy files matching a pattern from source to destination directory.

    Args:
        source_dir: Source directory.
        dest_dir:   Destination directory.
        pattern:    Glob pattern to match (default "*").
        recursive:  If True, descend into subdirectories.
        overwrite:  If True, overwrite existing files.

    Returns:
        dict with "copied" list of filenames and "count".
    """
    src = Path(source_dir).expanduser().resolve()
    dst = Path(dest_dir).expanduser().resolve()

    if not src.is_dir():
        return {"error": f"Not a directory: {src}"}

    dst.mkdir(parents=True, exist_ok=True)

    glob_fn = src.rglob if recursive else src.glob
    copied = []
    skipped = []

    for fpath in glob_fn(pattern):
        if not fpath.is_file():
            continue
        dest_path = dst / fpath.name
        if dest_path.exists() and not overwrite:
            skipped.append(fpath.name)
            continue
        shutil.copy2(fpath, dest_path)
        copied.append(fpath.name)

    return {"copied": copied, "count": len(copied),
            "skipped": skipped, "dest_dir": str(dst)}
