# pdf‑toolkit

Extract text, read metadata, list form fields, and merge PDF files.
Layout‑aware extraction that handles the messy reality of multi‑column PDFs,
encrypted files, and Unicode — so agents don't have to guess.

---

## When to Use This Toolset

- Extracting readable text from a PDF for analysis or search
- Reading PDF metadata (author, title, page count) without opening the file
- Listing fillable form fields before filling them
- Merging multiple PDFs into a single document
- Inspecting PDF structure before automated processing

---

## Decision Tree: Which Extraction Method?

```
What do you need from the PDF?

├── All readable text    → pdf_extract (layout‑aware via pdfplumber)
├── Tables from PDF      → pdf_extract + note: pdfplumber can also extract tables
├── Just metadata        → pdf_meta (fast, no page processing)
├── Form fields          → pdf_form_fields (lists names, types, values)
├── Merge PDFs           → pdf_merge (preserves order)
└── Split/extract pages  → pdf_extract with first_page/last_page params
```

---

## Process

### Extracting Text

```
Inspect → Extract → Review
```

1. **Inspect** with `pdf_meta` to check page count and encryption status
2. **Extract** with `pdf_extract` — use `first_page`/`last_page` for large docs
3. **Review** the output for formatting issues (common in scanned PDFs, right‑to‑left text, or complex tables)

### Working with Form Fields

```
Inspect → Map → Fill → Validate
```

1. **Inspect** with `pdf_form_fields` to list all field names, types, and current values
2. **Map** your data to the field names discovered in step 1
3. **Fill** the form using PyPDF2's `update_page_form_field_values`
4. **Validate** by re‑reading the fields to confirm values were set

### Merging Documents

```
Collect → Order → Merge → Verify
```

1. **Collect** all input PDF paths
2. **Order** them in the sequence you want in the output
3. **Merge** with `pdf_merge`
4. **Verify** with `pdf_meta` to check the output page count matches the sum

---

## Function Reference

### `pdf_extract`

Extract readable text using layout‑aware parsing.

**When to use:** Whenever you need text content from a PDF — search, analysis, indexing.

**Args:**
- `filepath` (str) — Path to the PDF
- `first_page` (int) — First page to extract (1‑based, default 1)
- `last_page` (int) — Last page to extract (0 = all pages)

**Returns:** `{text, pages, total, range}`

**Gotcha:** Scanned PDFs (images of text) will return empty text. You'd need OCR (not yet included).
Check `pdf_meta` for the producer — "scanner" or "Image" in the producer field is a clue.

### `pdf_meta`

Read metadata without processing page content.

**When to use:** Quick inspection before extracting, or when you only need structural info.

**Args:**
- `filepath` (str) — Path to the PDF

**Returns:** `{filename, pages, title, author, subject, creator, producer, encrypted, file_size_bytes}`

### `pdf_merge`

Merge multiple PDFs into one, preserving page order.

**When to use:** Combining chapters, appendices, or separate scans into a single document.

**Args:**
- `inputs` (list) — Ordered list of file paths to merge
- `output` (str) — Path for the merged output PDF

**Returns:** `{written, pages, sources}`

### `pdf_form_fields`

List all fillable form fields with types, current values, and options.

**When to use:** Before programmatically filling a PDF form — you need to know the field names.

**Args:**
- `filepath` (str) — Path to the PDF

**Returns:** `{has_fields, count, fields: [{name, type, value, flags, options}], filename}`

**Field type guide:**
| Type | Meaning |
|------|---------|
| `Tx` | Text field |
| `Btn` | Checkbox or radio button |
| `Ch` | Dropdown / choice |
| `Sig` | Signature field |

---

## Common Patterns

### Pattern: Extract and Analyze

```
pdf_meta     → page count, encryption status
pdf_extract  → full text
text_stats (from text-transform toolset) → readability, word count
```

### Pattern: Form Auto‑Fill

```
pdf_form_fields → list of field names and types
Map data to fields
Use PyPDF2 to fill fields programmatically
pdf_form_fields → verify values were set
```

### Pattern: Document Assembly

```
pdf_meta on each input → sanity check
pdf_merge → combine in order
pdf_meta on output   → verify page count = sum of inputs
```

---

## Guidelines

### Do
- Always check `pdf_meta` first to understand encryption and page count
- Use `first_page`/`last_page` for large documents (100+ pages)
- Verify merged output with `pdf_meta` — page count should equal sum of inputs
- Handle the case where `pdf_extract` returns empty text (scanned PDF)

### Don't
- Don't try to extract text from password‑protected PDFs (check `encrypted` in `pdf_meta`)
- Don't assume extracted text preserves exact original layout — it's best‑effort
- Don't merge PDFs with different page sizes without checking
- Don't fill forms without first inspecting field types (checkbox vs dropdown vs text)

### Limitations to Communicate
- **Scanned PDFs**: text extraction may return empty — mention this when it happens
- **Highly formatted documents**: pdfplumber does its best but may misorder text in complex layouts
- **Password protection**: encrypted PDFs must be unlocked before processing
- **Form filling**: `pdf_form_fields` lists fields; actual filling requires additional PyPDF2 calls
