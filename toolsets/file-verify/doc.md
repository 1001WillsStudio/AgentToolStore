# file‑verify

Systematic file validation — JSON/YAML syntax checking, CSV structure verification,
cryptographic hashing, and encoding detection.

This is the code‑backed version of the **verify** skill: instead of telling an agent
"check that the JSON is valid," it gives them the tools to actually do it and a
structured methodology for reporting results.

---

## When to Use This Toolset

- Validating JSON or YAML files before parsing them
- Checking CSV data for structural integrity (consistent column counts)
- Computing file checksums for integrity verification or deduplication
- Detecting text file encoding before reading
- Any scenario where you need to systematically verify file correctness

---

## Process

```
Understand → Choose Methods → Execute → Report
```

### 1. Understand What to Verify

Start by identifying what "correctness" means for the files in question:

- **Code correctness** — syntax, imports, linting
- **Data correctness** — valid JSON/YAML, consistent CSV structure, correct types
- **Output correctness** — matches expected format, right encoding, expected size range

### 2. Choose Methods

| File type | Verification method |
|-----------|-------------------|
| `.json` | `check_json` — parse + line:col error |
| `.yaml`, `.yml` | `check_yaml` — parse + line:col error |
| `.csv`, `.tsv` | `check_csv` — structure + encoding |
| Any file | `file_hash` — checksum for integrity |
| Text file | `detect_encoding` — encoding detection |
| `.md`, `.txt` | Manual review or pattern matching |

### 3. Execute

Run verification functions systematically. For batch verification of multiple files,
iterate through them and collect results.

### 4. Report

Present results in a **structured format**:

```markdown
| File | Check | Result | Detail |
|------|-------|--------|--------|
| data.json | JSON syntax | ✅ PASS | |
| users.csv  | CSV structure | ❌ FAIL | Row 47: 5 cols, expected 4 |
| report.md  | Encoding | ⚠️ WARN | Detected Latin-1, expected UTF-8 |
```

---

## Function Reference

### `check_json`

Validate JSON syntax and return the exact location of any parse error.

**When to use:** Before parsing a JSON file — catches syntax errors with line:column precision.

**Args:**
- `filepath` (str) — Path to the JSON file

**Returns:**
- `{valid: true, size_kb}` — on success
- `{valid: false, error, line, col, size_kb}` — on failure

### `check_yaml`

Validate YAML syntax (requires PyYAML).

**When to use:** Same as `check_json` but for YAML files — configuration files, CI pipelines, etc.

**Args:**
- `filepath` (str) — Path to the YAML file

**Returns:**
- `{valid: true, documents, size_kb}` — on success (documents = number of YAML docs)
- `{valid: false, error, size_kb}` — on failure

### `check_csv`

Validate CSV structure — consistent column counts, encoding detection.

**When to use:** Before loading CSV into a database or processing pipeline.

**Args:**
- `filepath` (str) — Path to the CSV file
- `delimiter` (str, optional) — Field delimiter (default comma)

**Returns:**
- `{valid: true, columns, rows, delimiter, encoding}` — on success
- `{valid: false, error, bad_rows: [...]}` — on failure

### `file_hash`

Compute a cryptographic hash of any file.

**When to use:** Integrity checks, deduplication, verifying downloads.

**Args:**
- `filepath` (str) — Path to the file
- `algorithm` (str, optional) — `sha256` (default), `md5`, `sha1`, or `sha512`

**Returns:** `{algorithm, hash, file, size_bytes}`

### `detect_encoding`

Detect the text encoding of a file.

**When to use:** Before reading a file whose encoding is unknown — avoids `UnicodeDecodeError`.

**Args:**
- `filepath` (str) — Path to the file

**Returns:** `{encoding, confidence, method, bom}`

**Method field:** `"chardet"` (high accuracy) or `"bom"` (BOM‑only fallback if chardet not installed).

---

## Checklists

### Code File Verification

- [ ] File exists at expected path
- [ ] File is not empty (or empty‑ness is intentional)
- [ ] JSON/YAML parses without errors (`check_json` / `check_yaml`)
- [ ] Encoding is as expected (`detect_encoding`)
- [ ] Checksum matches if comparing to a reference (`file_hash`)

### Data Export Verification (CSV)

- [ ] All rows have the same number of columns (`check_csv`)
- [ ] Header row is present and columns are named
- [ ] No empty rows in the middle of data
- [ ] Column types are consistent (numeric column has no text)
- [ ] No trailing empty rows
- [ ] Encoding is UTF‑8 (or documented otherwise)

### Document Verification (Markdown, Text)

- [ ] File is readable (encoding detectable)
- [ ] Links in the document are not broken
- [ ] Code blocks are correctly fenced
- [ ] File size is within expected range

---

## Guidelines

### Do
- Verify **before** processing — catching errors early saves troubleshooting time
- Report errors with **exact locations** (file path + line + column)
- Distinguish severity: **FAIL** (breaking), **WARN** (unusual but works), **PASS** (correct)
- Suggest **specific fixes** when reporting failures — not just "invalid JSON" but what's wrong
- Check encoding before reading text files — prevents cryptic errors

### Don't
- Don't over‑verify — validate what matters for correctness, skip cosmetic checks
- Don't trust file extensions alone — verify the actual content
- Don't assume UTF‑8 encoding without checking
- Don't report without context — include file path and size in every result

### Severity Classification

| Symbol | Meaning | Example |
|--------|---------|---------|
| ✅ **PASS** | Correct | JSON parses, CSV has consistent columns |
| ⚠️ **WARN** | Usable but concerning | File has trailing whitespace, encoding is unexpected but valid |
| ❌ **FAIL** | Broken | JSON parse error, CSV column count mismatch |
