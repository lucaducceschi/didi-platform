"""
Data Access & Transformation Service for DIDI Research Workbench.
Reads from local SQLite database (didi_corpus.db) with cached queries
and pandas transformations.
"""

import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.nlp.framing_divergence import (
    FOCUS_EVENTS,
    FocusEventManager,
    compute_dunning_keyness,
    compute_moral_divergence
)
from src.languages import (
    LANGUAGES,
    LANGUAGE_LABELS,
    get_active_language_codes,
    get_all_language_codes,
    get_language,
    get_language_caution,
    get_language_label,
    get_thesaurus,
    is_language_active,
)
from src.sources import SOURCE_LABELS, SOURCE_REGISTRY, SOURCE_TYPE_LABELS, get_source_type, get_sources_for_type
from src.nlp.hybrid_search import HybridSearchEngine
from src.nlp.readability import analyze_readability
from src.ui.qdpx import build_qdpx

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "didi_corpus.db"
DEFAULT_WORDS_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "didi_words.db"

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


QDPX_EXPORT_LIMIT = 1500

# Regional Trilingual Thesaurus linking key South Tyrolean concepts across DE, IT, and Ladin.
# Single source of truth is src.languages.
TRILINGUAL_THESAURUS: Dict[str, str] = get_thesaurus(active_only=False)


class DataService:
    """Access to the corpus in didi_corpus.db. Annotations live in the workbench's PostgreSQL database."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        words_db_path: Optional[Path] = None,
        read_only: bool = False,
        enable_hybrid: bool = True
    ):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.words_db_path = Path(words_db_path) if words_db_path else DEFAULT_WORDS_DB_PATH
        self.read_only = read_only
        if not self.db_path.exists():
            raise FileNotFoundError(f"Corpus database not found at {self.db_path}")
        self.last_query_expansion: Optional[str] = None
        self.hybrid_engine = HybridSearchEngine() if enable_hybrid else None

    def _get_connection(self) -> sqlite3.Connection:
        if self.read_only:
            conn = sqlite3.connect(f"{self.db_path.resolve().as_uri()}?mode=ro", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def normalize_query(self, raw_query: str) -> str:
        """Normalize curly apostrophes, quotes, and non-breaking spaces."""
        if not raw_query:
            return ""
        clean = (
            raw_query.replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
            .replace("\u00a0", " ")
            .strip()
        )
        return clean

    def build_fts_query(
        self,
        raw_query: str,
        expand_trilingual: bool = True,
        enable_prefix: bool = True,
        search_mode: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        Transform raw user input into an optimized, syntax-safe FTS5 query.
        Supports 3 explicit search modes:
        - 'exact': exact quoted phrase / term match only (no prefix, no synonyms)
        - 'word_family': transparent morphological prefix expansion within language
        - 'concept': multilingual thesaurus expansion across German, Italian, Ladin
        """
        clean_q = self.normalize_query(raw_query)
        if not clean_q:
            return "", None

        # Determine effective mode (supports backwards-compatible booleans)
        if search_mode:
            effective_mode = search_mode.lower()
        elif expand_trilingual:
            effective_mode = "concept"
        elif enable_prefix:
            effective_mode = "word_family"
        else:
            effective_mode = "exact"

        low = clean_q.lower()

        # 1. EXACT MODE
        if effective_mode == "exact":
            if clean_q.startswith('"') and clean_q.endswith('"') and len(clean_q) >= 2:
                return clean_q, "Exact quoted match active"
            return f'"{clean_q}"', f"Exact match active for '{clean_q}'"

        # 2. CONCEPT MODE: check trilingual thesaurus
        if effective_mode == "concept" and low in TRILINGUAL_THESAURUS:
            return TRILINGUAL_THESAURUS[low], f"Trilingual Concept Expansion active for '{clean_q}' (covering DE, IT, LLD)"

        # 3. WORD FAMILY MODE (or concept fallback when term not in thesaurus)
        # If user explicitly used quotes or boolean operators, preserve verbatim safely
        if '"' in clean_q or ' OR ' in clean_q or ' AND ' in clean_q or ' NOT ' in clean_q:
            return clean_q, None

        tokens = clean_q.split()
        prefixed = []
        for t in tokens:
            # Italian elisions / contractions or hyphenated compounds
            if "'" in t or "-" in t:
                prefixed.append(f'"{t}"')
            elif re.match(r"^[A-Za-zÄÖÜäöüßéèàòùìëç]+$", t) and len(t) >= 3 and not t.endswith("*"):
                prefixed.append(t + "*")
            else:
                prefixed.append(t)

        effective_q = " ".join(prefixed)
        mode_label = (
            "Word family prefix search active (*)"
            if effective_mode == "word_family"
            else f"Search active for '{clean_q}'"
        )
        return effective_q, mode_label

    def interpret_query(
        self,
        raw_query: str,
        search_mode: str = "concept",
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        total_results: int = 0,
    ) -> Dict[str, Any]:
        """
        Generate structured query interpretation metadata for researcher transparency.
        """
        clean_q = self.normalize_query(raw_query)
        effective_fts, expansion_note = self.build_fts_query(clean_q, search_mode=search_mode)

        expansion_terms = []
        low = clean_q.lower()

        if search_mode == "exact":
            expansion_terms.append({
                "term": f'"{clean_q}"',
                "language": "exact",
                "category": "exact_phrase",
            })
        elif search_mode == "concept" and low in TRILINGUAL_THESAURUS:
            # Break down individual thesaurus terms
            raw_terms = [t.strip() for t in effective_fts.split(" OR ") if t.strip()]
            for rt in raw_terms:
                cat = "thesaurus_expansion"
                lang = "cross_lingual"
                if any(x in rt for x in ["autonom", "schule", "schul", "minderheit", "wolf", "bär"]):
                    lang = "de"
                elif any(x in rt for x in ["scuola", "scolast", "minoranz", "lupo", "orso"]):
                    lang = "it"
                elif any(x in rt for x in ["scola", "cumpetënz", "lingaz", "urs"]):
                    lang = "lld"
                expansion_terms.append({
                    "term": rt,
                    "language": lang,
                    "category": cat,
                })
        else:
            tokens = clean_q.split()
            for t in tokens:
                if "'" in t or "-" in t:
                    expansion_terms.append({
                        "term": f'"{t}"',
                        "language": "exact_token",
                        "category": "compound_or_elision",
                    })
                elif len(t) >= 3 and not t.endswith("*"):
                    expansion_terms.append({
                        "term": t + "*",
                        "language": "stem",
                        "category": "prefix_wildcard",
                    })
                else:
                    expansion_terms.append({
                        "term": t,
                        "language": "verbatim",
                        "category": "literal",
                    })

        warnings = self.get_coverage_warnings(
            sources=sources,
            languages=languages,
            min_date=min_date,
            max_date=max_date,
        )

        return {
            "original_query": raw_query,
            "normalized_query": clean_q,
            "search_mode": search_mode,
            "effective_fts": effective_fts,
            "expansion_terms": expansion_terms,
            "expansion_language": "multilingual" if search_mode == "concept" else "source_language",
            "expansion_category": expansion_note,
            "warnings": warnings,
            "total_results": total_results,
            "active_filters": {
                "sources": sources or [],
                "languages": languages or [],
                "source_types": source_types or [],
                "min_date": min_date,
                "max_date": max_date,
            },
        }

    def get_coverage_warnings(
        self,
        sources: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> List[str]:
        """Generate non-blocking corpus coverage warnings for uneven periods."""
        warnings = []
        eff_sources = sources or ["tageszeitung", "provinz_news", "salto"]

        if min_date and min_date < "2021-07-01":
            if "provinz_news" in eff_sources or not sources:
                warnings.append(
                    "Official press office coverage (Provinz News) begins in July 2021; periods prior to 2021 represent journalistic media only."
                )

        if "salto" in eff_sources:
            if not min_date or min_date < "2025-01-01":
                warnings.append(
                    "Italian journalistic coverage from Salto.bz is clustered in 2026; earlier years contain sparse coverage."
                )

        if max_date and max_date > "2025-12-31":
            if "tageszeitung" in eff_sources or not sources:
                warnings.append(
                    "Die Neue Südtiroler Tageszeitung archive currently spans through December 2025."
                )

        return warnings

    def get_corpus_summary(self, active_only: bool = False) -> Dict[str, Any]:
        """Return global counts and aggregate stats for metric cards. Includes all languages by default."""
        active_codes = get_active_language_codes()
        where_sql = f"WHERE language IN ({','.join('?' for _ in active_codes)})" if active_only else ""
        params = list(active_codes) if active_only else []
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT 
                    count(*) as total_articles,
                    sum(word_count) as total_words,
                    min(publish_date) as min_date,
                    max(publish_date) as max_date
                FROM articles
                {where_sql}
            """, params)
            totals = dict(cur.fetchone())

            if active_only:
                cur.execute(f"""
                    SELECT count(*) as count
                    FROM article_nlp_metrics m
                    CROSS JOIN articles a ON a.id = m.article_id
                    WHERE a.language IN ({','.join('?' for _ in active_codes)})
                """, params)
            else:
                cur.execute("SELECT count(*) as count FROM article_nlp_metrics")
            nlp_count = cur.fetchone()["count"]
            totals["nlp_count"] = nlp_count

            # Counts by source
            cur.execute(f"SELECT source, count(*) as count, sum(word_count) as words FROM articles {where_sql} GROUP BY source ORDER BY count DESC", params)
            totals["sources"] = {r["source"]: {"count": r["count"], "words": r["words"]} for r in cur.fetchall()}

            # Counts by language
            cur.execute(f"SELECT language, count(*) as count, sum(word_count) as words FROM articles {where_sql} GROUP BY language ORDER BY count DESC", params)
            totals["languages"] = {r["language"]: {"count": r["count"], "words": r["words"]} for r in cur.fetchall()}

            # Counts by source_type (journalism vs official_press)
            type_counts: Dict[str, Dict[str, int]] = {
                "journalism": {"count": 0, "words": 0},
                "official_press": {"count": 0, "words": 0},
            }
            for src_id, stats in totals["sources"].items():
                stype = get_source_type(src_id)
                if stype in type_counts:
                    type_counts[stype]["count"] += stats["count"]
                    type_counts[stype]["words"] += stats["words"]
            totals["source_types"] = type_counts

            return totals

    def count_unconfigured_matches(
        self,
        query: str = "",
        sources: Optional[List[str]] = None,
    ) -> int:
        """Count articles matching query/sources whose language is unconfigured/deferred."""
        deferred_codes = [c for c, lang in LANGUAGES.items() if not lang.active]
        if not deferred_codes:
            return 0
        where_clauses: List[str] = [f"a.language IN ({','.join('?' for _ in deferred_codes)})"]
        params: List[Any] = list(deferred_codes)

        has_query = bool(query and query.strip())
        if has_query:
            clean_q, _ = self.build_fts_query(query)
            where_clauses.append("articles_fts MATCH ?")
            params.append(clean_q)

        if sources:
            placeholders = ",".join("?" for _ in sources)
            where_clauses.append(f"a.source IN ({placeholders})")
            params.extend(sources)

        from_sql = "articles_fts f JOIN articles a ON a.id = f.id" if has_query else "articles a"
        sql = f"SELECT count(*) as count FROM {from_sql} WHERE {' AND '.join(where_clauses)}"
        with self._get_connection() as conn:
            return conn.execute(sql, params).fetchone()["count"]

    def search_articles(
        self,
        query: str = "",
        sources: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        min_sentiment: Optional[float] = None,
        max_sentiment: Optional[float] = None,
        min_moral: Optional[float] = None,
        expand_trilingual: bool = True,
        enable_prefix: bool = True,
        search_mode: Optional[str] = None,
        use_hybrid: bool = True,
        active_only: bool = False,
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
                enable_prefix=enable_prefix,
                search_mode=search_mode,
            )
            self.last_query_expansion = expansion_note
            where_clauses.append("articles_fts MATCH ?")
            params.append(clean_q)
        else:
            self.last_query_expansion = None

        if source_types:
            type_sources = [s for s in SOURCE_REGISTRY.keys() if get_source_type(s) in source_types]
            if sources:
                effective_sources = [s for s in sources if s in type_sources]
            else:
                effective_sources = type_sources
            if not effective_sources:
                return [], 0
            placeholders = ",".join("?" for _ in effective_sources)
            where_clauses.append(f"a.source IN ({placeholders})")
            params.extend(effective_sources)
        elif sources:
            placeholders = ",".join("?" for _ in sources)
            where_clauses.append(f"a.source IN ({placeholders})")
            params.extend(sources)

        active_codes = get_active_language_codes()
        if active_only:
            if languages:
                effective_langs = [l for l in languages if l in active_codes]
                if not effective_langs:
                    return [], 0
            else:
                effective_langs = list(active_codes)
        else:
            effective_langs = languages

        if effective_langs:
            placeholders = ",".join("?" for _ in effective_langs)
            where_clauses.append(f"a.language IN ({placeholders})")
            params.extend(effective_langs)

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
        has_metric_filters = (
            min_sentiment is not None
            or max_sentiment is not None
            or (min_moral is not None and min_moral > 0)
        )

        if has_query:
            base_from = "FROM articles_fts f JOIN articles a ON a.id = f.id"
            select_snippet = "snippet(articles_fts, 2, '<mark class=\"fts-hl\">', '</mark>', '...', 50) as snippet,"
            order_sql = "ORDER BY bm25(articles_fts, 0.0, 5.0, 1.0) ASC"
        else:
            base_from = "FROM articles a"
            select_snippet = "substr(a.full_text, 1, 350) || '...' as snippet,"
            order_sql = "ORDER BY a.publish_date DESC"

        count_from = (
            f"{base_from} LEFT JOIN article_nlp_metrics m ON m.article_id = a.id"
            if has_metric_filters
            else base_from
        )
        data_from = f"{base_from} LEFT JOIN article_nlp_metrics m ON m.article_id = a.id"

        count_query = f"SELECT count(*) as total {count_from} {where_sql}"
        if not has_query and not has_metric_filters:
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
                FROM (
                    SELECT * FROM articles AS a INDEXED BY idx_articles_date
                    {where_sql}
                    ORDER BY a.publish_date DESC
                    LIMIT ? OFFSET ?
                ) a
                LEFT JOIN article_nlp_metrics m ON m.article_id = a.id
                ORDER BY a.publish_date DESC
            """
        else:
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
                {data_from}
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
            if has_query and use_hybrid and self.hybrid_engine and self.hybrid_engine.is_available:
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

            for r in rows:
                r["source_type"] = get_source_type(r["source"])
            return rows, total_count

    def compile_query_regex(self, interp: Dict[str, Any]) -> Optional[re.Pattern]:
        """Compile regex pattern matching the query terms according to search mode."""
        clean = interp.get("normalized_query", "").strip()
        mode = interp.get("search_mode", "word_family")
        terms = interp.get("expansion_terms", [])
        if mode == "exact":
            return re.compile(re.escape(clean), re.IGNORECASE) if clean else None

        patterns = []
        for item in terms:
            t = item["term"].strip().strip('"')
            if not t:
                continue
            if t.endswith("*"):
                stem = t[:-1]
                patterns.append(r"\b" + re.escape(stem) + r"\w*")
            else:
                patterns.append(r"\b" + re.escape(t) + r"\b")

        if not patterns and clean:
            tokens = clean.split()
            for tok in tokens:
                if len(tok) >= 3:
                    patterns.append(r"\b" + re.escape(tok) + r"\w*")
                else:
                    patterns.append(r"\b" + re.escape(tok) + r"\b")

        if not patterns:
            return None
        return re.compile(r"(?:" + "|".join(patterns) + r")", re.IGNORECASE)

    def get_concordance(
        self,
        query: str,
        search_mode: str = "word_family",
        sources: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        window_size: int = 50,
        page: int = 1,
        page_size: int = 50,
        active_only: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract KWIC (Key Word In Context) concordance lines with exact character offsets.
        Enforces coordinate system: document ID + [start_char, end_char].
        """
        if not query or not query.strip():
            return {
                "total_lines": 0,
                "total_articles": 0,
                "page": page,
                "page_size": page_size,
                "items": [],
            }

        interp = self.interpret_query(
            raw_query=query,
            search_mode=search_mode,
            sources=sources,
            languages=languages,
            source_types=source_types,
            min_date=min_date,
            max_date=max_date,
        )
        rx = self.compile_query_regex(interp)
        if not rx:
            return {
                "total_lines": 0,
                "total_articles": 0,
                "page": page,
                "page_size": page_size,
                "items": [],
            }

        target_skip = (page - 1) * page_size
        needed_lines = target_skip + page_size

        article_batch_size = 50
        article_offset = 0
        all_lines: List[Dict[str, Any]] = []
        total_matching_articles = 0
        total_occurrences = 0

        while len(all_lines) < needed_lines:
            articles, batch_total = self.search_articles(
                query=query,
                search_mode=search_mode,
                sources=sources,
                source_types=source_types,
                languages=languages,
                min_date=min_date,
                max_date=max_date,
                use_hybrid=False,
                active_only=active_only,
                limit=article_batch_size,
                offset=article_offset,
            )
            total_matching_articles = batch_total
            if not articles:
                break

            for a in articles:
                text = a.get("full_text") or ""
                for m in rx.finditer(text):
                    total_occurrences += 1
                    s, e = m.span()
                    left = text[max(0, s - window_size):s].replace("\n", " ").strip()
                    kw = text[s:e]
                    right = text[e:min(len(text), e + window_size)].replace("\n", " ").strip()
                    all_lines.append({
                        "article_id": a["id"],
                        "title": a["title"],
                        "source": a["source"],
                        "source_label": SOURCE_LABELS.get(a["source"], a["source"]),
                        "source_type": get_source_type(a["source"]),
                        "language": a["language"],
                        "language_label": LANGUAGE_LABELS.get(a["language"], a["language"]),
                        "publish_date": a["publish_date"],
                        "start_char": s,
                        "end_char": e,
                        "left_context": left,
                        "keyword": kw,
                        "right_context": right,
                    })

            article_offset += len(articles)
            if article_offset >= batch_total:
                break

        page_items = all_lines[target_skip : target_skip + page_size]
        return {
            "total_lines": total_occurrences,
            "total_articles": total_matching_articles,
            "page": page,
            "page_size": page_size,
            "items": page_items,
        }

    def get_search_distribution(
        self,
        query: str = "",
        search_mode: str = "word_family",
        sources: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        active_only: bool = True,
    ) -> Dict[str, Any]:
        """
        Compute faceted breakdown of matching articles by language, source, source_type, and year.
        """
        has_query = bool(query and query.strip())
        params: List[Any] = []
        where_clauses: List[str] = []

        if has_query:
            clean_q, _ = self.build_fts_query(query, search_mode=search_mode)
            where_clauses.append("articles_fts MATCH ?")
            params.append(clean_q)

        if source_types:
            type_sources = [s for s in SOURCE_REGISTRY.keys() if get_source_type(s) in source_types]
            effective_sources = [s for s in (sources or type_sources) if s in type_sources]
            if not effective_sources:
                return {"total": 0, "by_language": {}, "by_source": {}, "by_source_type": {}, "by_year": {}}
            placeholders = ",".join("?" for _ in effective_sources)
            where_clauses.append(f"a.source IN ({placeholders})")
            params.extend(effective_sources)
        elif sources:
            placeholders = ",".join("?" for _ in sources)
            where_clauses.append(f"a.source IN ({placeholders})")
            params.extend(sources)

        active_codes = get_active_language_codes()
        effective_langs = [l for l in (languages or active_codes) if l in active_codes] if active_only else languages
        if effective_langs:
            placeholders = ",".join("?" for _ in effective_langs)
            where_clauses.append(f"a.language IN ({placeholders})")
            params.extend(effective_langs)

        if min_date:
            where_clauses.append("a.publish_date >= ?")
            params.append(min_date)
        if max_date:
            where_clauses.append("a.publish_date <= ?")
            params.append(max_date)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        from_sql = "FROM articles_fts f JOIN articles a ON a.id = f.id" if has_query else "FROM articles a"

        sql = f"""
            SELECT 
                a.language,
                a.source,
                substr(a.publish_date, 1, 4) as year,
                count(*) as count
            {from_sql}
            {where_sql}
            GROUP BY a.language, a.source, year
        """

        by_language: Dict[str, int] = {}
        by_source: Dict[str, int] = {}
        by_source_type: Dict[str, int] = {}
        by_year: Dict[str, int] = {}
        total = 0

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            for r in cur.fetchall():
                lang = r["language"]
                src = r["source"]
                yr = r["year"] or "unknown"
                cnt = r["count"]
                stype = get_source_type(src)

                total += cnt
                by_language[lang] = by_language.get(lang, 0) + cnt
                by_source[src] = by_source.get(src, 0) + cnt
                by_source_type[stype] = by_source_type.get(stype, 0) + cnt
                by_year[yr] = by_year.get(yr, 0) + cnt

        return {
            "total": total,
            "by_language": dict(sorted(by_language.items())),
            "by_source": dict(sorted(by_source.items(), key=lambda x: x[1], reverse=True)),
            "by_source_type": dict(sorted(by_source_type.items())),
            "by_year": dict(sorted(by_year.items())),
        }

    def export_filtered_dataset(
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
        limit: int = 2000
    ) -> pd.DataFrame:
        """
        Export filtered corpus articles with clean academic columns and APA citations.
        Used for CSV downloads into R, SPSS, Python, and qualitative coding tools.
        """
        rows, _ = self.search_articles(
            query=query,
            sources=sources,
            languages=languages,
            min_date=min_date,
            max_date=max_date,
            min_sentiment=min_sentiment,
            max_sentiment=max_sentiment,
            min_moral=min_moral,
            expand_trilingual=expand_trilingual,
            enable_prefix=enable_prefix,
            use_hybrid=False,  # High throughput deterministic retrieval for bulk cohorts
            limit=limit,
            offset=0
        )
        if not rows:
            return pd.DataFrame()

        records = []
        for r in rows:
            author = r.get("author") or "Redaktion"
            pub_date = r.get("publish_date") or ""
            pub_year = pub_date[:4] if pub_date else "ND"
            source_name = SOURCE_LABELS.get(r.get("source"), r.get("source", ""))
            title = r.get("title", "")
            apa = f"{author} ({pub_year}). {title}. {source_name}. DIDI Corpus ID: {r.get('id')}."

            clean_snippet = re.sub(r'<[^>]+>', '', r.get("snippet", ""))
            clean_snippet = re.sub(r'\s+', ' ', clean_snippet).strip()

            records.append({
                "corpus_id": r.get("id"),
                "source": source_name,
                "language": r.get("language"),
                "publish_date": pub_date[:10] if pub_date else "",
                "author": author,
                "title": title,
                "category": r.get("category"),
                "word_count": r.get("word_count"),
                "net_sentiment": r.get("net_sentiment"),
                "care_density": r.get("care_density"),
                "fairness_density": r.get("fairness_density"),
                "loyalty_density": r.get("loyalty_density"),
                "authority_density": r.get("authority_density"),
                "sanctity_density": r.get("sanctity_density"),
                "moral_density": r.get("moral_density"),
                "trust_density": r.get("trust_density"),
                "fear_density": r.get("fear_density"),
                "joy_density": r.get("joy_density"),
                "sadness_density": r.get("sadness_density"),
                "anger_density": r.get("anger_density"),
                "anticipation_density": r.get("anticipation_density"),
                "disgust_density": r.get("disgust_density"),
                "surprise_density": r.get("surprise_density"),
                "context_snippet": clean_snippet,
                "url": r.get("url"),
                "apa_citation": apa
            })
        return pd.DataFrame(records)

    def search_article_ids(
        self,
        query: str = "",
        sources: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        active_only: bool = False,
    ) -> List[str]:
        """Return the IDs of all articles matching a search, without the cost of loading their text."""
        where_clauses: List[str] = []
        params: List[Any] = []
        has_query = bool(query and query.strip())
        if has_query:
            fts_query, _ = self.build_fts_query(query)
            where_clauses.append("articles_fts MATCH ?")
            params.append(fts_query)
        if source_types:
            type_sources = [s for s in SOURCE_REGISTRY.keys() if get_source_type(s) in source_types]
            if sources:
                effective_sources = [s for s in sources if s in type_sources]
            else:
                effective_sources = type_sources
            if not effective_sources:
                return []
            where_clauses.append(f"a.source IN ({','.join('?' for _ in effective_sources)})")
            params.extend(effective_sources)
        elif sources:
            where_clauses.append(f"a.source IN ({','.join('?' for _ in sources)})")
            params.extend(sources)
        active_codes = get_active_language_codes()
        if active_only:
            if languages:
                effective_langs = [l for l in languages if l in active_codes]
                if not effective_langs:
                    return []
            else:
                effective_langs = list(active_codes)
        else:
            effective_langs = languages

        if effective_langs:
            where_clauses.append(f"a.language IN ({','.join('?' for _ in effective_langs)})")
            params.extend(effective_langs)
        from_sql = "articles_fts f JOIN articles a ON a.id = f.id" if has_query else "articles a"
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        with self._get_connection() as conn:
            return [row["id"] for row in conn.execute(f"SELECT a.id FROM {from_sql} {where_sql}", params)]

    def get_article_metadata(self, article_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return {id: metadata} for the given articles, leaving out any that aren't in the corpus."""
        found: Dict[str, Dict[str, Any]] = {}
        ids = sorted(set(article_ids))
        with self._get_connection() as conn:
            for index in range(0, len(ids), 500):
                batch = ids[index : index + 500]
                rows = conn.execute(
                    f"""
                    SELECT id, source, language, url, title, publish_date, author, word_count, metadata_json
                    FROM articles WHERE id IN ({','.join('?' for _ in batch)})
                    """,
                    batch,
                )
                for row in rows:
                    d = dict(row)
                    d["source_type"] = get_source_type(d["source"])
                    if "metadata_json" in d:
                        try:
                            meta = json.loads(d.pop("metadata_json") or "{}")
                            d["metadata"] = meta
                            d["twin_article_id"] = meta.get("twin_article_id")
                        except Exception:
                            d["metadata"] = {}
                            d["twin_article_id"] = None
                    found[d["id"]] = d
        return found

    def get_article_texts(self, article_ids: List[str]) -> Dict[str, str]:
        """Return {id: full_text} for the given articles, leaving out any that aren't in the corpus."""
        found: Dict[str, str] = {}
        ids = sorted(set(article_ids))
        with self._get_connection() as conn:
            for index in range(0, len(ids), 500):
                batch = ids[index : index + 500]
                rows = conn.execute(f"SELECT id, full_text FROM articles WHERE id IN ({','.join('?' for _ in batch)})", batch)
                found.update({row["id"]: row["full_text"] for row in rows})
        return found

    def get_articles_for_qdpx(self, article_ids: List[str]) -> List[Dict[str, Any]]:
        """Return QDPX document records for the given articles, oldest first."""
        placeholders = ",".join("?" * len(article_ids))
        with self._get_connection() as conn:
            rows = conn.execute(f"""
                SELECT id, source, language, url, title, publish_date, author, category, full_text
                FROM articles
                WHERE id IN ({placeholders})
                ORDER BY publish_date ASC, id ASC
            """, article_ids).fetchall()

        documents = []
        for row in rows:
            date = row["publish_date"][:10]
            author = row["author"] or "Redaktion"
            source = SOURCE_LABELS.get(row["source"], row["source"])
            documents.append({
                "corpus_id": row["id"],
                "name": f"{date} {source} [{row['language']}] {row['title']}",
                "text": row["full_text"],
                "citation": f"{author} ({date[:4]}). {row['title']}. {source}. DIDI Corpus ID: {row['id']}.",
                "source": source,
                "variety": LANGUAGE_LABELS.get(row["language"], row["language"]),
                "publish_date": date,
                "author": author,
                "category": row["category"],
                "url": row["url"],
            })
        return documents

    def build_maxqda_export(self, limit: int = QDPX_EXPORT_LIMIT, **filters: Any) -> bytes:
        """Build a .qdpx project from the articles matching the search filters."""
        rows, _ = self.search_articles(use_hybrid=False, limit=limit, offset=0, **filters)
        return build_qdpx("DIDI corpus export", self.get_articles_for_qdpx([r["id"] for r in rows]))

    def get_triangulation_summary(
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
        enable_prefix: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute instant 3-way triangulation (German, Italian, Ladin) for the current search query.
        Returns article counts, mean valence, and dominant Moral Foundation per linguistic group.
        """
        where_clauses = []
        params = []
        has_query = bool(query and query.strip())

        if has_query:
            clean_q = query.strip()
            if expand_trilingual:
                clean_q_lower = clean_q.lower()
                expanded_q = TRILINGUAL_THESAURUS.get(clean_q_lower)
                if expanded_q:
                    clean_q = expanded_q

            if enable_prefix and " " not in clean_q and not clean_q.endswith("*") and "OR" not in clean_q:
                clean_q = f"{clean_q}*"

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
        else:
            from_sql = """
                FROM articles a
                LEFT JOIN article_nlp_metrics m ON m.article_id = a.id
            """

        sql = f"""
            SELECT 
                CASE 
                    WHEN a.language = 'de' THEN 'German'
                    WHEN a.language = 'it' THEN 'Italian'
                    ELSE 'Ladin'
                END as group_name,
                count(*) as article_count,
                avg(m.net_sentiment) as mean_sentiment,
                avg(m.care_density) as care,
                avg(m.fairness_density) as fairness,
                avg(m.loyalty_density) as loyalty,
                avg(m.authority_density) as authority,
                avg(m.sanctity_density) as sanctity
            {from_sql}
            {where_sql}
            GROUP BY group_name
        """

        summary = {
            "German": {"count": 0, "mean_sentiment": 0.0, "top_foundation": "None", "top_foundation_val": 0.0},
            "Italian": {"count": 0, "mean_sentiment": 0.0, "top_foundation": "None", "top_foundation_val": 0.0},
            "Ladin": {"count": 0, "mean_sentiment": 0.0, "top_foundation": "None", "top_foundation_val": 0.0}
        }

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            for row in cur.fetchall():
                r = dict(row)
                grp = r["group_name"]
                c = r["article_count"]
                s = r["mean_sentiment"] or 0.0
                founds = {
                    "Care": r["care"] or 0.0,
                    "Fairness": r["fairness"] or 0.0,
                    "Loyalty": r["loyalty"] or 0.0,
                    "Authority": r["authority"] or 0.0,
                    "Sanctity": r["sanctity"] or 0.0
                }
                top_f = max(founds.items(), key=lambda x: x[1])
                summary[grp] = {
                    "count": c,
                    "mean_sentiment": round(float(s), 2),
                    "top_foundation": top_f[0],
                    "top_foundation_val": round(float(top_f[1]), 1),
                    **{k.lower(): round(float(v), 1) for k, v in founds.items()}
                }

        return summary

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
            d["source_type"] = get_source_type(d["source"])
            if d.get("breadcrumbs_json"):
                d["breadcrumbs"] = json.loads(d["breadcrumbs_json"])
            if d.get("metadata_json"):
                d["metadata"] = json.loads(d["metadata_json"])
                d["twin_article_id"] = d["metadata"].get("twin_article_id")
            else:
                d["twin_article_id"] = None

            # Compute readability metrics dynamically if full text is available
            if d.get("full_text"):
                rb = analyze_readability(d["full_text"], language=d.get("language", "de"))
                d["readability_score"] = rb.score
                d["readability_metric"] = rb.primary_metric
                d["readability_grade"] = rb.grade_level
                d["lix"] = rb.lix
            else:
                d["readability_score"] = None
                d["readability_metric"] = None
                d["readability_grade"] = None
                d["lix"] = None

            return d

    def get_article_words(self, article_id: str) -> List[Dict[str, Any]]:
        """Retrieve word layer tokens for an article, ordered by token_idx."""
        from src.storage.word_layer import get_article_words as _get_words
        return _get_words(self.words_db_path, article_id)

    def get_passage_words(self, article_id: str, start_char: int, end_char: int) -> List[Dict[str, Any]]:
        """Retrieve word layer tokens covering or intersecting a text span [start_char:end_char]."""
        from src.storage.word_layer import get_passage_words as _get_passage
        return _get_passage(self.words_db_path, article_id, start_char, end_char)

    def get_article_quotes(self, article_id: str) -> List[Dict[str, Any]]:
        """Retrieve detected quote spans for an article, ordered by start_char."""
        from src.storage.word_layer import get_article_quotes as _get_quotes
        return _get_quotes(self.words_db_path, article_id)

    def get_passage_quotes(self, article_id: str, start_char: int, end_char: int) -> List[Dict[str, Any]]:
        """Retrieve detected quote spans covering or intersecting a text span [start_char:end_char]."""
        from src.storage.word_layer import get_passage_quotes as _get_passage_quotes
        return _get_passage_quotes(self.words_db_path, article_id, start_char, end_char)

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
            FROM article_nlp_metrics m
            CROSS JOIN articles a ON a.id = m.article_id
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

    def get_focus_event_coverage(self, event_date_str: str, window_days: int = 30) -> Dict[str, int]:
        """Count articles per language group inside an event's pre/post window."""
        event_date = datetime.fromisoformat(event_date_str).date()
        start = (event_date - timedelta(days=window_days)).isoformat()
        end = (event_date + timedelta(days=window_days)).isoformat()
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT COALESCE(SUM(language = 'de'), 0) AS de,
                       COALESCE(SUM(language = 'it'), 0) AS it,
                       COALESCE(SUM(language LIKE 'lld%'), 0) AS lld
                FROM articles
                WHERE substr(publish_date, 1, 10) >= ? AND substr(publish_date, 1, 10) < ?
            """, (start, end)).fetchone()
        return dict(row)

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
        sources: Optional[List[str]] = None,
        radar_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Calculate pairwise Jensen-Shannon Moral Divergence across DE, IT, and LLD.
        """
        if radar_df is None:
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
