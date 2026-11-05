"""
Hybrid Semantic & Lexical Search Engine for DIDI Platform.
Fuses SQLite FTS5 (BM25) with Multilingual MiniLM Vector Embeddings
using Reciprocal Rank Fusion (RRF).
"""

import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EMBEDDINGS_NPY_PATH = PROJECT_ROOT / "data" / "processed" / "embeddings.npy"
IDS_JSON_PATH = PROJECT_ROOT / "data" / "processed" / "embedding_ids.json"
SOCKET_PATH = "/tmp/didi_encoder.sock"


class HybridSearchEngine:
    """In-memory vector index and hybrid rank fusion engine."""

    def __init__(self):
        self._matrix: Optional[np.ndarray] = None
        self._id_list: Optional[List[str]] = None
        self._id_to_idx: Optional[Dict[str, int]] = None
        self._load_index()

    def _load_index(self):
        if EMBEDDINGS_NPY_PATH.exists() and IDS_JSON_PATH.exists():
            try:
                self._matrix = np.load(EMBEDDINGS_NPY_PATH).astype(np.float32)
                with open(IDS_JSON_PATH, "r", encoding="utf-8") as f:
                    self._id_list = json.load(f)
                self._id_to_idx = {aid: idx for idx, aid in enumerate(self._id_list)}
            except Exception as e:
                print(f"Warning: Failed to load vector index: {e}")
                self._matrix = None
                self._id_list = None

    @property
    def is_available(self) -> bool:
        return self._matrix is not None and self._id_list is not None

    def encode_query(self, query_text: str) -> Optional[np.ndarray]:
        """Encode user query text into a 384-dimensional vector in < 15ms via persistent local socket."""
        if not os.path.exists(SOCKET_PATH):
            return None

        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect(SOCKET_PATH)
            s.sendall(query_text.strip().encode("utf-8") + b"\n")
            chunks = []
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            s.close()

            raw_json = b"".join(chunks).decode("utf-8").strip()
            if not raw_json:
                return None
            vec_list = json.loads(raw_json)
            return np.array(vec_list, dtype=np.float32)
        except Exception as e:
            return None

    def semantic_search(self, query_text: str, top_k: int = 100) -> List[Tuple[str, float]]:
        """Compute cosine similarity against all articles in memory."""
        if not self.is_available:
            return []

        q_vec = self.encode_query(query_text)
        if q_vec is None:
            return []

        # Dot-product with normalized vectors is cosine similarity
        sims = np.dot(self._matrix, q_vec)
        # Top-K indices
        top_indices = np.argsort(sims)[::-1][:top_k]

        results = []
        for idx in top_indices:
            aid = self._id_list[idx]
            score = float(sims[idx])
            results.append((aid, score))
        return results

    def fuse_rankings(
        self,
        bm25_articles: List[Dict[str, Any]],
        vector_candidates: List[Tuple[str, float]],
        rrf_k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF) combining BM25 and Semantic Similarity.
        Score = 1 / (k + rank_bm25) + 1 / (k + rank_vec)
        """
        if not vector_candidates:
            # If semantic search unavailable, preserve BM25 ranking
            for idx, a in enumerate(bm25_articles):
                a["hybrid_score"] = round(1.0 / (idx + 1), 4)
                a["semantic_sim"] = None
            return bm25_articles

        vec_rank_map = {aid: (rank + 1, score) for rank, (aid, score) in enumerate(vector_candidates)}

        fused = []
        for rank_bm, a in enumerate(bm25_articles, start=1):
            aid = a["id"]
            if aid in vec_rank_map:
                rank_vec, sim = vec_rank_map[aid]
                rrf_score = (1.0 / (rrf_k + rank_bm)) + (1.0 / (rrf_k + rank_vec))
            else:
                sim = 0.0
                rrf_score = 1.0 / (rrf_k + rank_bm)

            a["hybrid_score"] = round(rrf_score, 5)
            a["semantic_sim"] = round(sim, 3) if sim > 0 else None
            fused.append(a)

        # Sort by hybrid RRF score descending
        fused.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return fused
