"""
Light topic modelling: one LDA model per active language, on Stanza lemmas.

This is the first, light version (decided 2026-11-10). LDA runs offline on the
word layer, so no model download and no external service. A multilingual
BERTopic model is planned later; the storage is generic (`method` column) so
both can sit side by side.

Documents are articles. Terms are lowercased lemmas of content words
(NOUN, PROPN, ADJ, VERB) from `didi_words.db`; the vocabulary is pruned by
document frequency. Results go to a local SQLite file (`didi_topics.db`,
gitignored like the other databases):

  topic_models   one row per trained model, with its parameters
  topics         per topic: share of corpus words, top terms
  article_topics topic weights per article (weights >= MIN_STORED_WEIGHT)
  model_arrays   numpy arrays: vocabulary, p(term | topic), corpus term counts,
                 words per topic, topic-to-topic Jensen-Shannon divergence

The term view follows LDAvis (Sievert & Shirley 2014): terms ranked by
relevance = lambda * log p(w|t) + (1 - lambda) * log(p(w|t) / p(w)), with each
term's estimated count in the topic shown against its corpus count, and
topics sized by their share of all words rather than by dominant articles.
"""

from __future__ import annotations

import io
import json
import sqlite3
from array import array
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

CONTENT_UPOS = ("NOUN", "PROPN", "ADJ", "VERB")
MIN_STORED_WEIGHT = 0.05
TOP_TERMS = 20
DEFAULT_LAMBDA = 0.6  # Sievert & Shirley (2014): most interpretable in their user study

SCHEMA = """
CREATE TABLE IF NOT EXISTS topic_models (
    model_id TEXT PRIMARY KEY,
    method TEXT NOT NULL,
    language TEXT NOT NULL,
    n_topics INTEGER NOT NULL,
    n_documents INTEGER NOT NULL,
    vocabulary_size INTEGER NOT NULL,
    params TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS topics (
    model_id TEXT NOT NULL,
    topic_id INTEGER NOT NULL,
    word_share REAL NOT NULL,
    top_terms TEXT NOT NULL,
    relevant_terms TEXT NOT NULL,
    PRIMARY KEY (model_id, topic_id)
);
CREATE TABLE IF NOT EXISTS article_topics (
    model_id TEXT NOT NULL,
    article_id TEXT NOT NULL,
    topic_id INTEGER NOT NULL,
    weight REAL NOT NULL,
    is_dominant INTEGER NOT NULL,
    PRIMARY KEY (model_id, article_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_article_topics_topic
    ON article_topics (model_id, topic_id, weight DESC);
CREATE TABLE IF NOT EXISTS model_arrays (
    model_id TEXT NOT NULL,
    name TEXT NOT NULL,
    data BLOB NOT NULL,
    PRIMARY KEY (model_id, name)
);
"""


@dataclass
class LdaParams:
    n_topics: int = 20
    min_df: int = 10
    max_df: float = 0.4
    max_features: int = 20000
    max_iter: int = 20
    seed: int = 42
    upos: Tuple[str, ...] = CONTENT_UPOS
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TopicStats:
    """Everything the term view needs, derived from a fitted model."""
    vocabulary: np.ndarray       # (V,) str
    phi: np.ndarray              # (K, V) p(term | topic)
    term_counts: np.ndarray      # (V,) corpus count of each term
    topic_tokens: np.ndarray     # (K,) estimated words per topic
    topic_jsd: np.ndarray        # (K, K) Jensen-Shannon divergence, bits

    @property
    def word_share(self) -> np.ndarray:
        return self.topic_tokens / self.topic_tokens.sum()

    def term_topic_counts(self) -> np.ndarray:
        """Estimated count of each term in each topic, summing to its corpus count (LDAvis)."""
        est = self.phi * self.topic_tokens[:, None]
        return est * (self.term_counts / np.maximum(est.sum(axis=0), 1e-12))[None, :]


def normalize_lemma(lemma: str) -> Optional[str]:
    """Lowercased lemma, or None for short or non-alphabetic lemmas."""
    lemma = lemma.strip().lower()
    if len(lemma) < 3 or not lemma.replace("-", "").isalpha():
        return None
    return lemma


def read_article_terms(
    words_db: Path, article_ids: Iterable[str], upos: Tuple[str, ...] = CONTENT_UPOS
) -> Tuple[Dict[str, array], List[str]]:
    """One sequential scan of the word layer: {article_id: term ids}, and the term list.

    No ORDER BY: the ordered scan goes through the index and takes far longer
    than a plain scan; token order does not matter for a bag of words.
    """
    wanted = set(article_ids)
    terms: Dict[str, int] = {}
    norm_cache: Dict[str, Optional[int]] = {}
    docs: Dict[str, array] = {}
    placeholders = ",".join("?" * len(upos))
    conn = sqlite3.connect(f"{Path(words_db).resolve().as_uri()}?mode=ro", uri=True)
    try:
        for aid, lemma in conn.execute(
            f"SELECT article_id, lemma FROM article_words WHERE upos IN ({placeholders})", upos
        ):
            if aid not in wanted:
                continue
            tid = norm_cache.get(lemma, -1)
            if tid == -1:
                norm = normalize_lemma(lemma)
                tid = None if norm is None else terms.setdefault(norm, len(terms))
                norm_cache[lemma] = tid
            if tid is not None:
                docs.setdefault(aid, array("I")).append(tid)
    finally:
        conn.close()
    return docs, list(terms)


def build_matrix(docs: Dict[str, array], terms: List[str], params: LdaParams, min_terms: int = 1,
                 stopwords: Iterable[str] = ()):
    """Document-term count matrix, pruned by stopwords and document frequency."""
    from scipy.sparse import coo_matrix

    ids = sorted(aid for aid, d in docs.items() if len(d) >= min_terms)
    rows = np.concatenate([np.full(len(docs[a]), i, dtype=np.int32) for i, a in enumerate(ids)])
    cols = np.concatenate([np.frombuffer(docs[a], dtype=np.uint32) for a in ids]).astype(np.int32)
    X = coo_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)),
                   shape=(len(ids), len(terms))).tocsr()
    X.sum_duplicates()

    df = np.bincount(X.indices, minlength=len(terms))
    stop = set(stopwords)
    allowed = np.array([term not in stop for term in terms], dtype=bool)
    keep = np.flatnonzero((df >= params.min_df) & (df <= params.max_df * len(ids)) & allowed)
    if len(keep) > params.max_features:
        freq = np.asarray(X[:, keep].sum(axis=0)).ravel()
        keep = np.sort(keep[np.argsort(-freq, kind="stable")[: params.max_features]])
    return ids, X[:, keep], np.array(terms, dtype=str)[keep]


def _jsd_matrix(phi: np.ndarray) -> np.ndarray:
    k = len(phi)
    out = np.zeros((k, k))
    logp = np.log2(np.maximum(phi, 1e-300))
    for i in range(k):
        for j in range(i + 1, k):
            m = 0.5 * (phi[i] + phi[j])
            logm = np.log2(np.maximum(m, 1e-300))
            d = 0.5 * (phi[i] @ (logp[i] - logm) + phi[j] @ (logp[j] - logm))
            out[i, j] = out[j, i] = max(0.0, float(d))
    return out


def fit_lda(X, vocabulary: np.ndarray, params: LdaParams) -> Tuple[np.ndarray, TopicStats]:
    """Fit LDA on a document-term matrix. Returns (doc_topic, stats)."""
    from sklearn.decomposition import LatentDirichletAllocation

    lda = LatentDirichletAllocation(
        n_components=params.n_topics,
        learning_method="online",
        max_iter=params.max_iter,
        random_state=params.seed,
        n_jobs=-1,
    )
    doc_topic = lda.fit_transform(X)
    phi = lda.components_ / lda.components_.sum(axis=1, keepdims=True)
    doc_len = np.asarray(X.sum(axis=1)).ravel()
    stats = TopicStats(
        vocabulary=vocabulary,
        phi=phi,
        term_counts=np.asarray(X.sum(axis=0)).ravel(),
        topic_tokens=(doc_topic * doc_len[:, None]).sum(axis=0),
        topic_jsd=_jsd_matrix(phi),
    )
    return doc_topic, stats


def timeline_arrays(doc_topic: np.ndarray, doc_len: np.ndarray, months: List[str],
                    source_types: List[str]) -> Dict[str, np.ndarray]:
    """Words per (source type, month, topic), plus words and articles per (source type, month).

    A topic's share of a period is its estimated words there over all words there,
    the same measure as its overall size, so the line and the size agree.
    """
    periods = sorted(set(months))
    types = sorted(set(source_types))
    p_idx = {p: i for i, p in enumerate(periods)}
    s_idx = {s: i for i, s in enumerate(types)}
    tokens = np.zeros((len(types), len(periods), doc_topic.shape[1]))
    words = np.zeros((len(types), len(periods)))
    articles = np.zeros((len(types), len(periods)), dtype=np.int64)
    for row, length, month, stype in zip(doc_topic, doc_len, months, source_types):
        s, p = s_idx[stype], p_idx[month]
        tokens[s, p] += row * length
        words[s, p] += length
        articles[s, p] += 1
    return {"timeline_periods": np.array(periods, dtype=str),
            "timeline_source_types": np.array(types, dtype=str),
            "timeline_tokens": tokens, "timeline_words": words, "timeline_articles": articles}


def topic_timeline(arrays: Dict[str, np.ndarray], topic_id: int, granularity: str = "year"
                   ) -> List[Dict[str, Any]]:
    """Per source type, the topic's share of words per year or month."""
    periods = arrays["timeline_periods"]
    keys = [str(p)[:4] if granularity == "year" else str(p) for p in periods]
    buckets = sorted(set(keys))
    b_idx = np.array([buckets.index(k) for k in keys])
    series = []
    for s, stype in enumerate(arrays["timeline_source_types"]):
        tok = np.bincount(b_idx, weights=arrays["timeline_tokens"][s, :, topic_id], minlength=len(buckets))
        wrd = np.bincount(b_idx, weights=arrays["timeline_words"][s], minlength=len(buckets))
        art = np.bincount(b_idx, weights=arrays["timeline_articles"][s], minlength=len(buckets))
        series.append({
            "source_type": str(stype),
            "points": [{"period": b, "share": round(float(tok[i] / wrd[i]), 5),
                        "articles": int(art[i]), "words": int(wrd[i])}
                       for i, b in enumerate(buckets) if art[i] > 0],
        })
    return series


def relevance(stats: TopicStats, topic_id: int, lam: float) -> np.ndarray:
    """LDAvis relevance of every term for one topic."""
    p_w = stats.term_counts / stats.term_counts.sum()
    log_phi = np.log(np.maximum(stats.phi[topic_id], 1e-300))
    return lam * log_phi + (1 - lam) * (log_phi - np.log(np.maximum(p_w, 1e-300)))


def ranked_terms(stats: TopicStats, topic_id: int, lam: float = DEFAULT_LAMBDA,
                 n: int = 30) -> List[Dict[str, Any]]:
    rel = relevance(stats, topic_id, lam)
    best = np.argsort(-rel, kind="stable")[:n]
    in_topic = stats.term_topic_counts()[topic_id]
    return [
        {"term": str(stats.vocabulary[i]),
         "relevance": round(float(rel[i]), 4),
         "p_term_topic": round(float(stats.phi[topic_id, i]), 6),
         "topic_count": round(float(in_topic[i]), 1),
         "corpus_count": int(stats.term_counts[i])}
        for i in best
    ]


def closest_topics(stats: TopicStats, topic_id: int, n: int = 3) -> List[Dict[str, Any]]:
    d = stats.topic_jsd[topic_id]
    order = [int(j) for j in np.argsort(d, kind="stable") if j != topic_id][:n]
    return [{"topic_id": j, "jsd": round(float(d[j]), 4)} for j in order]


def _to_blob(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr, allow_pickle=False)
    return buf.getvalue()


def save_model(topics_db: Path, model_id: str, language: str, article_ids: List[str],
               doc_topic: np.ndarray, stats: TopicStats, params: LdaParams,
               extra_arrays: Optional[Dict[str, np.ndarray]] = None) -> None:
    conn = sqlite3.connect(topics_db)
    try:
        conn.executescript(SCHEMA)
        for table in ("article_topics", "topics", "model_arrays", "topic_models"):
            conn.execute(f"DELETE FROM {table} WHERE model_id = ?", (model_id,))
        conn.execute(
            "INSERT INTO topic_models VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (model_id, "lda", language, params.n_topics, len(article_ids), len(stats.vocabulary),
             json.dumps(params.__dict__, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.executemany(
            "INSERT INTO topics VALUES (?, ?, ?, ?, ?)",
            [(model_id, t, round(float(stats.word_share[t]), 5),
              json.dumps([x["term"] for x in ranked_terms(stats, t, 1.0, TOP_TERMS)], ensure_ascii=False),
              json.dumps([x["term"] for x in ranked_terms(stats, t, DEFAULT_LAMBDA, TOP_TERMS)],
                         ensure_ascii=False))
             for t in range(params.n_topics)],
        )
        conn.executemany(
            "INSERT INTO model_arrays VALUES (?, ?, ?)",
            [(model_id, name, _to_blob(getattr(stats, name)))
             for name in ("vocabulary", "phi", "term_counts", "topic_tokens", "topic_jsd")]
            + [(model_id, name, _to_blob(arr)) for name, arr in (extra_arrays or {}).items()],
        )
        rows = []
        for aid, weights in zip(article_ids, doc_topic):
            dominant = int(weights.argmax())
            for t, w in enumerate(weights):
                if w >= MIN_STORED_WEIGHT or t == dominant:
                    rows.append((model_id, aid, t, round(float(w), 4), int(t == dominant)))
        conn.executemany("INSERT INTO article_topics VALUES (?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


# --- Reading (API) -----------------------------------------------------------

def _connect_ro(topics_db: Path) -> Optional[sqlite3.Connection]:
    if not Path(topics_db).exists():
        return None
    conn = sqlite3.connect(f"{Path(topics_db).resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def list_models(topics_db: Path, languages: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """All models with their topics: word share, dominant-article counts, top terms."""
    conn = _connect_ro(topics_db)
    if conn is None:
        return []
    try:
        allowed = set(languages) if languages is not None else None
        models = []
        for m in conn.execute("SELECT * FROM topic_models ORDER BY language, model_id"):
            if allowed is not None and m["language"] not in allowed:
                continue
            counts = dict(conn.execute(
                "SELECT topic_id, count(*) FROM article_topics "
                "WHERE model_id = ? AND is_dominant = 1 GROUP BY topic_id", (m["model_id"],)))
            topics = [
                {"topic_id": r["topic_id"], "word_share": r["word_share"],
                 "dominant_articles": counts.get(r["topic_id"], 0),
                 "top_terms": json.loads(r["top_terms"]),
                 "relevant_terms": json.loads(r["relevant_terms"])}
                for r in conn.execute("SELECT * FROM topics WHERE model_id = ? ORDER BY topic_id",
                                      (m["model_id"],))
            ]
            models.append({
                "model_id": m["model_id"], "method": m["method"], "language": m["language"],
                "n_topics": m["n_topics"], "n_documents": m["n_documents"],
                "vocabulary_size": m["vocabulary_size"], "params": json.loads(m["params"]),
                "created_at": m["created_at"], "topics": topics,
            })
        return models
    finally:
        conn.close()


@lru_cache(maxsize=8)
def _load_stats(path: str, model_id: str, mtime: float) -> Optional[TopicStats]:
    conn = _connect_ro(Path(path))
    if conn is None:
        return None
    try:
        arrays = {r["name"]: np.load(io.BytesIO(r["data"]), allow_pickle=False)
                  for r in conn.execute("SELECT name, data FROM model_arrays WHERE model_id = ?",
                                        (model_id,))}
    finally:
        conn.close()
    core = ("vocabulary", "phi", "term_counts", "topic_tokens", "topic_jsd")
    return TopicStats(**{k: arrays[k] for k in core}) if all(k in arrays for k in core) else None


@lru_cache(maxsize=8)
def _load_timeline(path: str, model_id: str, mtime: float) -> Optional[Dict[str, np.ndarray]]:
    conn = _connect_ro(Path(path))
    if conn is None:
        return None
    try:
        arrays = {r["name"]: np.load(io.BytesIO(r["data"]), allow_pickle=False)
                  for r in conn.execute("SELECT name, data FROM model_arrays "
                                        "WHERE model_id = ? AND name LIKE 'timeline_%'", (model_id,))}
    finally:
        conn.close()
    return arrays if len(arrays) == 5 else None


def load_timeline(topics_db: Path, model_id: str) -> Optional[Dict[str, np.ndarray]]:
    if not Path(topics_db).exists():
        return None
    return _load_timeline(str(topics_db), model_id, Path(topics_db).stat().st_mtime)


def load_stats(topics_db: Path, model_id: str) -> Optional[TopicStats]:
    if not Path(topics_db).exists():
        return None
    return _load_stats(str(topics_db), model_id, Path(topics_db).stat().st_mtime)


def topic_articles(topics_db: Path, model_id: str, topic_id: int,
                   min_weight: float = 0.3) -> List[Tuple[str, float]]:
    """(article_id, weight) for one topic, highest weight first."""
    conn = _connect_ro(topics_db)
    if conn is None:
        return []
    try:
        return [(r["article_id"], r["weight"]) for r in conn.execute(
            "SELECT article_id, weight FROM article_topics "
            "WHERE model_id = ? AND topic_id = ? AND weight >= ? ORDER BY weight DESC",
            (model_id, topic_id, min_weight))]
    finally:
        conn.close()


def get_model_info(topics_db: Path, model_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect_ro(topics_db)
    if conn is None:
        return None
    try:
        row = conn.execute("SELECT language, n_topics FROM topic_models WHERE model_id = ?",
                           (model_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
