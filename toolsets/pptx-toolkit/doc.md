# pptx‑toolkit

Create, inspect, and extract content from PowerPoint (.pptx) presentations —
slide‑level operations with code bindings for reading and generation.

---

## When to Use This Toolset

- Extracting text from slides for search or conversion
- Inspecting presentation structure (slide count, layouts, dimensions)
- Extracting speaker notes
- Creating presentations from structured slide data
- Generating pitch decks or report slides programmatically

---

## Process

### Extracting Content

```
Open → Inspect → Extract → Review
```

1. **Open** with `pptx_info` to get slide count and layouts
2. **Inspect** specific slides with `pptx_read`
3. **Extract** content — text, tables, notes
4. **Review** the extraction for completeness

### Creating a Presentation

```
Plan → Build → Format → Save
```

1. **Plan** the slide structure (title slide + content slides)
2. **Build** with `pptx_create` using structured data
3. **Format** is auto‑handled — title slide uses layout 0, content uses layout 1
4. **Save** to the target path

---

## Function Reference

### `pptx_read`

Extract all text slide‑by‑slide, including speaker notes.

**When to use:** Content extraction, slide indexing, note retrieval.

**Args:** `filepath` (str)

**Returns:** `{slides: [{index, title, body_text, notes, shape_count}], count}`

### `pptx_info`

Quick structural inspection.

**When to use:** Before editing — check layouts and dimensions.

**Args:** `filepath` (str)

**Returns:** `{slides, slide_width, slide_height, layouts, filename}`

### `pptx_create`

Create a new presentation from structured data.

**When to use:** Report generation, pitch deck creation, automated slide output.

**Args:** `filepath` (str), `title` (str), `slides_data` (list)

**Slides data format:** `[{title, bullets: [...]}, ...]` — each dict becomes a slide.

---

## Guidelines

### Do
- Use `pptx_info` first to understand the presentation structure
- Extract speaker notes with `pptx_read` — they often contain key context
- Verify output by reading back with `pptx_read`

### Don't
- Don't assume placeholder indices are consistent across templates
- Don't extract charts as text — they render as images
- Don't overwrite without confirming

### Limitations
- **Charts and media**: Text‑only extraction — charts, images not readable
- **Custom layouts**: `pptx_create` uses standard layouts 0 and 1
- **Animations**: Not preserved in programmatic creation
