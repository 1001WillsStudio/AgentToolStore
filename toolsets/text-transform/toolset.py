"""
text‑transform — Diff, regex extraction, markdown tables, and text statistics.
================================================================================

Pure‑stdlib toolkit for the text‑munging tasks that agents do every day
but currently need throw‑away scripts for.
"""

import difflib
import re

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn  # no‑op when toolstore package not installed


# ── text_diff ──────────────────────────────────────────────────────────

@tool
def text_diff(*, original: str, modified: str,
              context_lines: int = 3, label_a: str = "original",
              label_b: str = "modified") -> dict:
    """Compute a unified diff between two text blocks.

    Args:
        original:      The original text.
        modified:      The modified text.
        context_lines: Lines of context around each change (default 3).
        label_a:       Label for the original in the header.
        label_b:       Label for the modified in the header.

    Returns:
        dict with keys:
          diff     — unified diff string (empty if identical)
          added    — number of added lines
          removed  — number of removed lines
          changed  — True if the texts differ
    """
    a = original.splitlines(keepends=True)
    b = modified.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        a, b, fromfile=label_a, tofile=label_b, n=context_lines
    ))

    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

    return {
        "diff": "".join(diff_lines) if diff_lines else "",
        "added": added,
        "removed": removed,
        "changed": len(diff_lines) > 0,
    }


# ── regex_extract ──────────────────────────────────────────────────────

@tool
def regex_extract(*, text: str, pattern: str,
                  flags: list = None, max_matches: int = 0) -> dict:
    """Extract all regex matches from text, with optional capture groups.

    Args:
        text:        The text to search in.
        pattern:     Python regex pattern.
        flags:       List of flag names: IGNORECASE, MULTILINE, DOTALL.
        max_matches: Maximum matches to return (0 = all).

    Returns:
        dict with:
          matches — list of match dicts:
            {index, start, end, text, groups: [...]}
          count   — total matches found
    """
    flag_map = {
        "IGNORECASE": re.IGNORECASE,
        "MULTILINE": re.MULTILINE,
        "DOTALL": re.DOTALL,
    }
    re_flags = 0
    for f in (flags or []):
        re_flags |= flag_map.get(f.upper(), 0)

    try:
        compiled = re.compile(pattern, re_flags)
    except re.error as exc:
        return {"error": f"Invalid regex pattern: {exc}"}

    matches = []
    for idx, m in enumerate(compiled.finditer(text)):
        match_obj = {
            "index": idx,
            "start": m.start(),
            "end": m.end(),
            "text": m.group(0),
            "groups": list(m.groups()) if m.groups() else [],
        }
        if m.groupdict():
            match_obj["named_groups"] = m.groupdict()
        matches.append(match_obj)
        if max_matches and len(matches) >= max_matches:
            break

    return {"matches": matches, "count": len(matches)}


# ── markdown_table ─────────────────────────────────────────────────────

@tool
def markdown_table(*, data: list, columns: list = None,
                   align: str = "left") -> dict:
    """Convert a list of dicts to a formatted Markdown table.

    Args:
        data:    List of dicts (each dict = one row).
        columns: Column order (default: keys from first row).
        align:   Column alignment: left, center, or right.

    Returns:
        dict with "markdown" containing the formatted table string.
    """
    if not data:
        return {"markdown": "", "rows": 0, "columns": 0}

    if columns is None:
        columns = list(data[0].keys()) if data else []

    align_chars = {"left": ":", "center": ":", "right": ""}
    align_post = {"left": "-", "center": ":", "right": "-:"}

    def _cell(v):
        s = str(v) if v is not None else ""
        return s.replace("|", "\\|").replace("\n", " ")

    widths = {}
    for col in columns:
        widths[col] = len(str(col))
    for row in data:
        for col in columns:
            val_len = len(_cell(row.get(col, "")))
            if val_len > widths.get(col, 0):
                widths[col] = val_len

    header = "| " + " | ".join(str(c).ljust(widths[c]) for c in columns) + " |"
    sep = "|" + "|".join(
        f" {align_chars.get(align, ':')}{'-' * (widths[c] - 1)}{align_post.get(align, '-')} "
        for c in columns
    ) + "|"

    rows = []
    for row in data:
        rows.append("| " + " | ".join(
            _cell(row.get(c, "")).ljust(widths[c]) for c in columns
        ) + " |")

    return {
        "markdown": "\n".join([header, sep] + rows),
        "rows": len(data),
        "columns": len(columns),
    }


# ── text_stats ─────────────────────────────────────────────────────────

@tool
def text_stats(*, text: str) -> dict:
    """Compute statistics about a block of text.

    Args:
        text: The text to analyze.

    Returns:
        dict with:
          chars, words, lines, sentences, paragraphs,
          avg_word_len, avg_sentence_len,
          flesch_reading_ease (0–100, higher = easier)
    """
    chars = len(text)
    words = len(re.findall(r"\b\w+\b", text))
    lines = text.count("\n") + 1 if text else 0
    sentences = max(len(re.findall(r"[.!?]+", text)), 1)
    paragraphs = max(len(re.findall(r"\n\s*\n", text)) + 1, 1)

    avg_word_len = round(chars / words, 1) if words else 0
    avg_sentence_len = round(words / sentences, 1) if words else 0

    syllables = 0
    for w in re.findall(r"\b\w+\b", text.lower()):
        s = len(re.findall(r"[aeiouy]+", w))
        syllables += max(s, 1)
    try:
        flesch = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
        flesch = max(0, min(100, round(flesch, 1)))
    except (ZeroDivisionError, ValueError):
        flesch = 0

    return {
        "chars": chars,
        "words": words,
        "lines": lines,
        "sentences": sentences,
        "paragraphs": paragraphs,
        "avg_word_len": avg_word_len,
        "avg_sentence_len": avg_sentence_len,
        "flesch_reading_ease": flesch,
    }
