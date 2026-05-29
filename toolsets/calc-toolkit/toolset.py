"""
calc‑toolkit — Evaluate math expressions, convert units, and compute statistics.
===================================================================================

Safe expression evaluation with proper operator precedence, unit conversions,
and basic statistical operations — all stdlib, no external deps.
"""

import math
import operator
import re
from typing import Any

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


# ── Safe expression evaluator ─────────────────────────────────────────

_SAFE_OPS = {
    "+": operator.add, "-": operator.sub, "*": operator.mul,
    "/": operator.truediv, "**": operator.pow, "%": operator.mod,
    "//": operator.floordiv,
}
_SAFE_FUNCTIONS = {
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "log2": math.log2, "exp": math.exp,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "pi": math.pi, "e": math.e, "tau": math.tau,
    "ceil": math.ceil, "floor": math.floor, "factorial": math.factorial,
}


# ── eval_expression ────────────────────────────────────────────────────

@tool
def eval_expression(*, expr: str) -> dict:
    """Safely evaluate a mathematical expression.

    Supports: +, -, *, /, **, //, %, sqrt(), log(), sin(), cos(),
    pi, e, tau, abs(), round(), min(), max(), factorial(), ceil(), floor().

    Args:
        expr: Math expression string (e.g. "sqrt(16) + 2 * pi").

    Returns:
        dict with "result" (number) or "error".
    """
    import ast

    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as exc:
        return {"error": f"Syntax error: {exc}"}

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            name = node.id
            if name in _SAFE_FUNCTIONS:
                return _SAFE_FUNCTIONS[name]
            return {"error": f"Unknown name: {name}"}
        if isinstance(node, ast.BinOp):
            op_name = type(node.op).__name__
            python_op = {
                "Add": "+", "Sub": "-", "Mult": "*", "Div": "/",
                "Pow": "**", "Mod": "%", "FloorDiv": "//",
            }.get(op_name)
            if python_op not in _SAFE_OPS:
                return {"error": f"Unsupported operator: {op_name}"}
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(left, dict) and "error" in left:
                return left
            if isinstance(right, dict) and "error" in right:
                return right
            try:
                return _SAFE_OPS[python_op](left, right)
            except Exception as exc:
                return {"error": f"Compute error: {exc}"}
        if isinstance(node, ast.Call):
            func = _eval(node.func)
            if isinstance(func, dict) and "error" in func:
                return func
            args = [_eval(a) for a in node.args]
            for a in args:
                if isinstance(a, dict) and "error" in a:
                    return a
            try:
                return func(*args)
            except Exception as exc:
                return {"error": f"Function error: {exc}"}
        if isinstance(node, ast.UnaryOp):
            op_name = type(node.op).__name__
            val = _eval(node.operand)
            if isinstance(val, dict) and "error" in val:
                return val
            if op_name == "USub":
                return -val
            if op_name == "UAdd":
                return +val
        return {"error": f"Unsupported expression: {type(node).__name__}"}

    result = _eval(tree)
    if isinstance(result, dict) and "error" in result:
        return result
    if isinstance(result, float) and result == int(result):
        result = int(result)
    return {"result": result, "expression": expr}


# ── convert_unit ───────────────────────────────────────────────────────

_UNIT_CONVERSIONS = {
    # Length
    ("m", "km"): 0.001, ("km", "m"): 1000,
    ("m", "cm"): 100, ("cm", "m"): 0.01,
    ("m", "mm"): 1000, ("mm", "m"): 0.001,
    ("km", "mile"): 0.621371, ("mile", "km"): 1.60934,
    ("ft", "m"): 0.3048, ("m", "ft"): 3.28084,
    ("in", "cm"): 2.54, ("cm", "in"): 0.393701,
    # Weight
    ("kg", "g"): 1000, ("g", "kg"): 0.001,
    ("kg", "lb"): 2.20462, ("lb", "kg"): 0.453592,
    ("lb", "oz"): 16, ("oz", "lb"): 0.0625,
    # Temperature (special handling)
    ("C", "K"): "add:273.15", ("K", "C"): "sub:273.15",
    ("C", "F"): "c_to_f", ("F", "C"): "f_to_c",
    # Time
    ("h", "min"): 60, ("min", "h"): 1/60,
    ("min", "s"): 60, ("s", "min"): 1/60,
    ("h", "s"): 3600, ("s", "h"): 1/3600,
    ("day", "h"): 24, ("h", "day"): 1/24,
    # Digital
    ("B", "KB"): 1/1024, ("KB", "B"): 1024,
    ("KB", "MB"): 1/1024, ("MB", "KB"): 1024,
    ("MB", "GB"): 1/1024, ("GB", "MB"): 1024,
    ("GB", "TB"): 1/1024, ("TB", "GB"): 1024,
}


@tool
def convert_unit(*, value: float, from_unit: str, to_unit: str) -> dict:
    """Convert a value between units (length, weight, temperature, time, digital).

    Supported units:
      Length: m, km, cm, mm, ft, in, mile
      Weight: kg, g, lb, oz
      Temp:   C, F, K
      Time:   h, min, s, day
      Digital: B, KB, MB, GB, TB

    Args:
        value:     Numeric value to convert.
        from_unit: Source unit (case‑sensitive).
        to_unit:   Target unit (case‑sensitive).

    Returns:
        dict with "result", "from_unit", "to_unit", "original_value" or "error".
    """
    fkey = from_unit.strip()
    tkey = to_unit.strip()

    if fkey == tkey:
        return {"result": value, "from_unit": fkey, "to_unit": tkey,
                "original_value": value}

    factor = _UNIT_CONVERSIONS.get((fkey, tkey))
    if factor is None:
        return {"error": f"Unknown conversion: {fkey} → {tkey}. "
                f"Supported: {sorted(set(k[0] for k in _UNIT_CONVERSIONS))}"}

    if isinstance(factor, str):
        if factor == "add:273.15":
            result = value + 273.15
        elif factor == "sub:273.15":
            result = value - 273.15
        elif factor == "c_to_f":
            result = value * 9/5 + 32
        elif factor == "f_to_c":
            result = (value - 32) * 5/9
        else:
            return {"error": f"Unknown conversion function: {factor}"}
    else:
        result = value * factor

    if isinstance(result, float) and result == int(result):
        result = int(result)

    return {"result": result, "from_unit": fkey, "to_unit": tkey,
            "original_value": value, "formula": f"{value} {fkey} → {result} {tkey}"}


# ── basic_stats ────────────────────────────────────────────────────────

@tool
def basic_stats(*, numbers: list) -> dict:
    """Compute basic statistics for a list of numbers.

    Args:
        numbers: List of numeric values.

    Returns:
        dict with: count, sum, min, max, mean, median, stdev, variance.
    """
    if not numbers:
        return {"error": "Empty list"}

    try:
        nums = [float(n) for n in numbers]
    except (ValueError, TypeError) as exc:
        return {"error": f"Invalid number in list: {exc}"}

    n = len(nums)
    total = sum(nums)
    mean_val = total / n
    sorted_nums = sorted(nums)

    # Median
    if n % 2 == 0:
        median_val = (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2
    else:
        median_val = sorted_nums[n // 2]

    # Standard deviation (population)
    variance = sum((x - mean_val) ** 2 for x in nums) / n
    stdev = math.sqrt(variance)

    return {
        "count": n, "sum": total, "min": sorted_nums[0],
        "max": sorted_nums[-1], "mean": round(mean_val, 4),
        "median": round(median_val, 4),
        "stdev": round(stdev, 4), "variance": round(variance, 4),
    }
