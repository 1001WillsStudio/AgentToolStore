# xlsx‑toolkit

Spreadsheet creation, editing, inspection, and conversion — with code bindings
for the operations that agents previously had to write throw‑away scripts for.

---

## When to Use This Toolset

- Reading data from an existing `.xlsx` or `.xlsm` file
- Inspecting sheet structure before editing
- Creating a new spreadsheet from structured data (list of dicts → `.xlsx`)
- Converting spreadsheet data to CSV for further processing
- Editing values, formulas, or formatting in an existing workbook
- Working with multiple sheets in a single file

---

## Process

### Creating a Spreadsheet

```
Understand → Design → Build → Analyze → Finalize
```

1. **Understand** the data: what are the columns? What type of data (numbers, dates, text)?
   What will the consumer do with this spreadsheet?
2. **Design** the layout: columns, sheet names, formatting, any formulas.
   Use `xlsx_create` with clear column names and typed data.
3. **Build** the spreadsheet with `xlsx_create`. The function auto‑formats headers
   and auto‑widths columns.
4. **Analyze** with `xlsx_read` to verify the data reads back correctly.
5. **Finalize**: write to the target path and verify with `xlsx_sheets`.

### Editing a Spreadsheet

```
Open → Understand → Change → Verify
```

1. **Open** (or list sheets with `xlsx_sheets` to understand structure)
2. **Understand** dependencies: read the sheet with `xlsx_read`, check for formulas,
   merged cells, and data validation that might break
3. **Change** values carefully — the functions in this toolset handle data read/write.
   For formula editing, `openpyxl` preserves existing formulas when you modify cells.
4. **Verify** by reading back the changed cells/sheets

---

## Function Reference

### `xlsx_read`

Read an Excel sheet and return structured JSON.

**When to use:** Whenever you need to inspect or extract data from a spreadsheet.
Use this before editing so you understand the content.

**Args:**
- `filepath` (str) — Path to the `.xlsx` file
- `sheet` (str, optional) — Sheet name; defaults to the first sheet
- `max_rows` (int, optional) — Limit rows returned (0 = all)

**Returns:** `{sheet, columns, rows, count}`

**Gotcha:** For very large files (100k+ rows), use `max_rows` to avoid timeouts.
Open in chunks if you need everything.

### `xlsx_sheets`

List all sheets with row and column counts.

**When to use:** Before editing a workbook you haven't seen before.
Gives you a quick overview without reading all data.

**Args:**
- `filepath` (str) — Path to the `.xlsx` file

**Returns:** `{filename, sheets: [{name, rows, cols}]}`

### `xlsx_to_csv`

Convert a sheet to CSV text.

**When to use:** When you need to pipe spreadsheet data into another tool
that doesn't understand Excel format (e.g., command-line utilities, text processing).

**Args:**
- `filepath` (str) — Path to the `.xlsx` file
- `sheet` (str, optional) — Sheet name
- `delimiter` (str, optional) — Field delimiter (default comma)

**Returns:** `{csv, sheet, rows, columns}`

### `xlsx_create`

Create a new `.xlsx` from structured data.

**When to use:** When you need to generate a spreadsheet as output — report generation,
data exports, structured deliverables.

**Args:**
- `filepath` (str) — Where to write the new `.xlsx`
- `sheet` (str, optional) — Sheet name (default "Sheet1")
- `columns` (list) — Column header strings
- `rows` (list) — List of dicts keyed by column name, or list of lists

**Returns:** `{written, sheet, columns, rows}`

**Design tip:** Use descriptive column names. The header row will be styled
(bold white text on indigo background) for readability.

---

## Common Patterns

### Pattern 1: Inspect, Extract, Process

```
xlsx_sheets → understand structure
xlsx_read   → extract data (optionally filtered to specific sheet)
Process the JSON in your application logic
```

### Pattern 2: Data Export (CSV → XLSX)

```
Parse CSV → list of dicts
xlsx_create → formatted .xlsx output with styled headers
```

### Pattern 3: Multi‑Sheet Report

```
Call xlsx_create multiple times with different sheet names
(on the same file — openpyxl supports this)
```

---

## Formula Guidelines

When working with spreadsheets that contain formulas:

1. **Preserve formulas.** The `xlsx_read` function returns computed values (data_only=True).
   When editing with openpyxl directly, write to cells with formulas intact.
2. **Check dependencies.** Before changing a cell, check if other cells reference it.
3. **Document complex formulas.** If you're creating formulas, include a comment explaining the logic.
4. **Validate.** After editing formulas, read back the computed values to ensure correctness.
5. **Use named ranges** for complex spreadsheets to make formulas readable.

---

## Guidelines

### Do
- Always inspect with `xlsx_sheets` before editing an unfamiliar file
- Use `xlsx_read` with `max_rows` for previewing large files
- Verify data after writing — read it back to confirm
- Use descriptive column names when creating spreadsheets
- Handle empty cells explicitly (they come back as `None` in JSON)

### Don't
- Don't modify sheets with complex macros unless you understand them
- Don't assume the first row is always headers — inspect first
- Don't write to files that are open in Excel (you'll get a lock error)
- Don't use delimiters that appear in your data without proper quoting

### Edge Cases
- **Empty sheets**: `xlsx_read` returns `columns: [], rows: [], count: 0`
- **Missing files**: All functions return `{error: "File not found: ..."}`
- **Encrypted files**: Cannot be read by openpyxl in read-only mode
- **Very wide columns**: Auto-width is capped at 60 characters in `xlsx_create`
