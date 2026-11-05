#!/usr/bin/env python3
"""
Offline Vector Embedding Generator for DIDI Corpus.
Uses the locally cached multilingual MiniLM model:
paraphrase-multilingual-MiniLM-L12-v2

Generates:
  - `data/processed/embeddings.npy` (float16 matrix [N, 384])
  - `data/processed/embedding_ids.json` (ordered list of article IDs)
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "processed" / "didi_corpus.db"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
EMBEDDINGS_NPY_PATH = OUTPUT_DIR / "embeddings.npy"
IDS_JSON_PATH = OUTPUT_DIR / "embedding_ids.json"

MODEL_CACHE_DIR = Path.home() / ".cache" / "huggingface" / "hub" / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2" / "snapshots"


def get_model_snapshot() -> Path:
    if not MODEL_CACHE_DIR.exists():
        raise FileNotFoundError(f"Cached MiniLM model not found at {MODEL_CACHE_DIR}")
    snapshots = list(MODEL_CACHE_DIR.iterdir())
    if not snapshots:
        raise FileNotFoundError(f"No snapshot directory found in {MODEL_CACHE_DIR}")
    return snapshots[0]


def main():
    snapshot_path = get_model_snapshot()
    print(f"Loading local MiniLM model from: {snapshot_path}")

    device = torch.device("mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"Inference device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(snapshot_path)
    model = AutoModel.from_pretrained(snapshot_path).to(device)
    model.eval()

    print(f"Reading corpus articles from: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, substr(full_text, 1, 350)
        FROM articles
        ORDER BY publish_date DESC, id ASC
    """)
    rows = cur.fetchall()
    conn.close()

    total_articles = len(rows)
    print(f"Found {total_articles:,} articles to embed.")

    article_ids = [r[0] for r in rows]
    # Compose input text: title + lead context
    texts = [f"{r[1]}. {r[2] or ''}".strip() for r in rows]

    batch_size = 128
    all_embeddings = []
    t0 = time.time()

    for idx in range(0, total_articles, batch_size):
        batch_texts = texts[idx : idx + batch_size]
        inputs = tokenizer(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt"
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            # Mean pooling masked by attention
            mask = inputs["attention_mask"].unsqueeze(-1).expand(outputs.last_hidden_state.size()).float()
            sum_embeddings = torch.sum(outputs.last_hidden_state * mask, 1)
            sum_mask = torch.clamp(mask.sum(1), min=1e-9)
            mean_pooled = sum_embeddings / sum_mask
            # L2 Normalize so dot-product equals cosine similarity
            normalized = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)
            all_embeddings.append(normalized.cpu().numpy().astype(np.float16))

        if (idx // batch_size) % 10 == 0 or idx + batch_size >= total_articles:
            processed = min(idx + batch_size, total_articles)
            elapsed = time.time() - t0
            rate = processed / elapsed if elapsed > 0 else 0
            pct = (processed / total_articles) * 100
            print(f"Progress: {processed:,}/{total_articles:,} ({pct:.1f}%) | {rate:.1f} art/sec | Elapsed: {elapsed:.1f}s")

    matrix = np.vstack(all_embeddings)
    print(f"Matrix generated with shape {matrix.shape}, dtype={matrix.dtype}")

    print(f"Saving embeddings matrix to: {EMBEDDINGS_NPY_PATH}")
    np.save(EMBEDDINGS_NPY_PATH, matrix)

    print(f"Saving article IDs mapping to: {IDS_JSON_PATH}")
    with open(IDS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(article_ids, f)

    total_time = time.time() - t0
    print(f"DONE! Embedded {total_articles:,} articles in {total_time:.1f}s.")


if __name__ == "__main__":
    main()
