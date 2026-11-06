#!/usr/bin/env python3
"""Replace only the Salto rows in the corpus DB from data/raw/salto, leaving other sources as they are."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.harmonizers import SaltoHarmonizer
from src.storage import DIDICorpusDB

PROCESSED = PROJECT_ROOT / "data" / "processed"


def main():
    db = DIDICorpusDB(PROCESSED / "didi_corpus.db")
    articles = SaltoHarmonizer().parse_directory(PROJECT_ROOT / "data" / "raw" / "salto")

    with db._get_connection() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "article_annotations" in tables:
            kept = {a.id for a in articles}
            orphaned = [
                r[0]
                for r in conn.execute(
                    "SELECT an.article_id FROM article_annotations an JOIN articles a ON a.id = an.article_id WHERE a.source = 'salto'"
                )
                if r[0] not in kept
            ]
            if orphaned:
                sys.exit(f"Aborting: annotations would be orphaned for {sorted(set(orphaned))}")
        conn.execute("DELETE FROM article_nlp_metrics WHERE article_id IN (SELECT id FROM articles WHERE source = 'salto')")
        conn.execute("DELETE FROM articles WHERE source = 'salto'")
        conn.commit()

    print(f"Inserted {db.insert_batch(articles)} Salto articles")
    print(f"Scored {db.enrich_nlp_metrics()} articles")
    print(f"Exported {db.export_to_jsonl(PROCESSED / 'didi_corpus.jsonl', include_full_text=False)} JSONL rows")


if __name__ == "__main__":
    main()
