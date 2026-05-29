# docx‑toolkit

Create, edit, extract, and analyze Word (.docx) documents programmatically —
with code bindings replacing the throw‑away scripts agents previously wrote.

---

## When to Use This Toolset

- Extracting text from a .docx for search, analysis, or conversion
- Inspecting document structure before editing (paragraphs, tables, images)
- Extracting tables as structured data
- Creating new Word documents from markdown‑like content
- Working with tracked changes and comments

---

## Process

### Creating a Document

```
Determine structure → Choose approach → Build → Save → Verify
```

1. **Determine**: What sections? Tables? Headings? Lists?
2. **Choose**: Simple → `docx_create`, Complex → python-docx directly
3. **Build**: Content paragraphs (strings starting with `#` become headings, `-` become bullets)
4. **Save** with `docx_create` to the target path
5. **Verify** with `docx_read` — confirm paragraph count and content

### Editing a Document

```
Open → Inspect → Change → Verify
```

1. **Open** with `docx_info` to understand structure
2. **Inspect** with `docx_read` to see content
3. **Change** values (python-docx preserves existing styles when editing)
4. **Verify** by reading back with `docx_read`

---

## Function Reference

### `docx_read`

Extract full text from a Word document.

**When to use:** Before editing — understand what's in the document.

**Args:** `filepath` (str)

**Returns:** `{text, paragraphs, sections}`

### `docx_info`

Inspect structure without extracting content.

**When to use:** Quick overview — tables count, images, author metadata.

**Args:** `filepath` (str)

**Returns:** `{paragraphs, tables, sections, styles_count, images, core_properties, filename}`

### `docx_extract_tables`

Pull tables as structured row data.

**When to use:** Extracting data from document tables for analysis.

**Args:** `filepath` (str), `table_index` (int, -1 = all)

**Returns:** `{tables: [{index, rows, columns, data}], count}`

### `docx_create`

Create a new document from structured content.

**When to use:** Report generation, document export, template filling.

**Args:** `filepath` (str), `title` (str), `content` (list of strings/dicts), `author` (str)

**Content format:**
- `"# Heading"` → h2 heading
- `"- Item"` → bullet point
- `"Plain text"` → paragraph
- `{rows, columns}` → styled table

---

## Guidelines

### Do
- Inspect with `docx_info` before editing unfamiliar documents
- Use `docx_read` to verify content after changes
- Handle tracked changes explicitly — accept/reject before extracting
- Preserve formatting when editing existing documents

### Don't
- Don't assume first paragraph is the title — check heading styles
- Don't overwrite without confirming if the file exists
- Don't strip existing styles unless explicitly asked

### Edge Cases
- **Tables in headers/footers**: Not extracted by `docx_extract_tables`
- **Embedded objects**: Charts, equations — text not extractable
- **Password-protected**: Cannot be opened by python-docx
