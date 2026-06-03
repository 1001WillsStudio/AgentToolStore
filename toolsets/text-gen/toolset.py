"""
text‑gen — Lorem ipsum, random text, and structured filler data generation.
==============================================================================

Pure‑stdlib generators for placeholder content — useful for testing layouts,
populating templates, and creating demo data without external APIs.
"""

import random

try:
    from toolstore.toolset import tool
except ImportError:
    def tool(fn):
        return fn


# ── Built‑in word lists ────────────────────────────────────────────────

_LOREM = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
    "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
    "et", "dolore", "magna", "aliqua", "ut", "enim", "ad", "minim", "veniam",
    "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi", "ut",
    "aliquip", "ex", "ea", "commodo", "consequat", "duis", "aute", "irure",
    "dolor", "in", "reprehenderit", "in", "voluptate", "velit", "esse",
    "cillum", "dolore", "eu", "fugiat", "nulla", "pariatur", "excepteur",
    "sint", "occaecat", "cupidatat", "non", "proident", "sunt", "in",
    "culpa", "qui", "officia", "deserunt", "mollit", "anim", "id", "est",
    "laborum",
]


# ── lorem_words ────────────────────────────────────────────────────────

@tool
def lorem_words(*, count: int = 50, start_with_lorem: bool = True) -> dict:
    """Generate a sequence of lorem ipsum words.

    Args:
        count:            Number of words to generate.
        start_with_lorem: If True, first two words are "Lorem ipsum".

    Returns:
        dict with "text" containing space‑separated words.
    """
    words = []
    if start_with_lorem:
        words = ["Lorem", "ipsum"]
        count = max(0, count - 2)

    for i in range(count):
        words.append(_LOREM[i % len(_LOREM)])

    return {"text": " ".join(words), "word_count": len(words)}


# ── lorem_paragraphs ───────────────────────────────────────────────────

@tool
def lorem_paragraphs(*, count: int = 3, words_per: int = 60) -> dict:
    """Generate lorem ipsum paragraphs.

    Args:
        count:     Number of paragraphs.
        words_per: Approximate words per paragraph (±20%).

    Returns:
        dict with "paragraphs" (list of strings) and "count".
    """
    paragraphs = []
    used = 0
    for _ in range(count):
        wc = max(10, words_per + random.randint(-int(words_per * 0.2), int(words_per * 0.2)))
        words = []
        for _ in range(wc):
            words.append(_LOREM[used % len(_LOREM)])
            used += 1
        paragraph = " ".join(words).capitalize() + "."
        paragraphs.append(paragraph)

    return {"paragraphs": paragraphs, "count": len(paragraphs)}


# ── generate_sentences ─────────────────────────────────────────────────

@tool
def generate_sentences(*, count: int = 5, topic: str = "") -> dict:
    """Generate random English‑like sentences (not lorem ipsum).

    Uses a built‑in word pool with basic sentence templates for more
    natural‑sounding placeholder text.

    Args:
        count: Number of sentences.
        topic: Optional topic word to sprinkle in.

    Returns:
        dict with "sentences" (list) and "count".
    """
    subjects = ["The system", "Each component", "The algorithm", "Our approach",
                "The framework", "This method", "The interface", "A developer"]
    verbs = ["processes", "analyzes", "generates", "transforms", "evaluates",
             "optimizes", "integrates", "manages", "configures", "validates"]
    objects = ["the data stream", "input parameters", "configuration files",
               "runtime metrics", "user requests", "system events", "network packets",
               "database records", "API responses", "log entries"]

    sentences = []
    for i in range(count):
        subj = random.choice(subjects)
        verb = random.choice(verbs)
        obj = random.choice(objects)
        sentence = f"{subj} {verb} {obj}"

        if topic:
            if random.random() > 0.5:
                sentence += f" for {topic}"
            else:
                sentence += f" using {topic}"

        sentence += "."
        # Capitalize
        sentence = sentence[0].upper() + sentence[1:]
        sentences.append(sentence)

    return {"sentences": sentences, "count": len(sentences)}


# ── generate_data ──────────────────────────────────────────────────────

@tool
def generate_data(*, rows: int = 10, columns: list = None) -> dict:
    """Generate random tabular data for testing.

    Args:
        rows:    Number of data rows.
        columns: List of column name strings. Defaults to
                 ["id", "name", "value", "status"] if not provided.

    Returns:
        dict with "columns" and "rows" (list of dicts).
    """
    if not columns:
        columns = ["id", "name", "value", "status"]

    statuses = ["active", "inactive", "pending", "archived"]
    names_pool = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta",
                  "eta", "theta", "iota", "kappa", "lambda", "mu"]

    data_rows = []
    for i in range(1, rows + 1):
        row = {}
        for col in columns:
            low = col.lower()
            if low == "id":
                row[col] = i
            elif low == "name":
                row[col] = random.choice(names_pool)
            elif low in ("value", "score", "amount", "price"):
                row[col] = round(random.uniform(1, 1000), 2)
            elif low == "status":
                row[col] = random.choice(statuses)
            elif low in ("email",):
                row[col] = f"user{i}@example.com"
            elif low in ("date", "created", "updated"):
                row[col] = f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
            else:
                row[col] = f"{col}_{i}"
        data_rows.append(row)

    return {"columns": columns, "rows": data_rows, "count": len(data_rows)}
