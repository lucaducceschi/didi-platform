"""
Review and score the quote-detection validation sample (Task 6 / Stage 5).

  python scripts/validate_quotes.py review   # label rows in the terminal, resumable
  python scripts/validate_quotes.py score    # precision, boundary accuracy, miss rate

Labels for candidate_quote rows:
  c  correct: direct speech, and the span matches the quote exactly
  b  boundary: direct speech, but the span is cut short, too long or merges quotes
  n  not direct speech: scare quote, title, term, cited document
Labels for non_quote_paragraph rows:
  m  missed: the paragraph contains direct speech the detector did not find
  o  ok: no direct speech in the paragraph
Any row: s skips it, q saves and quits.
"""

from __future__ import annotations

import argparse
import csv
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CSV = ROOT / "data" / "processed" / "quotes_validation_sample.csv"
CORPUS_DB = ROOT / "data" / "processed" / "didi_corpus.db"
CONTEXT_CHARS = 200

LABELS = {
    "candidate_quote": {"c": "correct", "b": "boundary", "n": "not_speech"},
    "non_quote_paragraph": {"m": "missed", "o": "ok"},
}


def load(path: Path):
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def save(path: Path, fieldnames, rows):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def wilson(k: int, n: int, z: float = 1.96):
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def score(rows):
    """Per stratum (language/source_type) and overall counts and rates."""
    groups = defaultdict(lambda: defaultdict(int))
    for r in rows:
        label = r["label"].strip()
        if not label:
            continue
        for key in (f"{r['language']}/{r['source_type']}", "all"):
            groups[key][label] += 1

    results = {}
    for key, c in groups.items():
        speech = c["correct"] + c["boundary"]
        detected = speech + c["not_speech"]
        paragraphs = c["missed"] + c["ok"]
        results[key] = {
            "detected": detected,
            "precision": (speech, detected),          # labelled detections that are speech
            "exact_boundaries": (c["correct"], speech),  # of the true quotes, span exact
            "paragraphs": paragraphs,
            "miss_rate": (c["missed"], paragraphs),   # quote-free paragraphs hiding speech
        }
    return results


def fmt(k_n):
    k, n = k_n
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{k / n:6.1%} ({k}/{n}, 95% CI {lo:.0%}-{hi:.0%})"


def cmd_score(path: Path):
    _, rows = load(path)
    labelled = sum(1 for r in rows if r["label"].strip())
    print(f"{labelled}/{len(rows)} rows labelled in {path.name}\n")
    for key, res in sorted(score(rows).items(), key=lambda kv: (kv[0] == "all", kv[0])):
        print(f"{key}")
        print(f"  precision         {fmt(res['precision'])}")
        print(f"  exact boundaries  {fmt(res['exact_boundaries'])}")
        print(f"  miss rate         {fmt(res['miss_rate'])}")
    print("\n'all' pools the strata unweighted; it is not a corpus-wide estimate.")


def context(conn, row):
    start, end = int(row["start_char"]), int(row["end_char"])
    text = conn.execute("SELECT full_text FROM articles WHERE id = ?",
                        (row["article_id"],)).fetchone()[0]
    before = text[max(0, start - CONTEXT_CHARS):start]
    after = text[end:end + CONTEXT_CHARS]
    return f"…{before}\033[1;33m⟦{text[start:end]}⟧\033[0m{after}…"


def cmd_review(path: Path):
    fieldnames, rows = load(path)
    conn = sqlite3.connect(f"{CORPUS_DB.as_uri()}?mode=ro", uri=True)
    todo = [r for r in rows if not r["label"].strip()]
    print(f"{len(rows) - len(todo)}/{len(rows)} already labelled.")
    for i, row in enumerate(todo, start=1):
        options = LABELS[row["sample_type"]]
        question = ("Is the highlighted span direct speech?"
                    if row["sample_type"] == "candidate_quote"
                    else "Does this paragraph contain direct speech?")
        print(f"\n[{i}/{len(todo)}] #{row['sample_id']} {row['language']} "
              f"{row['source']} {row['article_id']}")
        print(context(conn, row))
        keys = " ".join(f"{k}={v}" for k, v in options.items())
        while True:
            answer = input(f"{question} {keys} s=skip q=quit > ").strip().lower()
            if answer == "q":
                save(path, fieldnames, rows)
                return
            if answer == "s" or answer in options:
                break
        if answer == "s":
            continue
        row["label"] = options[answer]
        row["notes"] = input("note (enter for none) > ").strip()
        save(path, fieldnames, rows)
    print("\nAll rows labelled. Run: python scripts/validate_quotes.py score")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["review", "score"])
    parser.add_argument("--csv", type=Path, default=SAMPLE_CSV)
    args = parser.parse_args()
    if not args.csv.exists():
        sys.exit(f"{args.csv} not found; run scripts/export_quotes_for_validation.py first.")
    cmd_review(args.csv) if args.command == "review" else cmd_score(args.csv)


if __name__ == "__main__":
    main()
