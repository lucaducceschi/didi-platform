#!/usr/bin/env python3
"""
Trilingual Corpus Harmonization & NLP Enrichment Runner for DIDI Platform.
Harmonizes Tageszeitung (DE), Salto.bz (DE/IT), and La Usc di Ladins (LLD)
into a unified SQLite FTS5 database and JSONL export with quantitative NLP metrics.
"""

import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.harmonizers import TageszeitungHarmonizer, LaUscHarmonizer, SaltoHarmonizer
from src.storage import DIDICorpusDB


def main():
    print("=" * 70)
    print("  DIDI Platform: Trilingual Corpus Harmonization & NLP Enrichment")
    print("=" * 70)

    db_path = PROJECT_ROOT / "data" / "processed" / "didi_corpus.db"
    db = DIDICorpusDB(db_path)

    start_time = time.time()

    # 1. Harmonize Tageszeitung (German)
    taz_dir = Path(os.environ.get("TAZ_RAW_DIR", str(Path.home() / "Data" / "KST" / "tagesScraping" / "zip_scraped_tageszeit")))
    if taz_dir.exists():
        print(f"\n[1/4] Ingesting Tageszeitung (DE) from: {taz_dir}")
        taz_harmonizer = TageszeitungHarmonizer()
        taz_articles = taz_harmonizer.parse_directory(taz_dir)
        inserted_taz = db.insert_batch(taz_articles)
        print(f"      -> Ingested {inserted_taz} Tageszeitung articles.")
    else:
        print(f"\n[1/4] Tageszeitung path not found: {taz_dir}")

    # 2. Harmonize Salto.bz (German & Italian)
    salto_dir = PROJECT_ROOT / "data" / "raw" / "salto"
    if salto_dir.exists():
        print(f"\n[2/4] Ingesting Salto.bz (DE / IT) from: {salto_dir}")
        salto_harmonizer = SaltoHarmonizer()
        salto_articles = salto_harmonizer.parse_directory(salto_dir)
        inserted_salto = db.insert_batch(salto_articles)
        print(f"      -> Ingested {inserted_salto} Salto.bz articles (bilingual).")
    else:
        print(f"\n[2/4] Salto raw directory not found: {salto_dir}")

    # 3. Harmonize La Usc di Ladins (Ladin Badia / Gherdëina)
    lausc_dir = Path(os.environ.get("LAUSC_RAW_DIR", str(Path.home() / "Gits" / "digi-rlf" / "text_corpus" / "scraping_ladino" / "json_backups")))
    if lausc_dir.exists():
        print(f"\n[3/4] Ingesting La Usc di Ladins (LLD) from: {lausc_dir}")
        lausc_harmonizer = LaUscHarmonizer()
        # Ingest 1,000 articles for a deep, balanced multi-thousand corpus
        lausc_articles = lausc_harmonizer.parse_directory(lausc_dir, limit=1000)
        inserted_lausc = db.insert_batch(lausc_articles)
        print(f"      -> Ingested {inserted_lausc} La Usc articles.")
    else:
        print(f"\n[3/4] La Usc path not found: {lausc_dir}")

    # 4. Quantitative NLP Metrics Enrichment (Lexical diversity & NRC Emotions)
    print(f"\n[4/4] Enriching Corpus with Quantitative NLP Metrics (Lexical & NRC Emotions)...")
    enriched_count = db.enrich_nlp_metrics()
    print(f"      -> Computed NLP profiles for {enriched_count} articles.")

    # 5. Export harmonized JSONL dataset
    jsonl_path = PROJECT_ROOT / "data" / "processed" / "didi_corpus.jsonl"
    exported_count = db.export_to_jsonl(jsonl_path)
    print(f"      -> Exported {exported_count} harmonized records to {jsonl_path.name}")

    elapsed = round(time.time() - start_time, 2)

    # 6. Corpus Statistics Summary
    stats = db.get_stats()
    print("\n" + "=" * 70)
    print(f"  Corpus Database Summary (Elapsed: {elapsed}s)")
    print("=" * 70)
    print(f"  Total Harmonized Articles:    {stats['total_articles']:,}")
    print(f"  Total Words Processed:       {stats['total_words']:,}")
    print(f"  NLP-Profiled Articles:       {stats['nlp_profiled_articles']:,}")
    print(f"  Temporal Span:               {stats['earliest_date'][:10]} to {stats['latest_date'][:10]}")
    print("\n  Distribution by Outlet / Source:")
    for src, data in stats["sources"].items():
        print(f"    - {src.ljust(18)}: {data['articles']:,} articles ({data['words']:,} words)")
    print("\n  Distribution by Language / Dialect:")
    for lang, count in stats["languages"].items():
        print(f"    - {lang.ljust(18)}: {count:,} articles")

    # 7. Verification Multi-Faceted Search Test
    print("\n" + "=" * 70)
    print("  Testing Integrated Qualitative FTS5 + Quantitative NLP Search")
    print("=" * 70)
    sample_queries = ["Autonomie", "Kultur", "Wahl", "scola"]
    for q in sample_queries:
        results = db.search_articles(q, limit=1)
        if results:
            r = results[0]
            sentiment_str = f"{r['net_sentiment']:+.2f}" if r.get('net_sentiment') is not None else "N/A"
            ttr_str = f"{r['ttr']:.3f}" if r.get('ttr') is not None else "N/A"
            print(f"  Query: '{q}' -> [{r['source'].upper()} | {r['language']}] {r['title']} ({r['publish_date'][:10]})")
            print(f"          Sentiment: {sentiment_str} | TTR: {ttr_str} | Words: {r['word_count']}")
            print(f"          Snippet: {r['snippet']}")

    print("\n" + "=" * 70)
    print("  Harmonization & NLP Profiling Complete. Ready for Workbench & RAG.")
    print("=" * 70)


if __name__ == "__main__":
    main()
