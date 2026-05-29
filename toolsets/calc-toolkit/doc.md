# calc‑toolkit

Safe expression evaluation, unit conversion, and basic statistics.
Pure‑stdlib — no dependencies.

---

## When to Use This Toolset

- Evaluating math expressions safely (no `eval()` risks)
- Converting between units (length, weight, temperature, time, digital)
- Computing quick statistics (mean, median, stdev) on number lists
- Quick calculations agents need without terminal scripts

---

## Process

```
Choose function → Provide input → Get result
```

All functions are one‑shot — no multi‑step workflows needed.

---

## Function Reference

### `eval_expression`

Safely evaluate a mathematical expression using Python's AST parser.

**Supported:** `+`, `-`, `*`, `/`, `**`, `//`, `%`, `sqrt()`, `log()`, `sin()`, `cos()`, `pi`, `e`, `tau`, `abs()`, `round()`, `min()`, `max()`, `factorial()`, `ceil()`, `floor()`

**Args:** `expr` (str) — e.g. `"sqrt(16) + 2 * pi"`

**Returns:** `{result, expression}` or `{error}`

### `convert_unit`

Convert between common units.

**Supported units:**
| Category | Units |
|----------|-------|
| Length | m, km, cm, mm, ft, in, mile |
| Weight | kg, g, lb, oz |
| Temperature | C, F, K |
| Time | h, min, s, day |
| Digital | B, KB, MB, GB, TB |

**Args:** `value` (float), `from_unit` (str), `to_unit` (str)

**Returns:** `{result, from_unit, to_unit, original_value, formula}`

### `basic_stats`

Compute count, sum, min, max, mean, median, standard deviation, variance.

**Args:** `numbers` (list of numbers)

**Returns:** `{count, sum, min, max, mean, median, stdev, variance}`

---

## Guidelines

### Do
- Use `eval_expression` instead of writing Python scripts for simple math
- Check unit conversion results for reasonable magnitudes
- Verify `basic_stats` on known datasets before trusting outputs

### Don't
- Don't pass user‑supplied strings to eval without sanitization (handled by AST)
- Don't use for high‑precision scientific computing
