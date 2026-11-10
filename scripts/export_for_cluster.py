#!/usr/bin/env python3
"""
Export unannotated German and Italian articles to a compact gzipped JSONL
file for GPU annotation on the cluster.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.languages import get_active_language_codes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("export_cluster")

DEFAULT_CORPUS_DB = PROJECT_ROOT / "data" / "processed" / "didi_corpus.db"
DEFAULT_WORDS_DB = PROJECT_ROOT / "data" / "processed" / "didi_words.db"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "articles_to_annotate.jsonl.gz"


def export_articles(
    corpus_db_path: Path,
    words_db_path: Path,
    output_path: Path,
    limit: int | None = None,
) -> int:
    active_langs = set(get_active_language_codes())
    log.info("Active languages for annotation: %s", active_langs)

    # 1. Get already annotated article IDs
    annotated_ids = set()
    if words_db_path.exists():
        log.info("Reading existing word-layer IDs from %s...", words_db_path)
        with sqlite3.connect(words_db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT article_id FROM article_words")
            annotated_ids = {row[0] for row in cur.fetchall()}
        log.info("Found %d articles with existing word layer", len(annotated_ids))

    # 2. Query corpus articles in active languages
    log.info("Selecting unannotated articles from %s...", corpus_db_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with sqlite3.connect(corpus_db_path) as conn, gzip.open(output_path, "wt", encoding="utf-8") as out:
        cur = conn.cursor()
        cur.execute("SELECT id, source, language, full_text FROM articles")
        for art_id, source, lang, full_text in cur:
            if lang not in active_langs:
                continue
            if art_id in annotated_ids:
                continue
            if not full_text or len(full_text.strip()) < 10:
                continue

            record = {
                "id": art_id,
                "source": source,
                "language": lang,
                "text": full_text.strip(),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
            if limit and count >= limit:
                break

    log.info("Exported %d articles to %s (size: %.1f MB)", count, output_path, output_path.stat().st_size / (1024 * 1024))
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export articles for cluster GPU annotation")
    parser.add_argument("--corpus-db", type=Path, default=DEFAULT_CORPUS_DB)
    parser.add_argument("--words-db", type=Path, default=DEFAULT_WORDS_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    export_articles(args.corpus_db, args.words_db, args.output, args.limit)


if __name__ == "__main__":
    main()

