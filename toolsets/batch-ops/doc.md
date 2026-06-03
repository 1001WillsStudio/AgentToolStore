# batch‑ops

Bulk file operations — rename, find‑and‑replace, aggregate stats, and batch copy.
Pure‑stdlib, safe‑by‑default (dry‑run preview before changes).

---

## When to Use This Toolset

- Renaming multiple files with regex patterns
- Finding and replacing text across many files
- Getting aggregate file statistics for a directory
- Copying files matching a glob pattern
- Any repetitive file operation best automated

---

## Process

```
Scope → Preview → Execute → Verify
```

1. **Scope**: Define the directory and pattern. Use dry‑run first!
2. **Preview**: Run with `dry_run=True` (default) to see what will change
3. **Execute**: Run with `dry_run=False` to apply changes
4. **Verify**: Check the results — run `batch_stats` to confirm

> ⚠️ **Always dry‑run first.** All destructive operations default to `dry_run=True`.

---

## Function Reference

### `batch_rename`

Rename files matching a regex pattern.

**When to use:** Normalizing filenames, adding prefixes/suffixes, date formatting.

**Args:** `directory` (str), `pattern` (str), `replacement` (str),
`dry_run` (bool, default true), `recursive` (bool, default false)

**Returns:** `{changes: [{old_name, new_name}], count, dry_run, directory}`

### `batch_find_replace`

Find‑and‑replace across text files.

**When to use:** Updating URLs, changing variable names, fixing typos across a codebase.

**Args:** `directory` (str), `pattern` (str, glob), `find_text` (str),
`replace_text` (str), `dry_run` (bool, default true), `recursive` (bool)

**Returns:** `{changes: [{file, matches}], total_files, total_matches, dry_run, directory}`

### `batch_stats`

Aggregate statistics for files in a directory.

**When to use:** Understanding project structure, finding large files, auditing.

**Args:** `directory` (str), `pattern` (str, default "*"), `recursive` (bool)

**Returns:** `{file_count, total_size_bytes, extensions, largest_file, smallest_file, directory}`

### `batch_copy`

Copy files matching a pattern to a destination.

**When to use:** Collecting files from subdirectories, backing up specific file types.

**Args:** `source_dir` (str), `dest_dir` (str), `pattern` (str, default "*"),
`recursive` (bool), `overwrite` (bool, default false)

**Returns:** `{copied: [...], count, skipped: [...], dest_dir}`

---

## Common Patterns

### Audit then Clean
```
batch_stats → understand file composition
batch_rename(dry_run=True) → preview changes
batch_rename(dry_run=False) → apply
batch_stats → verify result
```

### Find and Fix
```
batch_find_replace(dry_run=True) → see what matches
batch_find_replace(dry_run=False) → apply changes
git diff → verify changes are expected
```

---

## Guidelines

### Do
- **Always dry‑run first** — default is `dry_run=True`
- Use `batch_stats` before and after to verify changes
- Test regex patterns on a single file before batch‑renaming
- Use `text_diff` (from text‑transform) to verify find‑replace results

### Don't
- Don't batch‑rename without confirming the regex matches the right files
- Don't find‑replace in binary files — use glob patterns to restrict to text files
- Don't copy with `overwrite=True` without checking destination first
- Don't run recursive operations on root directories — scope tightly

### Safety Features
- All destructive ops default to `dry_run=True`
- `batch_rename` skips files where target name already exists
- `batch_copy` skips existing files unless `overwrite=True`
- All functions validate directory existence before operating
