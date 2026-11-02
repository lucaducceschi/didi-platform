#!/usr/bin/env python3
"""
Interactive Research Query & Quantitative NLP Profiler for DIDI Platform.
Enables mixed-methods researchers to query topics and inspect emotional/lexical framing.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "processed" / "didi_corpus.db"


def query_corpus(
    query: str,
    source: str = None,
    language: str = None,
    min_sentiment: float = None,
    max_sentiment: float = None,
    min_moral: float = None,
    limit: int = 10,
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = """
        SELECT a.id, a.source, a.language, a.title, a.publish_date, a.author, a.category, a.word_count,
               m.net_sentiment, m.ttr, m.mean_sentence_length,
               m.joy_density, m.fear_density, m.anger_density, m.trust_density,
               m.care_density, m.fairness_density, m.loyalty_density, m.authority_density, m.sanctity_density,
               m.moral_density, m.moral_valence,
               snippet(articles_fts, 1, '\033[1;33m', '\033[0m', '...', 25) as snippet
        FROM articles_fts f
        JOIN articles a ON a.id = f.id
        LEFT JOIN article_nlp_metrics m ON m.article_id = a.id
        WHERE articles_fts MATCH ?
    """
    params = [query]
    if source:
        sql += " AND a.source = ?"
        params.append(source)
    if language:
        sql += " AND a.language = ?"
        params.append(language)
    if min_sentiment is not None:
        sql += " AND m.net_sentiment >= ?"
        params.append(min_sentiment)
    if max_sentiment is not None:
        sql += " AND m.net_sentiment <= ?"
        params.append(max_sentiment)
    if min_moral is not None:
        sql += " AND m.moral_density >= ?"
        params.append(min_moral)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    cur.execute(sql, params)
    rows = cur.fetchall()

    print(f"\nFound {len(rows)} article(s) matching query: '{query}'")
    print("-" * 75)
    for i, r in enumerate(rows, 1):
        s_val = f"{r['net_sentiment']:+.2f}" if r["net_sentiment"] is not None else "N/A"
        m_val = f"{r['moral_valence']:+.2f}" if r["moral_valence"] is not None else "N/A"
        print(f"[{i}] [{r['source'].upper()} | {r['language']}] {r['title']} ({r['publish_date'][:10]})")
        print(f"    Author: {r['author']} | Category: {r['category']} | Tokens: {r['word_count']} | TTR: {r['ttr']}")
        print(f"    Valence: {s_val} | Joy: {r['joy_density']}/1k | Fear: {r['fear_density']}/1k | Anger: {r['anger_density']}/1k | Trust: {r['trust_density']}/1k")
        print(f"    Morality ({r['moral_density']}/1k, val {m_val}): Care {r['care_density']} | Fair {r['fairness_density']} | Loyal {r['loyalty_density']} | Auth {r['authority_density']} | Sanct {r['sanctity_density']}")
        print(f"    Snippet: {r['snippet']}\n")


def main():
    parser = argparse.ArgumentParser(description="Query DIDI Trilingual Corpus")
    parser.add_argument("query", help="Keyword or search phrase")
    parser.add_argument("--source", choices=["tageszeitung", "salto", "la_usc", "trail"], help="Filter by outlet")
    parser.add_argument("--lang", help="Filter by language code (de, it, lld_badia, lld_gherd, lld_fascia)")
    parser.add_argument("--min-sentiment", type=float, help="Filter by minimum sentiment (-1.0 to 1.0)")
    parser.add_argument("--max-sentiment", type=float, help="Filter by maximum sentiment (-1.0 to 1.0)")
    parser.add_argument("--min-moral", type=float, help="Filter by minimum moral token density per 1k words")
    parser.add_argument("--limit", type=int, default=5, help="Max results to display")
    args = parser.parse_args()

    query_corpus(
        query=args.query,
        source=args.source,
        language=args.lang,
        min_sentiment=args.min_sentiment,
        max_sentiment=args.max_sentiment,
        min_moral=args.min_moral,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
