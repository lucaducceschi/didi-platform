#!/usr/bin/env python3
"""
Import script for KST Stanza-annotated Neue Südtiroler Tageszeitung articles.

Ingests articles into DIDI's canonical SQLite corpus (data/processed/didi_corpus.db)
and builds the token-level word layer (data/processed/didi_words.db).
"""

import argparse
import io
import json
import os
import sqlite3
import sys
import tarfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.importers.tageszeitung import (
    extract_words_from_conll,
    make_article_id,
    normalize_url,
    parse_german_date,
    stream_conll_articles,
)
from src.storage.word_layer import DEFAULT_WORDS_DB_PATH, init_words_db, insert_words_batch

DEFAULT_CORPUS_DB = REPO_ROOT / "data" / "processed" / "didi_corpus.db"
DEFAULT_ARCHIVE = Path.home() / "Data" / "KST" / "cluster" / "tageszeitung.tar.gz"
SAMPLE_ARCHIVE = Path.home() / "Data" / "KST" / "cluster" / "tageszeitung_sample.tar.gz"


def load_existing_tageszeitung(corpus_db_path: Path) -> Dict[str, Tuple[str, str]]:
    """Return map of {normalized_url: (article_id, full_text)} for existing tageszeitung articles."""
    if not corpus_db_path.exists():
        return {}

    with sqlite3.connect(corpus_db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, url, full_text FROM articles WHERE source = 'tageszeitung'"
        )
        return {normalize_url(row[1]): (row[0], row[2]) for row in cur.fetchall()}


def run_import(
    archive_path: Path,
    corpus_db_path: Path,
    words_db_path: Path,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute the full Tageszeitung import and word layer population."""
    start_time = time.time()
    print(f"=== DIDI Tageszeitung Corpus & Word Layer Ingestion ===")
    print(f"Archive:       {archive_path}")
    print(f"Corpus DB:     {corpus_db_path}")
    print(f"Words DB:      {words_db_path}")
    print(f"Limit:         {limit or 'None (all articles)'}")
    print(f"Dry run:       {dry_run}")
    print("-------------------------------------------------------")

    if not archive_path.exists():
        raise FileNotFoundError(f"Archive file not found: {archive_path}")

    # 1. Inspect existing articles
    existing_map = load_existing_tageszeitung(corpus_db_path)
    print(f"Existing Tageszeitung articles in DIDI: {len(existing_map)}")

    # 2. Extract JSON mapping from archive
    print("Loading JSON article metadata from archive...")
    json_articles: Dict[str, Dict[str, Any]] = {}
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar:
            if member.name.endswith(".json"):
                f = tar.extractfile(member)
                if f:
                    raw_list = json.load(f)
                    for item in raw_list:
                        norm_u = normalize_url(item["url"])
                        json_articles[norm_u] = item
                break

    print(f"Loaded {len(json_articles):,} articles from JSON.")

    # 3. Stream CoNLL annotations and correlate
    print("Streaming CoNLL-U annotations...")
    if not dry_run:
        words_db_path = init_words_db(words_db_path)

    stats = {
        "total_conll_articles": 0,
        "added_to_corpus": 0,
        "already_present": 0,
        "skipped_articles": 0,
        "skip_reasons": Counter(),
        "word_layer_articles": 0,
        "word_layer_skipped": 0,
        "word_layer_skip_reasons": Counter(),
        "total_words": 0,
        "by_year": Counter(),
        "by_category": Counter(),
    }

    corpus_insert_batch: List[Tuple] = []
    words_insert_batch: List[Dict[str, Any]] = []

    corpus_conn = None
    if not dry_run:
        corpus_conn = sqlite3.connect(corpus_db_path)
        corpus_conn.execute("PRAGMA journal_mode = WAL")
        corpus_conn.execute("PRAGMA synchronous = NORMAL")

    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar:
                if not member.name.endswith(".conll"):
                    continue

                f = io.BufferedReader(tar.extractfile(member))
                for raw_url, conll_lines in stream_conll_articles(f):
                    stats["total_conll_articles"] += 1
                    if limit and stats["total_conll_articles"] > limit:
                        break

                    norm_url = normalize_url(raw_url)
                    json_art = json_articles.get(norm_url)
                    if not json_art:
                        stats["skipped_articles"] += 1
                        stats["skip_reasons"]["url_not_in_json"] += 1
                        continue

                    title = json_art.get("title", "").strip()
                    content = json_art.get("content", "").strip()
                    date_str = json_art.get("date")
                    tag = json_art.get("tag") or "News"
                    comments = json_art.get("comments") or []

                    if not content:
                        stats["skipped_articles"] += 1
                        stats["skip_reasons"]["empty_content"] += 1
                        continue

                    pub_date = parse_german_date(date_str, norm_url)
                    year = pub_date.year
                    category = tag.strip() if tag else "News"

                    stats["by_year"][year] += 1
                    stats["by_category"][category] += 1

                    # Check if already present in DIDI corpus
                    is_existing = norm_url in existing_map
                    if is_existing:
                        art_id, target_full_text = existing_map[norm_url]
                        stats["already_present"] += 1
                    else:
                        art_id = make_article_id(pub_date, norm_url)
                        target_full_text = content
                        created_at = datetime.now(timezone.utc).isoformat()
                        breadcrumbs = json.dumps(["Home", category])
                        metadata = json.dumps(
                            {
                                "raw_date": date_str,
                                "raw_tag": tag,
                                "comments_count": len(comments),
                            }
                        )
                        corpus_insert_batch.append(
                            (
                                art_id,
                                "tageszeitung",
                                "de",
                                norm_url,
                                title,
                                pub_date.isoformat(),
                                "Redaktion",
                                category,
                                breadcrumbs,
                                target_full_text,
                                len(target_full_text.split()),
                                metadata,
                                created_at,
                            )
                        )
                        stats["added_to_corpus"] += 1

                    # Word layer extraction & verification
                    words, is_valid, error = extract_words_from_conll(
                        conll_lines, title, target_full_text, art_id
                    )

                    if is_valid and words:
                        words_insert_batch.extend(words)
                        stats["word_layer_articles"] += 1
                        stats["total_words"] += len(words)
                    else:
                        stats["word_layer_skipped"] += 1
                        reason_key = error.split(":")[0] if error else "empty_words"
                        stats["word_layer_skip_reasons"][reason_key] += 1

                    # Flush corpus batch
                    if not dry_run and len(corpus_insert_batch) >= 1000:
                        corpus_conn.executemany(
                            """
                            INSERT OR IGNORE INTO articles
                            (id, source, language, url, title, publish_date, author, category,
                             breadcrumbs_json, full_text, word_count, metadata_json, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            corpus_insert_batch,
                        )
                        corpus_conn.commit()
                        corpus_insert_batch = []

                    # Flush words batch
                    if not dry_run and len(words_insert_batch) >= 50000:
                        insert_words_batch(words_db_path, words_insert_batch)
                        words_insert_batch = []

                    if stats["total_conll_articles"] % 10000 == 0:
                        elapsed = time.time() - start_time
                        print(
                            f"  Processed {stats['total_conll_articles']:,} articles "
                            f"({stats['added_to_corpus']:,} added, {stats['total_words']:,} words) "
                            f"[{elapsed:.1f}s]"
                        )

                break
    finally:
        # Final flush
        if not dry_run:
            if corpus_insert_batch and corpus_conn:
                corpus_conn.executemany(
                    """
                    INSERT OR IGNORE INTO articles
                    (id, source, language, url, title, publish_date, author, category,
                     breadcrumbs_json, full_text, word_count, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    corpus_insert_batch,
                )
                corpus_conn.commit()

            if corpus_conn:
                corpus_conn.close()

            if words_insert_batch:
                insert_words_batch(
                    words_db_path,
                    words_insert_batch,
                    metadata={
                        "source": "Stanza",
                        "language": "de",
                        "model": "German (de)",
                        "processors": "tokenize,lemma,pos,ner,depparse",
                        "imported_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            else:
                # Store metadata even if batch empty
                insert_words_batch(
                    words_db_path,
                    [],
                    metadata={
                        "source": "Stanza",
                        "language": "de",
                        "model": "German (de)",
                        "processors": "tokenize,lemma,pos,ner,depparse",
                        "imported_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

    total_time = time.time() - start_time
    stats["elapsed_seconds"] = total_time

    # Print Final Ingestion Report
    print("\n=======================================================")
    print("INGESTION REPORT: TAGESZEITUNG CORPUS & WORD LAYER")
    print("=======================================================")
    print(f"Total CoNLL articles processed:  {stats['total_conll_articles']:,}")
    print(f"Articles added to corpus:        {stats['added_to_corpus']:,}")
    print(f"Articles already in DIDI:        {stats['already_present']:,} (preserved unchanged)")
    print(f"Articles skipped:                {stats['skipped_articles']:,}")
    for reason, count in stats["skip_reasons"].items():
        print(f"  - {reason}: {count:,}")
    print(f"Articles with valid Word Layer:  {stats['word_layer_articles']:,}")
    print(f"Articles skipped from Word Layer:{stats['word_layer_skipped']:,}")
    for reason, count in stats["word_layer_skip_reasons"].items():
        print(f"  - {reason}: {count:,}")
    print(f"Total word tokens stored:        {stats['total_words']:,}")
    print(f"Total execution time:            {total_time:.1f} seconds")
    print("-------------------------------------------------------")
    print("Articles by Year:")
    for yr in sorted(stats["by_year"].keys()):
        print(f"  {yr}: {stats['by_year'][yr]:,} articles")
    print("-------------------------------------------------------")
    print("Top Categories:")
    for cat, cnt in stats["by_category"].most_common(12):
        print(f"  {cat}: {cnt:,} articles")
    print("=======================================================\n")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Ingest KST Tageszeitung articles & Word Layer into DIDI.")
    parser.add_argument(
        "--archive",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help="Path to tageszeitung.tar.gz archive",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use tageszeitung_sample.tar.gz instead of full archive",
    )
    parser.add_argument(
        "--corpus-db",
        type=Path,
        default=DEFAULT_CORPUS_DB,
        help="Path to didi_corpus.db",
    )
    parser.add_argument(
        "--words-db",
        type=Path,
        default=DEFAULT_WORDS_DB_PATH,
        help="Path to didi_words.db",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of articles to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without modifying databases",
    )

    args = parser.parse_args()
    archive = SAMPLE_ARCHIVE if args.sample else args.archive

    run_import(
        archive_path=archive,
        corpus_db_path=args.corpus_db,
        words_db_path=args.words_db,
        limit=args.limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

