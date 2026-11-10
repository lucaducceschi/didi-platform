"""
Export a stratified sample of detected quotes and quote-free paragraphs for
human validation (Task 6 / Stage 5).

Strata: active language (de, it) x source type (journalism, official_press).
Per stratum: QUOTES_PER_STRATUM detected quotes (precision and boundaries) and
PARAGRAPHS_PER_STRATUM paragraphs with no detection (missed quotes). At most one
quote and one paragraph per article, so a single quote-heavy article cannot
dominate a stratum. Sampling is reproducible: article ids are sorted and then
shuffled with a seeded RNG (SQLite's RANDOM() cannot be seeded).

The CSV holds verbatim article text, so it stays local (gitignored).
Label it with:  python scripts/validate_quotes.py review
Score it with:  python scripts/validate_quotes.py score
"""

from __future__ import annotations

import csv
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.languages import get_active_language_codes
from src.nlp.quotes import RULE_VERSION, detect_direct_quotes
from src.sources import get_source_type
from src.storage.word_layer import get_article_words

CORPUS_DB = ROOT / "data" / "processed" / "didi_corpus.db"
WORDS_DB = ROOT / "data" / "processed" / "didi_words.db"
OUTPUT_CSV = ROOT / "data" / "processed" / "quotes_validation_sample.csv"

SEED = 42
QUOTES_PER_STRATUM = 50
PARAGRAPHS_PER_STRATUM = 15
MIN_PARAGRAPH_WORDS = 15

FIELDNAMES = [
    "sample_id", "sample_type", "language", "source_type", "source", "article_id",
    "start_char", "end_char", "rule_version", "text", "label", "notes",
]


def paragraphs(text: str):
    """Yield (start, end) of each paragraph separated by a blank line."""
    offset = 0
    for part in text.split("\n\n"):
        stripped = part.strip()
        if stripped:
            start = text.find(stripped, offset)
            yield start, start + len(stripped)
        offset += len(part) + 2


def sample_stratum(conn, rng, language, source_ids):
    placeholders = ",".join("?" * len(source_ids))
    ids = [r[0] for r in conn.execute(
        f"SELECT id FROM articles WHERE language = ? AND source IN ({placeholders}) "
        "AND length(full_text) > 200 ORDER BY id",
        (language, *source_ids),
    )]
    rng.shuffle(ids)

    quotes, paras = [], []
    for aid in ids:
        if len(quotes) >= QUOTES_PER_STRATUM and len(paras) >= PARAGRAPHS_PER_STRATUM:
            break
        source, text = conn.execute(
            "SELECT source, full_text FROM articles WHERE id = ?", (aid,)
        ).fetchone()
        tokens = get_article_words(WORDS_DB, aid) or None
        detected = detect_direct_quotes(text, language=language, tokens=tokens)
        base = {"language": language, "source_type": get_source_type(source),
                "source": source, "article_id": aid, "rule_version": RULE_VERSION}

        if detected and len(quotes) < QUOTES_PER_STRATUM:
            q = rng.choice(detected)
            quotes.append({**base, "sample_type": "candidate_quote",
                           "start_char": q.start_char, "end_char": q.end_char})

        if len(paras) < PARAGRAPHS_PER_STRATUM:
            free = [
                (s, e) for s, e in paragraphs(text)
                if len(text[s:e].split()) >= MIN_PARAGRAPH_WORDS
                and not any(max(s, q.start_char) < min(e, q.end_char) for q in detected)
            ]
            if free:
                s, e = rng.choice(free)
                paras.append({**base, "sample_type": "non_quote_paragraph",
                              "start_char": s, "end_char": e})

    for row in quotes + paras:
        row["text"] = " ".join(
            conn.execute("SELECT substr(full_text, ?, ?) FROM articles WHERE id = ?",
                         (row["start_char"] + 1, row["end_char"] - row["start_char"],
                          row["article_id"])).fetchone()[0].split()
        )
    return quotes, paras


def main():
    if not CORPUS_DB.exists():
        sys.exit(f"Corpus DB not found at {CORPUS_DB}")
    if OUTPUT_CSV.exists():
        with open(OUTPUT_CSV, encoding="utf-8-sig") as f:
            if any((r.get("label") or r.get("is_direct_speech") or "").strip()
                   for r in csv.DictReader(f)):
                sys.exit(f"{OUTPUT_CSV} already has labels; move it away before re-exporting.")

    rng = random.Random(SEED)
    conn = sqlite3.connect(f"{CORPUS_DB.as_uri()}?mode=ro", uri=True)
    sources = [r[0] for r in conn.execute("SELECT DISTINCT source FROM articles")]

    rows = []
    for language in sorted(get_active_language_codes()):
        for source_type in ("journalism", "official_press"):
            ids = [s for s in sources if get_source_type(s) == source_type]
            quotes, paras = sample_stratum(conn, rng, language, ids)
            print(f"{language}/{source_type}: {len(quotes)} quotes, {len(paras)} paragraphs")
            rows += quotes + paras

    rng.shuffle(rows)
    for i, row in enumerate(rows, start=1):
        row.update(sample_id=i, label="", notes="")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
