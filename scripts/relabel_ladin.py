#!/usr/bin/env python3
"""Apply the harmonizer's Ladin variety labels to the corpus DB and rescore only the articles that change."""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.harmonizers import LaUscHarmonizer
from src.storage import DIDICorpusDB

PROCESSED = PROJECT_ROOT / "data" / "processed"
LADIN_MASTER_DB = Path(
    os.environ.get(
        "LADIN_MASTER_DB",
        str(Path.home() / "Gits" / "digi-rlf" / "text_corpus" / "scraping_ladino" / "corpus_master.db"),
    )
)


def main():
    db = DIDICorpusDB(PROCESSED / "didi_corpus.db")
    articles = LaUscHarmonizer().parse_master_db(LADIN_MASTER_DB, limit=None)

    with db._get_connection() as conn:
        stored = {
            r["id"]: r
            for r in conn.execute("SELECT id, language, full_text FROM articles WHERE source IN ('la_usc', 'trail')")
        }
        if {a.id for a in articles} != set(stored) or any(a.full_text != stored[a.id]["full_text"] for a in articles):
            sys.exit("Aborting: the master corpus no longer matches the DB; run a full harmonization instead.")

        changed = [a for a in articles if a.language != stored[a.id]["language"]]
        conn.executemany(
            "UPDATE articles SET metadata_json = ? WHERE id = ?",
            [(json.dumps(a.metadata), a.id) for a in articles],
        )
        conn.executemany("UPDATE articles SET language = ? WHERE id = ?", [(a.language, a.id) for a in changed])
        conn.executemany("DELETE FROM article_nlp_metrics WHERE article_id = ?", [(a.id,) for a in changed])
        conn.commit()

    print(f"Relabelled {len(changed)} articles")
    print(f"Scored {db.enrich_nlp_metrics()} articles")
    print(f"Exported {db.export_to_jsonl(PROCESSED / 'didi_corpus.jsonl', include_full_text=False)} JSONL rows")
    print("Next: run `make reconcile` so annotations follow any changed text.")


if __name__ == "__main__":
    main()
