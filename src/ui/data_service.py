"""
Data Access & Transformation Service for DIDI Research Workbench.
Reads from local SQLite database (didi_corpus.db) with cached queries
and pandas transformations.
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.nlp.framing_divergence import (
    FOCUS_EVENTS,
    FocusEventManager,
    compute_dunning_keyness,
    compute_moral_divergence
)
from src.nlp.hybrid_search import HybridSearchEngine

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

# Regional Trilingual Thesaurus linking key South Tyrolean concepts across DE, IT, and Ladin
TRILINGUAL_THESAURUS: Dict[str, str] = {
    "scuola": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "scuole": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "scolastica": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "scolastico": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "schule": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "schulen": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "scola": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "scoles": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "bildung": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",
    "istruzione": "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*",

    "autonomia": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
    "autonomie": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
    "statuto": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
    "statut": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
    "competenze": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
    "competenza": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
    "zuständigkeit": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",
    "zuständigkeiten": "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*",

    "lupo": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
    "lupi": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
    "wolf": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
    "wölfe": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
    "orso": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
    "orsi": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
    "bär": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
    "bären": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",
    "großraubwild": "wolf* OR wölfe* OR lupo* OR lupi* OR bär* OR bären* OR orso* OR orsi* OR großraubwild* OR lfs* OR urs*",

    "brenner": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",
    "brennero": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",
    "transit": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",
    "lueg": "brenner* OR brennero* OR transit* OR lueg* OR autobahn* OR autostrad*",

    "koalition": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
    "coalizione": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
    "landesregierung": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
    "giunta": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
    "jonta": "koalition* OR coalizion* OR regierung* OR giunta* OR jonta* OR kompatscher*",
    "kompatscher": "kompatscher* OR svp*",
    "svp": "svp* OR volkspartei*",

    "minoranza": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
    "minoranze": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
    "minderheit": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
    "minderheiten": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
    "proporz": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",
    "sprachgruppe": "minderheit* OR minoranz* OR minorit* OR proporz* OR sprachgrupp* OR censiment*",

    "bilinguismo": "zweisprachig* OR bilingu* OR muttersprach* OR madrelingu* OR lingaz*",
    "zweisprachigkeit": "zweisprachig* OR bilingu* OR muttersprach* OR madrelingu* OR lingaz*",
    "muttersprache": "zweisprachig* OR bilingu* OR muttersprach* OR madrelingu* OR lingaz*",
    "madrelingua": "zweisprachig* OR bilingu* OR muttersprach* OR madrelingu* OR lingaz*",
}


class DataService:
    """Read-only access service for didi_corpus.db."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not self.db_path.exists():
            raise FileNotFoundError(f"Corpus database not found at {self.db_path}")
        self.last_query_expansion: Optional[str] = None
        self.hybrid_engine = HybridSearchEngine()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def build_fts_query(
        self,
        raw_query: str,
        expand_trilingual: bool = True,
        enable_prefix: bool = True
    ) -> Tuple[str, Optional[str]]:
        """
        Transform raw user input into an optimized FTS5 query.
        Applies trilingual thesaurus expansion and automated prefix matching (*).
        """
        if not raw_query or not raw_query.strip():
            return "", None

        clean_q = raw_query.strip()
        low = clean_q.lower()

        # Check trilingual concept expansion
        if expand_trilingual and low in TRILINGUAL_THESAURUS:
            return TRILINGUAL_THESAURUS[low], f"Trilingual Concept Expansion active for '{clean_q}' (covering DE, IT, LLD)"

        # If user explicitly used quotes or boolean operators, preserve verbatim
        if '"' in clean_q or ' OR ' in clean_q or ' AND ' in clean_q or ' NOT ' in clean_q:
            return clean_q, None

        # Apply prefix wildcarding on alphanumeric words (>= 3 chars)
        if enable_prefix:
            tokens = clean_q.split()
            prefixed = []
            for t in tokens:
                if re.match(r"^[A-Za-zÄÖÜäöüßéèàòùìëç]+$", t) and len(t) >= 3 and not t.endswith("*"):
                    prefixed.append(t + "*")
                else:
                    prefixed.append(t)
            return " ".join(prefixed), "Prefix wildcard search active (*)"

        return clean_q, None

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
        expand_trilingual: bool = True,
        enable_prefix: bool = True,
        use_hybrid: bool = True,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Execute faceted search over SQLite FTS5 index with title-boosted BM25 ranking.
        Supports automated prefix matching (*) and trilingual concept expansion.
        """
        has_query = bool(query and query.strip())
        params: List[Any] = []
        where_clauses: List[str] = []

        if has_query:
            clean_q, expansion_note = self.build_fts_query(
                query,
                expand_trilingual=expand_trilingual,
                enable_prefix=enable_prefix
            )
            self.last_query_expansion = expansion_note
            where_clauses.append("articles_fts MATCH ?")
            params.append(clean_q)
        else:
            self.last_query_expansion = None

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
            select_snippet = "snippet(articles_fts, 2, '<mark class=\"fts-hl\">', '</mark>', '...', 50) as snippet,"
            order_sql = "ORDER BY bm25(articles_fts, 0.0, 5.0, 1.0) ASC"
        else:
            from_sql = """
                FROM articles a
                LEFT JOIN article_nlp_metrics m ON m.article_id = a.id
            """
            select_snippet = "substr(a.full_text, 1, 350) || '...' as snippet,"
            order_sql = "ORDER BY a.publish_date DESC"

        count_query = f"SELECT count(*) as total {from_sql} {where_sql}"
        data_query = f"""
            SELECT 
                a.id, a.source, a.language, a.url, a.title, a.publish_date, a.author, a.category,
                a.word_count, a.full_text, {select_snippet}
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

            # Apply hybrid semantic expansion and fusion
            if has_query and use_hybrid and self.hybrid_engine.is_available:
                vector_candidates = self.hybrid_engine.semantic_search(query, top_k=100)
                if vector_candidates:
                    existing_ids = {r["id"] for r in rows}
                    # If BM25 returned fewer than limit matches (e.g. cross-lingual mismatch),
                    # fetch top semantic candidates that are missing
                    needed_extra = [aid for aid, sim in vector_candidates if aid not in existing_ids and sim >= 0.45][:limit]
                    if needed_extra:
                        placeholders = ",".join("?" for _ in needed_extra)
                        sql_extra = f"""
                            SELECT 
                                a.id, a.source, a.language, a.url, a.title, a.publish_date, a.author, a.category,
                                a.word_count, a.full_text, substr(a.full_text, 1, 350) || '...' as snippet,
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
                            FROM articles a
                            LEFT JOIN article_nlp_metrics m ON m.article_id = a.id
                            WHERE a.id IN ({placeholders})
                        """
                        cur.execute(sql_extra, needed_extra)
                        extra_rows = [dict(r) for r in cur.fetchall()]
                        rows.extend(extra_rows)
                        total_count = max(total_count, len(rows))

                    rows = self.hybrid_engine.fuse_rankings(rows, vector_candidates)
                    rows = rows[:limit]

                    if self.last_query_expansion:
                        self.last_query_expansion += " + 🧠 Hybrid Semantic Fusion"
                    else:
                        self.last_query_expansion = "🧠 Hybrid Semantic Fusion active (BM25 + Multilingual MiniLM)"

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
        Executed directly in SQL for instant (<20ms) aggregation across all matching articles.
        """
        agg_exprs = [f"AVG(m.{c}) AS {c}" for c in FOUNDATION_COLS + EMOTION_COLS + ["net_sentiment", "moral_density", "moral_valence"]]
        agg_exprs_str = ", ".join(agg_exprs)

        sql = f"""
            SELECT a.language, COUNT(*) as article_count, {agg_exprs_str}
            FROM articles a
            JOIN article_nlp_metrics m ON a.id = m.article_id
            WHERE 1=1
        """
        params = []
        if query:
            fts_q, _ = self.build_fts_query(query, expand_trilingual=True, enable_prefix=True)
            sql += " AND a.id IN (SELECT id FROM articles_fts WHERE articles_fts MATCH ?)"
            params.append(fts_q)
        if sources:
            placeholders = ",".join("?" * len(sources))
            sql += f" AND a.source IN ({placeholders})"
            params.extend(sources)
        if languages:
            placeholders = ",".join("?" * len(languages))
            sql += f" AND a.language IN ({placeholders})"
            params.extend(languages)
        if min_date:
            sql += " AND a.publish_date >= ?"
            params.append(min_date)
        if max_date:
            sql += " AND a.publish_date <= ?"
            params.append(max_date)

        sql += " GROUP BY a.language ORDER BY a.language"

        with self._get_connection() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        return df

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

    def get_focus_events(self) -> Dict[str, Any]:
        """Return registry of historical regional focus events."""
        return FOCUS_EVENTS

    def analyze_focus_event(
        self,
        event_date_str: str,
        window_days: int = 30,
        query: str = ""
    ) -> Dict[str, Any]:
        """Run pre/post focus event framing analysis."""
        mgr = FocusEventManager(self.db_path)
        return mgr.analyze_event_window(event_date_str, window_days=window_days, query=query)

    def get_cross_lingual_keyness(
        self,
        target_lang: str,
        ref_lang: str,
        query: str = "",
        sources: Optional[List[str]] = None,
        limit: int = 500,
        min_freq: int = 3,
        top_n: int = 20
    ) -> pd.DataFrame:
        """
        Compute Dunning G² keyness between two languages for a filtered topic.
        """
        target_articles, _ = self.search_articles(
            query=query,
            sources=sources,
            languages=[target_lang],
            limit=limit
        )
        ref_articles, _ = self.search_articles(
            query=query,
            sources=sources,
            languages=[ref_lang],
            limit=limit
        )

        texts_target = [a["full_text"] for a in target_articles]
        texts_ref = [a["full_text"] for a in ref_articles]

        return compute_dunning_keyness(texts_target, texts_ref, min_freq=min_freq, top_n=top_n)

    def compute_cross_lingual_moral_divergence(
        self,
        query: str = "",
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Calculate pairwise Jensen-Shannon Moral Divergence across DE, IT, and LLD.
        """
        radar_df = self.get_aggregated_radar_data(query=query, sources=sources)
        if radar_df.empty:
            return {}

        profiles = {}
        for _, row in radar_df.iterrows():
            lang = row["language"]
            profiles[lang] = {k: row[f"{k}_density"] for k in ["care", "fairness", "loyalty", "authority", "sanctity"]}

        results = {}
        pairs = [("de", "it"), ("de", "lld_gherd"), ("it", "lld_gherd")]
        for l1, l2 in pairs:
            if l1 in profiles and l2 in profiles:
                pair_key = f"{l1.upper()}_vs_{l2.upper()}"
                results[pair_key] = compute_moral_divergence(profiles[l1], profiles[l2])

        return results


