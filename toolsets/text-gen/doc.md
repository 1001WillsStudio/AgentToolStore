# text‑gen

Generate placeholder text — lorem ipsum, random sentences, and structured tabular
data. Pure‑stdlib, no external dependencies. Useful for testing layouts, populating
templates, and creating demo datasets.

---

## When to Use This Toolset

- Filling templates or mockups with placeholder text
- Generating demo data for testing pipelines
- Creating sample content for documentation
- Populating UI prototypes with realistic‑looking data
- Testing text processing tools with controlled input

---

## Process

```
Choose generator → Set parameters → Generate → Use
```

1. **Choose**: Lorem ipsum (`lorem_words`, `lorem_paragraphs`) for classical filler,
   `generate_sentences` for readable English, `generate_data` for structured tables
2. **Set** count, word count, columns, etc.
3. **Generate** — all functions return dicts ready for use
4. **Use** directly or pipe into `markdown_table` (from text‑transform) for formatted output

---

## Function Reference

### `lorem_words`

Space‑separated lorem ipsum words.

**Args:** `count` (int, default 50), `start_with_lorem` (bool, default true)

**Returns:** `{text, word_count}`

### `lorem_paragraphs`

Multiple lorem ipsum paragraphs with sentence structure.

**Args:** `count` (int, default 3), `words_per` (int, default 60)

**Returns:** `{paragraphs: [...], count}`

### `generate_sentences`

Random English‑like sentences (not lorem ipsum) — more readable.

**Args:** `count` (int, default 5), `topic` (str, optional)

**Returns:** `{sentences: [...], count}`

### `generate_data`

Random tabular data for testing — auto‑detects columns like id, name, value, status.

**Args:** `rows` (int, default 10), `columns` (list, optional)

**Returns:** `{columns, rows, count}`

**Recognized columns:** id (auto‑increment), name (random), value/score/amount (numeric),
status (active/inactive/pending/archived), email, date.

---

## Common Patterns

### Template Filling
```
lorem_paragraphs(count=2) → placeholder body text
generate_data(rows=5, columns=["id","name","value"]) → sample table
markdown_table(demo_data) → formatted output
```

### UI Prototyping
```
generate_sentences(count=8, topic="dashboard") → readable headings/descriptions
lorem_words(count=20) → short labels
```

---

## Guidelines

### Do
- Use `generate_sentences` for readable placeholder text (better for demos)
- Use `lorem_paragraphs` when classical filler is expected
- Combine with `markdown_table` for formatted demo reports

### Don't
- Don't use lorem ipsum in production content
- Don't rely on specific order — word sequences repeat cyclically
