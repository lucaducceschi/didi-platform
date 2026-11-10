"""
Macro-level Quantitative Corpus Analytics API Router.
Ports the quantitative views from the Streamlit workbench (Moral Foundations Radar,
Plutchik discrete emotions, longitudinal timeline dynamics, focus event meaning-making,
and Dunning G² differential keyness) into the FastAPI backend.
"""

import logging
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from src.ui.data_service import LANGUAGE_LABELS, SOURCE_LABELS, DataService

from backend.app.corpus import get_corpus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])
Corpus = Annotated[DataService, Depends(get_corpus)]

_RADAR_CACHE: Dict[str, Any] = {}
_FOCUS_EVENTS_CACHE: Optional[List[Dict[str, Any]]] = None


@router.get("/radar")
def get_radar_analytics(
    corpus: Corpus,
    q: str = "",
    source: Annotated[Optional[List[str]], Query()] = None,
    language: Annotated[Optional[List[str]], Query()] = None,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return aggregated 5-axis Moral Foundations and 8-emotion Plutchik densities
    grouped by language variety, plus cross-lingual pairwise JSD divergence.
    """
    cache_key = f"{q.strip()}|{sorted(source or [])}|{sorted(language or [])}|{min_date}|{max_date}"
    if cache_key in _RADAR_CACHE:
        return _RADAR_CACHE[cache_key]

    try:
        radar_df = corpus.get_aggregated_radar_data(
            query=q,
            sources=source,
            languages=language,
            min_date=min_date,
            max_date=max_date,
        )

        languages_data = []
        if not radar_df.empty:
            for _, row in radar_df.iterrows():
                lang = str(row["language"])
                languages_data.append({
                    "language": lang,
                    "language_label": LANGUAGE_LABELS.get(lang, lang.upper()),
                    "article_count": int(row["article_count"]),
                    "net_sentiment": round(float(row.get("net_sentiment", 0.0) or 0.0), 3),
                    "moral_density": round(float(row.get("moral_density", 0.0) or 0.0), 2),
                    "foundations": {
                        "care": round(float(row.get("care_density", 0.0) or 0.0), 2),
                        "fairness": round(float(row.get("fairness_density", 0.0) or 0.0), 2),
                        "loyalty": round(float(row.get("loyalty_density", 0.0) or 0.0), 2),
                        "authority": round(float(row.get("authority_density", 0.0) or 0.0), 2),
                        "sanctity": round(float(row.get("sanctity_density", 0.0) or 0.0), 2),
                    },
                    "emotions": {
                        "anger": round(float(row.get("anger_density", 0.0) or 0.0), 2),
                        "anticipation": round(float(row.get("anticipation_density", 0.0) or 0.0), 2),
                        "disgust": round(float(row.get("disgust_density", 0.0) or 0.0), 2),
                        "fear": round(float(row.get("fear_density", 0.0) or 0.0), 2),
                        "joy": round(float(row.get("joy_density", 0.0) or 0.0), 2),
                        "sadness": round(float(row.get("sadness_density", 0.0) or 0.0), 2),
                        "surprise": round(float(row.get("surprise_density", 0.0) or 0.0), 2),
                        "trust": round(float(row.get("trust_density", 0.0) or 0.0), 2),
                    },
                })

        pairwise_jsd = corpus.compute_cross_lingual_moral_divergence(
            query=q, sources=source, radar_df=radar_df
        )

        res = {
            "languages": languages_data,
            "pairwise_jsd": pairwise_jsd,
        }
        if len(_RADAR_CACHE) > 100:
            _RADAR_CACHE.clear()
        _RADAR_CACHE[cache_key] = res
        return res
    except Exception as exc:
        logger.exception("Error calculating radar analytics: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/timeline")
def get_timeline_analytics(
    corpus: Corpus,
    q: str = "",
    source: Annotated[Optional[List[str]], Query()] = None,
    language: Annotated[Optional[List[str]], Query()] = None,
) -> Dict[str, Any]:
    """
    Return longitudinal monthly timeseries of article volume, net sentiment,
    and moral framing density across languages (2017–2026).
    """
    try:
        with corpus._get_connection() as conn:
            sql = """
                SELECT substr(a.publish_date, 1, 7) AS period, a.language,
                       COUNT(*) AS article_count,
                       AVG(m.net_sentiment) AS avg_sentiment,
                       AVG(m.moral_density) AS avg_moral_density,
                       AVG(a.word_count) AS avg_word_count
                FROM articles a
                JOIN article_nlp_metrics m ON a.id = m.article_id
                WHERE a.publish_date IS NOT NULL AND a.publish_date != ''
            """
            params: List[Any] = []
            if q:
                fts_q, _ = corpus.build_fts_query(q, expand_trilingual=True, enable_prefix=True)
                sql += " AND a.id IN (SELECT id FROM articles_fts WHERE articles_fts MATCH ?)"
                params.append(fts_q)
            if source:
                placeholders = ",".join("?" * len(source))
                sql += f" AND a.source IN ({placeholders})"
                params.extend(source)
            if language:
                placeholders = ",".join("?" * len(language))
                sql += f" AND a.language IN ({placeholders})"
                params.extend(language)

            sql += " GROUP BY period, a.language ORDER BY period ASC"
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        series = []
        for r in rows:
            period = r["period"]
            # Filter out non-date periods or malformed years
            if not period or len(period) < 7:
                continue
            series.append({
                "period": period,
                "language": r["language"],
                "article_count": int(r["article_count"]),
                "avg_sentiment": round(float(r["avg_sentiment"] or 0.0), 3),
                "avg_moral_density": round(float(r["avg_moral_density"] or 0.0), 2),
                "avg_word_count": round(float(r["avg_word_count"] or 0.0), 1),
            })

        return {"series": series}
    except Exception as exc:
        logger.exception("Error querying timeline analytics: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/focus-events")
def get_focus_events_list(corpus: Corpus) -> List[Dict[str, Any]]:
    """Return registry of historical regional focus events with coverage counts."""
    global _FOCUS_EVENTS_CACHE
    if _FOCUS_EVENTS_CACHE is not None:
        return _FOCUS_EVENTS_CACHE

    events_dict = corpus.get_focus_events()
    out = []
    for date_str, info in sorted(events_dict.items()):
        coverage = corpus.get_focus_event_coverage(date_str, info.get("default_window", 30))
        out.append({
            "id": date_str,
            "date": date_str,
            "title": info["title"],
            "description": info["description"],
            "category": info["category"],
            "default_window": info.get("default_window", 30),
            "coverage": coverage,
        })
    _FOCUS_EVENTS_CACHE = out
    return out


@router.get("/focus-events/{event_date}")
def analyze_focus_event_details(
    corpus: Corpus,
    event_date: str,
    window_days: Annotated[int, Query(ge=7, le=120)] = 30,
    q: str = "",
) -> Dict[str, Any]:
    """Run pre/post focus event framing analysis per Hurtado-Bodell & Menshikova (2026)."""
    try:
        res = corpus.analyze_focus_event(event_date, window_days=window_days, query=q)

        # Serialize keyness dataframe
        keyness_records = []
        if "keyness_df" in res and not res["keyness_df"].empty:
            for _, row in res["keyness_df"].iterrows():
                keyness_records.append({
                    "term": str(row["term"]),
                    "g2": round(float(row["g2"]), 2),
                    "target_per_1k": round(float(row["target_per_1k"]), 2),
                    "ref_per_1k": round(float(row["ref_per_1k"]), 2),
                })

        return {
            "event_date": res["event_date"],
            "window_days": res["window_days"],
            "pre_period": res["pre_period"],
            "post_period": res["post_period"],
            "pre_count": res["pre_count"],
            "post_count": res["post_count"],
            "pct_surge": res["pct_surge"],
            "pre_sentiment": res["pre_sentiment"],
            "post_sentiment": res["post_sentiment"],
            "delta_sentiment": res["delta_sentiment"],
            "moral_divergence": res["moral_divergence"],
            "pre_moral": res["pre_moral"],
            "post_moral": res["post_moral"],
            "keyness": keyness_records,
        }
    except Exception as exc:
        logger.exception("Error analyzing focus event %s: %s", event_date, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/keyness")
def get_cross_lingual_keyness_endpoint(
    corpus: Corpus,
    target_lang: str = "de",
    ref_lang: str = "it",
    q: str = "",
    source: Annotated[Optional[List[str]], Query()] = None,
    top_n: Annotated[int, Query(ge=5, le=50)] = 15,
) -> List[Dict[str, Any]]:
    """Compute Dunning G² differential keyness between two languages."""
    try:
        df = corpus.get_cross_lingual_keyness(
            target_lang=target_lang,
            ref_lang=ref_lang,
            query=q,
            sources=source,
            top_n=top_n,
        )
        records = []
        if not df.empty:
            for _, row in df.iterrows():
                records.append({
                    "term": str(row["term"]),
                    "g2": round(float(row["g2"]), 2),
                    "target_per_1k": round(float(row["target_per_1k"]), 2),
                    "ref_per_1k": round(float(row["ref_per_1k"]), 2),
                })
        return records
    except Exception as exc:
        logger.exception("Error calculating keyness: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/word-bubbles")
def get_word_bubbles_endpoint(
    corpus: Corpus,
    mode: Annotated[str, Query(pattern="^(focus|languages|discourse)$")] = "focus",
) -> List[Dict[str, Any]]:
    """
    Retrieve interactive word bubble cluster for the dashboard.
    Modes:
    - 'focus': Top regional sociopolitical themes
    - 'languages': Cross-linguistic keyness gap (German vs. Italian media emphasis)
    - 'discourse': Journalistic scrutiny vs. Official Press PR framing
    """
    try:
        from backend.app.services.word_bubbles import get_word_bubbles
        return get_word_bubbles(corpus, mode=mode)
    except Exception as exc:
        logger.exception("Error retrieving word bubbles: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


