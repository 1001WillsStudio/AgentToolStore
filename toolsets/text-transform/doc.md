# text‑transform

Diff computation, regex extraction, Markdown table generation, and text statistics.
Pure‑stdlib toolkit for the text‑munging tasks agents do constantly but currently
need throw‑away scripts for.

---

## When to Use This Toolset

- Comparing two versions of text and getting a unified diff
- Extracting structured data from unstructured text using regex
- Converting tabular data (list of dicts) into Markdown tables for reports
- Computing readability statistics for generated content
- Validating that text transformations produced expected results

---

## Process

### General Text Transformation Workflow

```
Understand the input → Choose the right function → Execute → Validate output
```

1. **Understand** what you're starting with: Is it a single string? Two strings to compare?
   Structured data? Unstructured text with patterns?
2. **Choose** the right function(s) based on the task
3. **Execute** — most functions are one‑shot; combine them for multi‑step transforms
4. **Validate** — use `text_stats` to confirm the output has reasonable characteristics,
   or `text_diff` to verify that a transformation produced expected changes

---

## Function Reference

### `text_diff`

Compute a unified diff between two text blocks.

**When to use:**
- Comparing two versions of a file or output
- Showing exactly what changed after a transformation
- Verifying that an edit only changed what you intended

**Args:**
- `original` (str) — The original text
- `modified` (str) — The modified text
- `context_lines` (int, optional) — Lines of context around changes (default 3)
- `label_a` (str, optional) — Label for original in header
- `label_b` (str, optional) — Label for modified in header

**Returns:** `{diff, added, removed, changed}`

**Workflow tip:** After applying a transformation, use `text_diff(original=before, modified=after)`
to confirm the diff contains only expected changes.

### `regex_extract`

Find all regex matches with positions, capture groups, and named groups.

**When to use:**
- Extracting URLs, emails, dates, or IDs from text
- Parsing structured patterns from semi‑structured output
- Validating that expected patterns exist in generated text

**Args:**
- `text` (str) — The text to search
- `pattern` (str) — Python regex pattern
- `flags` (list, optional) — `["IGNORECASE"]`, `["MULTILINE"]`, `["DOTALL"]`, or combinations
- `max_matches` (int, optional) — Limit matches returned (0 = all)

**Returns:** `{matches: [{index, start, end, text, groups, named_groups?}], count}`

### `markdown_table`

Convert structured data to a formatted Markdown table.

**When to use:**
- Generating report tables from data
- Formatting query results for display
- Creating documentation tables from structured data

**Args:**
- `data` (list) — List of dicts, each dict = one row
- `columns` (list, optional) — Column order (default: keys from first row)
- `align` (str, optional) — `"left"` (default), `"center"`, or `"right"`

**Returns:** `{markdown, rows, columns}`

### `text_stats`

Compute readability and structure statistics for a text block.

**When to use:**
- Checking if generated content is at an appropriate reading level
- Validating that output has expected word/character counts
- Profiling text before processing (e.g., for summarization)

**Args:**
- `text` (str) — The text to analyze

**Returns:** `{chars, words, lines, sentences, paragraphs, avg_word_len, avg_sentence_len, flesch_reading_ease}`

**Flesch Reading Ease scale:**
| Score | Level |
|-------|-------|
| 90–100 | Very easy (5th grade) |
| 60–70 | Plain English (8th–9th grade) |
| 30–50 | College level |
| 0–30 | Very difficult (graduate) |

---

## Common Patterns

### Pattern: Extract and Verify

```
regex_extract → extract all URLs from text
Check count of matches against expectations
If count differs → investigate with text_diff
```

### Pattern: Diff‑Based Validation

```
Save original text
Apply transformation (edit, reformat, translate)
text_diff(original, transformed) → show what changed
Verify only expected changes appear in diff
```

### Pattern: Data → Markdown Report

```
Parse/collect data into list of dicts
markdown_table → formatted table
Embed table in report markdown
text_stats on final report → sanity check
```

### Pattern: Text Quality Check

```
text_stats on generated content
Check flesch_reading_ease — is it appropriate for the audience?
Check avg_sentence_len — too long? (>25 words = complex)
Adjust content and re‑check
```

---

## Guidelines

### Do
- Use `text_diff` after any transformation to verify changes are expected
- Anchor regex patterns with `^` and `$` when matching complete lines
- Use `max_matches` for large texts to avoid overwhelming output
- Check `text_stats` on output to catch structural issues (e.g., all text collapsed to one line)
- Use `regex_extract` with `flags=["IGNORECASE"]` when case doesn't matter

### Don't
- Don't use regex to parse nested structures (HTML, JSON, XML) — use proper parsers
- Don't trust regex patterns without testing on edge cases first
- Don't generate markdown tables with inconsistent column counts across rows
- Don't treat Flesch score as absolute — it's a rough heuristic, not a quality guarantee
- Don't `text_diff` on very large files (10k+ lines) — use `context_lines=0` or compare smaller chunks

### Regex Pattern Pitfalls
- **Greedy quantifiers**: `.*` matches too much — use `.*?` for non‑greedy
- **Dot matches newline**: Use `flags=["DOTALL"]` if you want `.` to match `\n`
- **Unescaped special chars**: Escape `.`, `*`, `+`, `?`, `[`, `]`, `(`, `)`, `{`, `}`, `|`, `^`, `$`
- **Character classes**: `\d` matches Unicode digits too — use `[0-9]` for ASCII‑only
