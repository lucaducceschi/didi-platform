#!/usr/bin/env python3
"""
Repair script to restore full article text for Provinz official press releases.

The Kontent CMS API stores the main body in 'long_text' when 'normal_text' is '<p><br></p>'.
This script re-extracts the full text and updates 'articles' and 'articles_fts' in didi_corpus.db.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.collectors.provinz import (
    API_BASE,
    fetch_batch_with_retry,
    parse_item,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fix_provinz")

CORPUS_DB = PROJECT_ROOT / "data" / "processed" / "didi_corpus.db"
USER_AGENT = "DIDI-ResearchBot/1.0"
BATCH_SIZE = 100


def main() -> None:
    if not CORPUS_DB.exists():
        log.error("Corpus DB not found at %s", CORPUS_DB)
        sys.exit(1)

    conn = sqlite3.connect(CORPUS_DB)
    cur = conn.cursor()

    log.info("Loading existing provinz_news articles from %s...", CORPUS_DB)
    cur.execute("SELECT id, url, full_text, word_count FROM articles WHERE source = 'provinz_news'")
    existing: Dict[str, Tuple[str, str, int]] = {row[1]: (row[0], row[2], row[3]) for row in cur.fetchall()}
    log.info("Loaded %d existing provinz_news articles", len(existing))

    updated_count = 0
    total_checked = 0
    words_added = 0

    for lang in ("it", "de"):
        log.info("Starting text recovery for language: %s", lang)
        skip = 0
        while True:
            url = f"{API_BASE}?system.type=news&language={lang}&limit={BATCH_SIZE}&skip={skip}&order=system.last_modified[asc]"
            try:
                raw_bytes = fetch_batch_with_retry(url, USER_AGENT, lang, skip)
            except Exception as e:
                log.error("Failed to fetch batch for %s at skip %d: %s", lang, skip, e)
                break

            data = json.loads(raw_bytes.decode("utf-8"))
            items = data.get("items", [])
            if not items:
                break

            updates = []
            for item in items:
                total_checked += 1
                rec = parse_item(item, lang)
                if not rec:
                    continue

                canonical_url = rec["url"]
                if canonical_url in existing:
                    art_id, old_text, old_wc = existing[canonical_url]
                    new_text = rec["full_text"]
                    new_wc = rec["word_count"]

                    # Only update if new text is substantially longer than previous (recovered body)
                    if len(new_text) > len(old_text) + 20:
                        updates.append((new_text, new_wc, art_id))
                        words_added += (new_wc - old_wc)

            if updates:
                cur.executemany("UPDATE articles SET full_text = ?, word_count = ? WHERE id = ?", updates)
                conn.commit()
                updated_count += len(updates)
                log.info("[%s] skip=%5d: updated %d articles (total updated: %d, +%d words)", lang, skip, len(updates), updated_count, words_added)

            skip += len(items)
            pagination = data.get("pagination", {})
            next_page = pagination.get("next_page")
            if not next_page or len(items) < BATCH_SIZE:
                break

            time.sleep(0.3)

    log.info("Rebuilding FTS5 full-text index...")
    t0 = time.time()
    cur.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
    conn.commit()
    log.info("FTS5 index rebuilt in %.2fs", time.time() - t0)

    # Check updated stats
    cur.execute("SELECT COUNT(*), SUM(CASE WHEN word_count < 40 THEN 1 ELSE 0 END) FROM articles WHERE source = 'provinz_news'")
    total, short = cur.fetchone()
    conn.close()

    log.info("=== REPAIR COMPLETE ===")
    log.info("Total provinz articles: %d", total)
    log.info("Articles with restored body: %d", updated_count)
    log.info("Total words added: %d", words_added)
    log.info("Remaining articles under 40 words: %d (%.1f%%)", short, (short / total) * 100 if total else 0)


if __name__ == "__main__":
    main()
