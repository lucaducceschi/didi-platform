"""
Data Access & Transformation Service for DIDI Research Workbench.
Reads from local SQLite database (didi_corpus.db) with cached queries
and pandas transformations.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "didi_corpus.db"

EMOTION_COLS = [
    "anger_density", "anticipation_density", "disgust_density", "fear_density",
    "joy_density", "sadness_density", "surprise_density", "trust_density"
]

FOUNDATION_COLS = [
    "care_density", "fairness_density", "loyalty_density", "authority_density", "sanctity_density"
]

FOUNDATION_POLE_COLS = [
    "care_virtue_density", "care_vice_density",
    "fairness_virtue_density", "fairness_vice_density",
    "loyalty_virtue_density", "loyalty_vice_density",
    "authority_virtue_density", "authority_vice_density",
    "sanctity_virtue_density", "sanctity_vice_density"
]

LANGUAGE_LABELS = {
    "de": "German (de)",
    "it": "Italian (it)",
    "lld_gherd": "Ladin Gherdëina (lld_gherd)",
    "lld_badia": "Ladin Val Badia (lld_badia)",
    "lld_fascia": "Ladin Fascia (lld_fascia)"
}

SOURCE_LABELS = {
    "tageszeitung": "Die Neue Südtiroler Tageszeitung",
    "salto": "Salto.bz",
    "la_usc": "La Usc di Ladins",
    "trail": "RaiNews TGR TRAIL"
}


class DataService:
    """Read-only access service for didi_corpus.db."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not self.db_path.exists():
            raise FileNotFoundError(f"Corpus database not found at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_corpus_summary(self) -> Dict[str, Any]:
        """Return global counts and aggregate stats for metric cards."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    count(*) as total_articles,
                    sum(word_count) as total_words,
                    min(publish_date) as min_date,
                    max(publish_date) as max_date
                FROM articles
            """)
            totals = dict(cur.fetchone())

            cur.execute("SELECT count(*) as count FROM article_nlp_metrics")
            nlp_count = cur.fetchone()["count"]
            totals["nlp_count"] = nlp_count

            # Counts by source
            cur.execute("SELECT source, count(*) as count, sum(word_count) as words FROM articles GROUP BY source ORDER BY count DESC")
            totals["sources"] = {r["source"]: {"count": r["count"], "words": r["words"]} for r in cur.fetchall()}

            # Counts by language
            cur.execute("SELECT language, count(*) as count, sum(word_count) as words FROM articles GROUP BY language ORDER BY count DESC")
            totals["languages"] = {r["language"]: {"count": r["count"], "words": r["words"]} for r in cur.fetchall()}

            return totals

    def search_articles(
        self,
        query: str = "",
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        min_sentiment: Optional[float] = None,
        max_sentiment: Optional[float] = None,
        min_moral: Optional[float] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Execute faceted search over SQLite FTS5 index and metadata tables.
        Returns (list_of_articles, total_matching_count).
        """
        has_query = bool(query and query.strip())
        params: List[Any] = []
        where_clauses: List[str] = []

        if has_query:
            clean_q = query.strip()
            # Escape double quotes and normalize query for FTS5
            clean_q = clean_q.replace('"', '""')
            where_clauses.append("articles_fts MATCH ?")
            params.append(clean_q)

        if sources:
            placeholders = ",".join("?" for _ in sources)
            where_clauses.append(f"a.source IN ({placeholders})")
            params.extend(sources)

        if languages:
            placeholders = ",".join("?" for _ in languages)
            where_clauses.append(f"a.language IN ({placeholders})")
            params.extend(languages)

        if min_date:
            where_clauses.append("a.publish_date >= ?")
            params.append(min_date)

        if max_date:
            where_clauses.append("a.publish_date <= ?")
            params.append(max_date)

        if min_sentiment is not None:
            where_clauses.append("m.net_sentiment >= ?")
            params.append(float(min_sentiment))

        if max_sentiment is not None:
            where_clauses.append("m.net_sentiment <= ?")
            params.append(float(max_sentiment))

        if min_moral is not None and min_moral > 0:
            where_clauses.append("m.moral_density >= ?")
            params.append(float(min_moral))

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        if has_query:
            from_sql = """
                FROM articles_fts f
                JOIN articles a ON a.id = f.id
                LEFT JOIN article_nlp_metrics m ON m.article_id = a.id
            """
            select_snippet = "snippet(articles_fts, 1, '<mark class=\"fts-hl\">', '</mark>', '...', 28) as snippet,"
            order_sql = "ORDER BY rank"
        else:
            from_sql = """
                FROM articles a
                LEFT JOIN article_nlp_metrics m ON m.article_id = a.id
            """
            select_snippet = "substr(a.full_text, 1, 260) || '...' as snippet,"
            order_sql = "ORDER BY a.publish_date DESC"

        count_query = f"SELECT count(*) as total {from_sql} {where_sql}"
        data_query = f"""
            SELECT 
                a.id, a.source, a.language, a.url, a.title, a.publish_date, a.author, a.category,
                a.word_count, {select_snippet}
                m.net_sentiment, m.ttr, m.root_ttr, m.mean_sentence_length,
                m.anger_density, m.anticipation_density, m.disgust_density, m.fear_density,
                m.joy_density, m.sadness_density, m.surprise_density, m.trust_density,
                m.care_density, m.fairness_density, m.loyalty_density, m.authority_density, m.sanctity_density,
                m.care_virtue_density, m.care_vice_density,
                m.fairness_virtue_density, m.fairness_vice_density,
                m.loyalty_virtue_density, m.loyalty_vice_density,
                m.authority_virtue_density, m.authority_vice_density,
                m.sanctity_virtue_density, m.sanctity_vice_density,
                m.moral_density, m.moral_valence
            {from_sql}
            {where_sql}
            {order_sql}
            LIMIT ? OFFSET ?
        """

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(count_query, params)
            total_count = cur.fetchone()["total"]

            cur.execute(data_query, params + [limit, offset])
            rows = [dict(r) for r in cur.fetchall()]

            return rows, total_count

    def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve complete article including full text, breadcrumbs, and all metrics."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    a.id, a.source, a.language, a.url, a.title, a.publish_date, a.author, a.category,
                    a.breadcrumbs_json, a.full_text, a.word_count, a.metadata_json, a.created_at,
                    m.word_count as nlp_word_count, m.vocab_size, m.sentence_count, m.mean_sentence_length,
                    m.ttr, m.root_ttr, m.log_ttr, m.hapax_count, m.hapax_ratio,
                    m.net_sentiment, m.positive_density, m.negative_density,
                    m.anger_density, m.anticipation_density, m.disgust_density, m.fear_density,
                    m.joy_density, m.sadness_density, m.surprise_density, m.trust_density, m.emotional_density,
                    m.care_density, m.fairness_density, m.loyalty_density, m.authority_density, m.sanctity_density,
                    m.care_virtue_density, m.care_vice_density,
                    m.fairness_virtue_density, m.fairness_vice_density,
                    m.loyalty_virtue_density, m.loyalty_vice_density,
                    m.authority_virtue_density, m.authority_vice_density,
                    m.sanctity_virtue_density, m.sanctity_vice_density,
                    m.moral_density, m.moral_valence
                FROM articles a
                LEFT JOIN article_nlp_metrics m ON a.id = m.article_id
                WHERE a.id = ?
            """, (article_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("breadcrumbs_json"):
                d["breadcrumbs"] = json.loads(d["breadcrumbs_json"])
            if d.get("metadata_json"):
                d["metadata"] = json.loads(d["metadata_json"])
            return d

    def get_aggregated_radar_data(
        self,
        query: str = "",
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Compute mean Moral Foundations and Emotion densities grouped by language variety.
        Returns a DataFrame ready for Plotly Radar / Bar plotting.
        """
        rows, _ = self.search_articles(
            query=query,
            sources=sources,
            languages=languages,
            min_date=min_date,
            max_date=max_date,
            limit=2000,
            offset=0
        )
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        # Simplify language grouping into 3 high-level categories if needed (DE, IT, LLD) or specific dialects
        agg_cols = FOUNDATION_COLS + EMOTION_COLS + ["net_sentiment", "moral_density", "moral_valence"]
        grouped = df.groupby("language")[agg_cols].mean().reset_index()
        return grouped

    def get_timeline_data(
        self,
        query: str = "",
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        freq: str = "M"
    ) -> pd.DataFrame:
        """
        Compute monthly or quarterly timeseries of article volume, net sentiment, and moral density.
        """
        rows, _ = self.search_articles(
            query=query,
            sources=sources,
            languages=languages,
            limit=5000,
            offset=0
        )
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["publish_date"] = pd.to_datetime(df["publish_date"], errors="coerce", utc=True)
        df = df.dropna(subset=["publish_date"])
        df["period"] = df["publish_date"].dt.tz_localize(None).dt.to_period(freq).dt.to_timestamp()

        grouped = df.groupby(["period", "language"]).agg(
            article_count=("id", "count"),
            avg_sentiment=("net_sentiment", "mean"),
            avg_moral_density=("moral_density", "mean"),
            avg_word_count=("word_count", "mean")
        ).reset_index()

        return grouped

