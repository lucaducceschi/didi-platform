#!/usr/bin/env python3
"""
Merge a cluster-generated word layer SQLite database into the canonical didi_words.db.
Uses SQLite ATTACH DATABASE for fast atomic insertion.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("merge_words")

DEFAULT_TARGET_DB = PROJECT_ROOT / "data" / "processed" / "didi_words.db"


def merge_databases(source_db_path: Path, target_db_path: Path) -> None:
    if not source_db_path.exists():
        log.error("Source database not found: %s", source_db_path)
        sys.exit(1)
    if not target_db_path.exists():
        log.error("Target database not found: %s", target_db_path)
        sys.exit(1)

    log.info("Merging tokens from %s into %s...", source_db_path, target_db_path)
    t0 = time.time()

    with sqlite3.connect(target_db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute(f"ATTACH DATABASE '{source_db_path.resolve()}' AS cluster_db")

        # Check source counts
        cur = conn.cursor()
        source_count = cur.execute("SELECT COUNT(*) FROM cluster_db.article_words").fetchone()[0]
        source_articles = cur.execute("SELECT COUNT(DISTINCT article_id) FROM cluster_db.article_words").fetchone()[0]
        log.info("Source database contains %d tokens across %d articles", source_count, source_articles)

        log.info("Inserting tokens (INSERT OR IGNORE)...")
        cur.execute("""
            INSERT OR IGNORE INTO main.article_words (
                article_id, token_idx, start_char, end_char, form, lemma, upos, xpos, feats, ner
            )
            SELECT
                article_id, token_idx, start_char, end_char, form, lemma, upos, xpos, feats, ner
            FROM cluster_db.article_words
        """)
        conn.commit()

        # Update metadata timestamp
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        conn.execute("INSERT OR REPLACE INTO word_layer_metadata VALUES ('last_cluster_merge', ?)", (now_str,))
        conn.commit()

        total_count = cur.execute("SELECT COUNT(*) FROM main.article_words").fetchone()[0]
        total_articles = cur.execute("SELECT COUNT(DISTINCT article_id) FROM main.article_words").fetchone()[0]

    log.info("Merge completed in %.2fs", time.time() - t0)
    log.info("Target database now holds %d tokens across %d articles", total_count, total_articles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge cluster word layer database into local didi_words.db")
    parser.add_argument("--from", dest="source_db", type=Path, required=True, help="Path to didi_words_cluster.db")
    parser.add_argument("--to", dest="target_db", type=Path, default=DEFAULT_TARGET_DB, help="Path to local didi_words.db")
    args = parser.parse_args()

    merge_databases(args.source_db, args.target_db)


if __name__ == "__main__":
    main()

