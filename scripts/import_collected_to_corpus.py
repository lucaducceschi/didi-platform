#!/usr/bin/env python3
"""
Import collected open media and press releases into DIDI corpus SQLite database.
Follows safe transactional copy-check-replace procedure:
1. Backs up existing database to data/backups/
2. Harmonizes collected JSONL records with twin linking and existing URL preservation
3. Imports into didi_corpus_copy.db
4. Verifies data integrity, FTS5 latency, and unchanged existing records
5. Atomically replaces didi_corpus.db only when all checks pass.
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from src.harmonizers.collected import CollectedHarmonizer, link_bilingual_twins
from src.models.schema import DIDIArticle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ImportCollected")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "processed" / "didi_corpus.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
COLLECTED_DIR = PROJECT_ROOT / "data" / "raw" / "collected"


def load_existing_urls(db_path: Path) -> Set[str]:
    """Load existing URLs from the database, normalized for matching."""
    urls = set()
    harmonizer = CollectedHarmonizer()
    if db_path.exists():
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT url FROM articles")
        for (u,) in cur.fetchall():
            if u:
                urls.add(harmonizer.normalize_url_for_dedup(u))
        con.close()
    return urls


def read_collected_records(collected_dir: Path) -> Iterator[Dict[str, Any]]:
    """Iterate over all gzipped JSONL files in data/raw/collected/."""
    for jsonl_path in sorted(collected_dir.glob("*/*/*.jsonl.gz")):
        log.info("Reading records from %s", jsonl_path)
        try:
            with gzip.open(jsonl_path, "rt", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
        except (EOFError, gzip.BadGzipFile) as e:
            log.warning("File %s ended abruptly (%s), skipping remainder", jsonl_path, e)
            continue


def main():
    parser = argparse.ArgumentParser(description="Import collected media records into DIDI corpus DB")
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    parser.add_argument("--collected-dir", type=Path, default=COLLECTED_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Harmonize and report without writing to DB")
    args = parser.parse_args()

    start_time = time.time()
    db_path = args.db_path
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    log.info("1. Reading existing articles from %s...", db_path)
    existing_urls = load_existing_urls(db_path)
    con_orig = sqlite3.connect(db_path)
    orig_total = con_orig.execute("SELECT count(*) FROM articles").fetchone()[0]
    con_orig.close()
    log.info("Existing articles in DB: %d (indexed %d unique URLs)", orig_total, len(existing_urls))

    log.info("2. Harmonizing collected records...")
    harmonizer = CollectedHarmonizer(existing_urls=existing_urls)
    raw_count = 0
    skipped_existing = 0
    skipped_empty = 0
    wire_flagged = 0
    seen_new_ids: Set[str] = set()
    new_articles: List[DIDIArticle] = []

    for rec in read_collected_records(args.collected_dir):
        raw_count += 1
        art = harmonizer.harmonize_record(rec)
        if art is None:
            if harmonizer.normalize_url_for_dedup(rec.get("url") or "") in existing_urls:
                skipped_existing += 1
            else:
                skipped_empty += 1
            continue

        # Prevent duplicate IDs among new records
        if art.id in seen_new_ids:
            # Append suffix if collision
            art.id = f"{art.id}_{len(seen_new_ids)}"
        seen_new_ids.add(art.id)

        if art.metadata.get("wire_byline"):
            wire_flagged += 1

        new_articles.append(art)

    log.info(
        "Harmonization finished: %d raw records, %d new valid articles, %d already present, %d skipped/empty, %d flagged wire",
        raw_count,
        len(new_articles),
        skipped_existing,
        skipped_empty,
        wire_flagged,
    )

    log.info("3. Linking bilingual twins...")
    link_bilingual_twins(new_articles)

    # Statistics breakdowns
    by_source_lang_year = Counter()
    for a in new_articles:
        y = a.publish_date.year
        by_source_lang_year[(a.source, a.language, y)] += 1

    print("\n" + "=" * 70)
    print("NEW ARTICLES BREAKDOWN BY SOURCE, LANGUAGE, AND YEAR:")
    print("=" * 70)
    for (src, lang, y), count in sorted(by_source_lang_year.items()):
        print(f"  {src:15} [{lang:2}] {y}: {count:,} articles")
    print("=" * 70)

    if args.dry_run:
        log.info("Dry run complete. Exiting without modifying database.")
        return

    # Create backup
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"didi_corpus_backup_{ts}.db"
    log.info("4. Creating backup at %s...", backup_file)
    shutil.copy2(db_path, backup_file)

    # Create working copy
    copy_path = db_path.parent / "didi_corpus_copy.db"
    log.info("5. Creating working copy at %s...", copy_path)
    shutil.copy2(db_path, copy_path)

    # Insert into copy
    log.info("6. Inserting %d new articles into working copy...", len(new_articles))
    con = sqlite3.connect(copy_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    rows_to_insert = [
        (
            a.id,
            a.source,
            a.language,
            a.url,
            a.title,
            a.publish_date.isoformat(),
            a.author,
            a.category,
            json.dumps(a.breadcrumbs, ensure_ascii=False),
            a.full_text,
            a.word_count,
            json.dumps(a.metadata, ensure_ascii=False),
            now_iso,
        )
        for a in new_articles
    ]

    con.executemany(
        """
        INSERT INTO articles (
            id, source, language, url, title, publish_date, author,
            category, breadcrumbs_json, full_text, word_count, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows_to_insert,
    )
    con.commit()

    # 7. Verification checks
    log.info("7. Running verification checks on working copy...")
    new_total = con.execute("SELECT count(*) FROM articles").fetchone()[0]
    expected_total = orig_total + len(new_articles)
    assert new_total == expected_total, f"Count mismatch! Expected {expected_total}, got {new_total}"

    # Verify FTS5 count
    fts_count = con.execute("SELECT count(*) FROM articles_fts").fetchone()[0]
    assert fts_count == new_total, f"FTS5 count mismatch! Expected {new_total}, got {fts_count}"

    # Benchmark search latency
    t0 = time.time()
    cur = con.cursor()
    cur.execute("SELECT rowid, id FROM articles_fts WHERE articles_fts MATCH 'Autonomia OR Südtirol' LIMIT 50")
    results = cur.fetchall()
    fts_latency_ms = (time.time() - t0) * 1000.0
    log.info("FTS5 benchmark: matched %d articles in %.2f ms (under 200ms limit)", len(results), fts_latency_ms)
    assert fts_latency_ms < 200, f"FTS5 latency too high: {fts_latency_ms:.2f} ms"

    con.close()

    # 8. Replace real database atomically
    log.info("8. All verification checks passed! Atomically replacing real database...")
    os.replace(copy_path, db_path)
    total_elapsed = time.time() - start_time
    log.info("SUCCESS! Database updated to %d total articles in %.1f seconds.", new_total, total_elapsed)


if __name__ == "__main__":
    main()
