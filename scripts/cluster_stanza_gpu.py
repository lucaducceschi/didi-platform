#!/usr/bin/env python3
"""
GPU-accelerated batch annotation worker for DIDI Platform using Stanza.
Runs on Eurac HPC GPU nodes via Slurm.

Inputs:  articles_to_annotate.jsonl.gz (jsonlines with id, language, text)
Outputs: SQLite database (didi_words_cluster.db) with article_words table matching
         DIDI's word layer specification and exact character offsets.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import stanza
import torch

# PyTorch 2.6+ defaults weights_only=True, which breaks Stanza 1.6 checkpoint loading
# Fall back to weights_only=False if not explicitly specified.
_orig_torch_load = torch.load
def _torch_load_compat(*args, **kwargs):
    if "weights_only" not in kwargs:
        kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)
torch.load = _torch_load_compat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("stanza_gpu")


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create or connect to output SQLite word layer database with optimal settings."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA synchronous = OFF")
    cur.execute("PRAGMA cache_size = -64000")  # 64MB cache

    cur.execute("""
        CREATE TABLE IF NOT EXISTS article_words (
            article_id TEXT NOT NULL,
            token_idx INTEGER NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            form TEXT NOT NULL,
            lemma TEXT NOT NULL,
            upos TEXT NOT NULL,
            xpos TEXT,
            feats TEXT,
            ner TEXT,
            PRIMARY KEY (article_id, token_idx)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS completed_articles (
            article_id TEXT PRIMARY KEY,
            word_count INTEGER NOT NULL,
            processed_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def load_completed_ids(conn: sqlite3.Connection) -> set[str]:
    cur = conn.cursor()
    cur.execute("SELECT article_id FROM completed_articles")
    return {row[0] for row in cur.fetchall()}


def process_batch(
    nlp: stanza.Pipeline,
    batch: List[Dict[str, Any]],
) -> Tuple[List[Tuple], List[Tuple[str, int, str]]]:
    """Process a batch of articles with Stanza and extract aligned tokens."""
    word_rows = []
    completed_rows = []
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Create document objects
    texts = [item["text"] for item in batch]
    in_docs = [stanza.Document([], text=t) for t in texts]

    try:
        out_docs = nlp(in_docs)
    except Exception as e:
        log.warning("Batch processing failed (%s), retrying one by one...", e)
        out_docs = []
        for doc in in_docs:
            try:
                out_docs.append(nlp(doc))
            except Exception as item_err:
                log.error("Failed single article processing: %s", item_err)
                out_docs.append(None)

    for item, doc in zip(batch, out_docs):
        if doc is None:
            continue

        art_id = item["id"]
        full_text = item["text"]
        token_idx = 0
        article_words = []
        aligned = True

        for sent in doc.sentences:
            for token in sent.tokens:
                start_c = token.start_char
                end_c = token.end_char

                # Verify alignment against raw text
                if full_text[start_c:end_c] != token.text:
                    aligned = False
                    break

                ner_tag = token.ner or "O"

                # Multi-word tokens (MWTs) in German/Italian expand into multiple words
                for word in token.words:
                    w_form = word.text
                    w_lemma = word.lemma or word.text
                    w_upos = word.upos or "X"
                    w_xpos = word.xpos or ""
                    w_feats = word.feats or ""

                    article_words.append((
                        art_id,
                        token_idx,
                        start_c,
                        end_c,
                        w_form,
                        w_lemma,
                        w_upos,
                        w_xpos,
                        w_feats,
                        ner_tag,
                    ))
                    token_idx += 1

            if not aligned:
                break

        if aligned and article_words:
            word_rows.extend(article_words)
            completed_rows.append((art_id, len(article_words), now_str))
        else:
            log.warning("Article %s had alignment error; skipped", art_id)

    return word_rows, completed_rows


def run_annotation(
    input_path: Path,
    output_path: Path,
    model_dir: str,
    batch_size: int = 32,
) -> None:
    use_gpu = torch.cuda.is_available()
    log.info("CUDA available: %s (PyTorch %s)", use_gpu, torch.__version__)
    if use_gpu:
        log.info("GPU Device: %s (Capability: %s)", torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))

    conn = init_db(output_path)
    completed_ids = load_completed_ids(conn)
    log.info("Already completed articles: %d", len(completed_ids))

    # Read pending articles grouped by language
    articles_by_lang: Dict[str, List[Dict[str, Any]]] = {"de": [], "it": []}
    log.info("Reading input articles from %s...", input_path)
    opener = gzip.open if str(input_path).endswith(".gz") else open

    with opener(input_path, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            if item["id"] in completed_ids:
                continue
            lang = item.get("language")
            if lang in articles_by_lang:
                articles_by_lang[lang].append(item)

    total_pending = sum(len(v) for v in articles_by_lang.values())
    log.info("Pending articles to annotate: %d (de: %d, it: %d)", total_pending, len(articles_by_lang["de"]), len(articles_by_lang["it"]))

    processors = "tokenize,lemma,pos,ner,depparse"

    for lang in ("de", "it"):
        queue = articles_by_lang[lang]
        if not queue:
            continue

        log.info("=========================================")
        log.info("Initializing Stanza pipeline for '%s'...", lang)
        nlp = stanza.Pipeline(
            lang=lang,
            dir=model_dir,
            processors=processors,
            use_gpu=use_gpu,
            verbose=False,
        )
        log.info("Pipeline ready. Processing %d articles...", len(queue))

        t0 = time.time()
        words_buf = []
        completed_buf = []
        processed_lang = 0

        for i in range(0, len(queue), batch_size):
            batch = queue[i : i + batch_size]
            words, comps = process_batch(nlp, batch)
            words_buf.extend(words)
            completed_buf.extend(comps)
            processed_lang += len(batch)

            if len(words_buf) >= 50000 or (i + batch_size) >= len(queue):
                cur = conn.cursor()
                cur.executemany("INSERT OR IGNORE INTO article_words VALUES (?,?,?,?,?,?,?,?,?,?)", words_buf)
                cur.executemany("INSERT OR IGNORE INTO completed_articles VALUES (?,?,?)", completed_buf)
                conn.commit()
                words_buf.clear()
                completed_buf.clear()

            if (i // batch_size) % 10 == 0 or (i + batch_size) >= len(queue):
                elapsed = time.time() - t0
                speed = processed_lang / elapsed if elapsed > 0 else 0
                log.info(
                    "[%s] Progress: %5d / %5d (%.1f%%) | Speed: %.1f art/s | Elapsed: %.1fs",
                    lang,
                    processed_lang,
                    len(queue),
                    (processed_lang / len(queue)) * 100,
                    speed,
                    elapsed,
                )

    log.info("Creating index on article_words(article_id, start_char)...")
    cur = conn.cursor()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_article_words_start ON article_words (article_id, start_char)")
    conn.commit()

    cur.execute("SELECT COUNT(*), COUNT(DISTINCT article_id) FROM article_words")
    total_tokens, total_articles = cur.fetchone()
    conn.close()

    log.info("=== CLUSTER STAGE 2 COMPLETED SUCCESSFULLY ===")
    log.info("Total tokens stored: %d across %d articles", total_tokens, total_articles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GPU-accelerated Stanza pipeline on cluster")
    parser.add_argument("--input", type=Path, default=Path("articles_to_annotate.jsonl.gz"))
    parser.add_argument("--output", type=Path, default=Path("didi_words_cluster.db"))
    parser.add_argument("--model-dir", type=str, default="/data/users/luducceschi_eurac/stanza")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    run_annotation(args.input, args.output, args.model_dir, args.batch_size)


if __name__ == "__main__":
    main()
