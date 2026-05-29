"""
file‑verify — Validate file formats, compute hashes, and detect encodings.
============================================================================

Systematic file verification so agents don't have to write ad‑hoc checks.
All functions take a filepath and return a structured result dict.
"""

import csv
import hashlib
import io
import json
from pathlib import Path

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn  # no‑op when toolstore package not installed


# ── check_json ─────────────────────────────────────────────────────────

@tool
def check_json(*, filepath: str) -> dict:
    """Validate a JSON file and return the exact parse error location.

    Args:
        filepath: Path to the JSON file.

    Returns:
        dict with:
          valid   — True/False
          error   — error message (if invalid)
          line    — line number of error (if invalid)
          col     — column of error (if invalid)
          size_kb — file size in kilobytes
    """
    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        return {"valid": False, "error": f"File not found: {p}"}

    size_kb = round(p.stat().st_size / 1024, 1)

    try:
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as exc:
        return {"valid": False, "error": f"Not valid UTF-8: {exc}",
                "size_kb": size_kb}

    try:
        json.loads(content)
        return {"valid": True, "size_kb": size_kb}
    except json.JSONDecodeError as exc:
        return {
            "valid": False,
            "error": exc.msg,
            "line": exc.lineno,
            "col": exc.colno,
            "size_kb": size_kb,
        }


# ── check_yaml ─────────────────────────────────────────────────────────

@tool
def check_yaml(*, filepath: str) -> dict:
    """Validate a YAML file and return parse status with document count.

    Args:
        filepath: Path to the YAML file.

    Returns:
        dict with:
          valid     — True/False
          documents — number of YAML documents found (if valid)
          error     — error message (if invalid)
          size_kb   — file size in kilobytes
    """
    try:
        import yaml
    except ImportError:
        return {"error": "PyYAML not installed — run: pip install pyyaml"}

    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        return {"valid": False, "error": f"File not found: {p}"}

    size_kb = round(p.stat().st_size / 1024, 1)

    try:
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as exc:
        return {"valid": False, "error": f"Not valid UTF-8: {exc}",
                "size_kb": size_kb}

    try:
        docs = list(yaml.safe_load_all(content))
        doc_count = sum(1 for d in docs if d is not None)
        return {"valid": True, "documents": doc_count, "size_kb": size_kb}
    except yaml.YAMLError as exc:
        msg = str(exc).split("\n")[0] if str(exc) else "YAML parse error"
        return {"valid": False, "error": msg, "size_kb": size_kb}


# ── check_csv ──────────────────────────────────────────────────────────

@tool
def check_csv(*, filepath: str, delimiter: str = ",") -> dict:
    """Validate CSV structure — consistent columns, readable encoding.

    Args:
        filepath:  Path to the CSV file.
        delimiter: Field delimiter (default comma).

    Returns:
        dict with:
          valid      — True/False
          columns    — number of columns detected
          rows       — total data rows
          error      — error message (if invalid)
          delimiter  — the delimiter used
    """
    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        return {"valid": False, "error": f"File not found: {p}"}

    encoding = "utf-8"
    try:
        import chardet
        with open(p, "rb") as f:
            raw = f.read(10000)
        detected = chardet.detect(raw)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
    except ImportError:
        pass

    try:
        with open(p, "r", encoding=encoding, errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)
    except Exception as exc:
        return {"valid": False, "error": f"Cannot read CSV: {exc}"}

    if not rows:
        return {"valid": True, "columns": 0, "rows": 0, "delimiter": delimiter}

    expected = len(rows[0])
    bad_rows = []
    for i, row in enumerate(rows):
        if len(row) != expected:
            bad_rows.append({"row": i + 1, "expected_cols": expected,
                             "actual_cols": len(row)})

    result = {
        "valid": len(bad_rows) == 0,
        "columns": expected,
        "rows": len(rows),
        "delimiter": delimiter,
        "encoding": encoding,
    }

    if bad_rows:
        result["error"] = f"{len(bad_rows)} row(s) have inconsistent column counts"
        result["bad_rows"] = bad_rows[:20]

    return result


# ── file_hash ──────────────────────────────────────────────────────────

@tool
def file_hash(*, filepath: str, algorithm: str = "sha256") -> dict:
    """Compute a cryptographic hash of a file.

    Args:
        filepath:  Path to the file.
        algorithm: One of sha256, md5, sha1, sha512 (default sha256).

    Returns:
        dict with "algorithm", "hash" (hex), "file", "size_bytes".
    """
    allowed = {"sha256": hashlib.sha256, "md5": hashlib.md5,
               "sha1": hashlib.sha1, "sha512": hashlib.sha512}

    algo = algorithm.lower()
    if algo not in allowed:
        return {"error": f"Unknown algorithm '{algo}'. Use: {', '.join(allowed)}"}

    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        return {"error": f"File not found: {p}"}
    if not p.is_file():
        return {"error": f"Not a regular file: {p}"}

    h = allowed[algo]()
    size = p.stat().st_size

    with open(p, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)

    return {
        "algorithm": algo,
        "hash": h.hexdigest(),
        "file": p.name,
        "size_bytes": size,
    }


# ── detect_encoding ────────────────────────────────────────────────────

@tool
def detect_encoding(*, filepath: str) -> dict:
    """Detect the character encoding of a text file.

    Uses chardet when available; falls back to a basic UTF‑8 / UTF‑16
    BOM check if chardet is not installed.

    Args:
        filepath: Path to the file.

    Returns:
        dict with:
          encoding      — detected encoding name
          confidence    — 0.0–1.0 (only with chardet)
          bom           — detected BOM or None
          method        — "chardet" or "bom"
    """
    p = Path(filepath).expanduser().resolve()
    if not p.exists():
        return {"error": f"File not found: {p}"}

    try:
        import chardet
        with open(p, "rb") as f:
            raw = f.read(50000)
        result = chardet.detect(raw)
        return {
            "encoding": result.get("encoding", "unknown"),
            "confidence": round(result.get("confidence", 0), 2),
            "method": "chardet",
            "bom": _detect_bom(raw),
        }
    except ImportError:
        pass

    with open(p, "rb") as f:
        head = f.read(4)

    bom, enc = _detect_bom(head), "unknown"
    if head.startswith(b"\xef\xbb\xbf"):
        enc = "utf-8"
    elif head.startswith(b"\xff\xfe\x00\x00"):
        enc = "utf-32-le"
    elif head.startswith(b"\x00\x00\xfe\xff"):
        enc = "utf-32-be"
    elif head.startswith(b"\xff\xfe"):
        enc = "utf-16-le"
    elif head.startswith(b"\xfe\xff"):
        enc = "utf-16-be"

    return {"encoding": enc, "confidence": 1.0 if enc != "unknown" else 0,
            "method": "bom", "bom": bom}


def _detect_bom(raw: bytes) -> str:
    """Return the BOM name if present."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return "UTF-8 BOM"
    if raw.startswith(b"\xff\xfe\x00\x00"):
        return "UTF-32 LE BOM"
    if raw.startswith(b"\x00\x00\xfe\xff"):
        return "UTF-32 BE BOM"
    if raw.startswith(b"\xff\xfe"):
        return "UTF-16 LE BOM"
    if raw.startswith(b"\xfe\xff"):
        return "UTF-16 BE BOM"
    return None
