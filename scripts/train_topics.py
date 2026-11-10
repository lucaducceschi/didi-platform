"""
Train the light LDA topic models, one per active language (see src/nlp/topics.py).

  .venv/bin/python scripts/train_topics.py                 # de and it, 20 topics each
  .venv/bin/python scripts/train_topics.py --language it --topics 15

Needs scikit-learn (requirements.txt). Writes data/processed/didi_topics.db, which
stays local like the other databases.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.languages import get_active_language_codes
from src.nlp.topics import LdaParams, build_matrix, fit_lda, ranked_terms, read_article_terms, save_model

CORPUS_DB = ROOT / "data" / "processed" / "didi_corpus.db"
WORDS_DB = ROOT / "data" / "processed" / "didi_words.db"
TOPICS_DB = ROOT / "data" / "processed" / "didi_topics.db"
MIN_LEMMAS = 30  # skip very short articles (captions, stubs)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--language", action="append",
                        help="language code; repeat for several (default: all active)")
    parser.add_argument("--topics", type=int, default=20)
    parser.add_argument("--max-iter", type=int, default=20)
    args = parser.parse_args()

    languages = args.language or sorted(get_active_language_codes())
    conn = sqlite3.connect(f"{CORPUS_DB.as_uri()}?mode=ro", uri=True)
    lang_of = dict(conn.execute(
        f"SELECT id, language FROM articles WHERE language IN ({','.join('?' * len(languages))})",
        languages,
    ))
    source_of = dict(conn.execute("SELECT id, source FROM articles"))

    t0 = time.time()
    docs, terms = read_article_terms(WORDS_DB, lang_of)
    print(f"Read lemmas of {len(docs)} articles in {time.time() - t0:.0f}s", flush=True)

    params = LdaParams(n_topics=args.topics, max_iter=args.max_iter)
    for lang in languages:
        lang_docs = {a: d for a, d in docs.items() if lang_of[a] == lang}
        if not lang_docs:
            print(f"{lang}: no annotated articles, skipped")
            continue
        ids, X, vocab = build_matrix(lang_docs, terms, params, min_terms=MIN_LEMMAS)
        sources = Counter(source_of[a] for a in ids)
        params.extra = {"min_lemmas": MIN_LEMMAS, "sources": dict(sources)}
        t1 = time.time()
        doc_topic, stats = fit_lda(X, vocab, params)
        model_id = f"lda_{lang}_k{params.n_topics}"
        save_model(TOPICS_DB, model_id, lang, ids, doc_topic, stats, params)
        print(f"{model_id}: {len(ids)} articles {dict(sources)}, "
              f"{len(vocab)} terms, {time.time() - t1:.0f}s", flush=True)
        for t in range(params.n_topics):
            words = ", ".join(x["term"] for x in ranked_terms(stats, t, n=8))
            print(f"  {t + 1:2d} {stats.word_share[t]:5.1%}  {words}", flush=True)


if __name__ == "__main__":
    main()
