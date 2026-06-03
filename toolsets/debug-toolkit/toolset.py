"""debug‑toolkit — Parse and analyze error messages and stack traces.
==============================================================="""

import re

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


@tool
def analyze_error(*, error_text: str) -> dict:
    """Parse an error message or stack trace into structured parts.

    Handles Python tracebacks, generic error messages, and multi-line logs.

    Args:
        error_text: The full error/stack trace text.

    Returns:
        dict with: error_type, message, file, line, traceback_frames
    """
    result = {"error_type": "", "message": "", "file": "", "line": None, "frames": []}

    # Python traceback
    tb_match = re.search(r'Traceback \(most recent call last\):', error_text)
    if tb_match:
        frames = re.findall(r'File "(.+?)", line (\d+), in (\w+)', error_text)
        for fpath, lineno, func in frames:
            result["frames"].append({"file": fpath, "line": int(lineno), "function": func})
        err_match = re.search(r'(\w+(?:Error|Exception|Warning)): (.+)', error_text)
        if err_match:
            result["error_type"] = err_match.group(1)
            result["message"] = err_match.group(2)
        if result["frames"]:
            result["file"] = result["frames"][-1]["file"]
            result["line"] = result["frames"][-1]["line"]
        return result

    # Generic error
    err_match = re.search(r'(\w+(?:Error|Exception|Warning)):?\s*(.+)', error_text)
    if err_match:
        result["error_type"] = err_match.group(1)
        result["message"] = err_match.group(2).strip()
    elif error_text.strip():
        result["message"] = error_text.strip().split("\n")[0]

    return result


@tool
def extract_log_patterns(*, log_text: str, pattern: str = "") -> dict:
    """Extract common log patterns: timestamps, IPs, error levels, URLs.

    Args:
        log_text: The log content to scan.
        pattern:  One of "timestamps", "ips", "errors", "urls", "all".
                  Defaults to "all".

    Returns:
        dict with found patterns grouped by type.
    """
    patterns = {}
    if pattern in ("all", "timestamps"):
        ts = re.findall(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?', log_text)
        if ts:
            patterns["timestamps"] = ts
    if pattern in ("all", "ips"):
        ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', log_text)
        if ips:
            # Filter valid IPs only
            valid = [ip for ip in ips if all(0 <= int(o) <= 255 for o in ip.split("."))]
            if valid:
                patterns["ips"] = valid[:50]
    if pattern in ("all", "errors"):
        errs = re.findall(r'(ERROR|WARN|WARNING|CRITICAL|FATAL|DEBUG|INFO|TRACE)', log_text)
        if errs:
            from collections import Counter
            patterns["log_levels"] = dict(Counter(errs))
    if pattern in ("all", "urls"):
        urls = re.findall(r'https?://[^\s<>"\'\)]+', log_text)
        if urls:
            patterns["urls"] = urls[:50]

    patterns["total_chars"] = len(log_text)
    patterns["total_lines"] = log_text.count("\n") + 1
    return patterns
