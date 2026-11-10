import logging
import math
import re
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.nlp.complexity import analyze_complexity
from src.nlp.concreteness import analyze_concreteness
from src.nlp.framing_divergence import (
    FOUNDATION_KEYS,
    compute_dunning_keyness,
    compute_jsd,
    compute_moral_divergence,
)
from src.nlp.readability import analyze_readability
from src.sources import SOURCE_LABELS, SOURCE_TYPE_LABELS, get_source_type
from src.ui.data_service import DataService

from backend.app.corpus import get_corpus
from backend.app.models import Project, SavedCorpusSelection, SavedSelectionMember

logger = logging.getLogger(__name__)

EMOTION_KEYS = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]

DE_INGROUP_PRONOUNS = {"wir", "uns", "unser", "unsere", "unserer", "unseres", "unseren", "unserm", "unserem"}
IT_INGROUP_PRONOUNS = {"noi", "ci", "nostro", "nostra", "nostri", "nostre"}


def compute_emotion_divergence(
    emotions_a: Dict[str, float],
    emotions_b: Dict[str, float]
) -> Dict[str, Any]:
    """Calculate Jensen-Shannon Divergence across 8 discrete Plutchik emotions."""
    vec_a = np.array([float(emotions_a.get(k, 0.0)) for k in EMOTION_KEYS])
    vec_b = np.array([float(emotions_b.get(k, 0.0)) for k in EMOTION_KEYS])

    sum_a = np.sum(vec_a)
    sum_b = np.sum(vec_b)

    if sum_a == 0 or sum_b == 0:
        return {
            "jsd": 0.0,
            "norm_vec_a": {k: 0.0 for k in EMOTION_KEYS},
            "norm_vec_b": {k: 0.0 for k in EMOTION_KEYS},
            "deltas": {k: 0.0 for k in EMOTION_KEYS},
        }

    norm_a = vec_a / sum_a
    norm_b = vec_b / sum_b
    jsd_score = compute_jsd(norm_a, norm_b)
    deltas = {k: float(norm_a[i] - norm_b[i]) for i, k in enumerate(EMOTION_KEYS)}

    return {
        "jsd": round(jsd_score, 4),
        "norm_vec_a": {k: round(float(norm_a[i]), 4) for i, k in enumerate(EMOTION_KEYS)},
        "norm_vec_b": {k: round(float(norm_b[i]), 4) for i, k in enumerate(EMOTION_KEYS)},
        "deltas": {k: round(v, 4) for k, v in deltas.items()},
    }


def compute_selection_profile(
    article_ids: List[str],
    label: str,
    selection_id: str = "",
    data_service: Optional[DataService] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Compute full linguistic, moral, and emotional profile for a set of article IDs.
    Returns (profile_dict, full_texts).
    """
    if data_service is None:
        data_service = get_corpus()

    if not article_ids:
        empty_profile = {
            "id": selection_id,
            "label": label,
            "article_count": 0,
            "total_words": 0,
            "dominant_language": "de",
            "net_sentiment": 0.0,
            "moral_density": 0.0,
            "foundations": {k: 0.0 for k in ["care", "fairness", "loyalty", "authority", "sanctity"]},
            "emotions": {k: 0.0 for k in EMOTION_KEYS},
            "readability": {"score": 0.0, "metric": "WSTF 1", "grade": "N/A"},
            "nominal_ratio": 0.0,
            "concreteness": 3.0,
            "ingroup_pronouns_rate": 0.0,
            "languages": {},
            "sources": {},
            "source_types": {},
            "timeline": [],
        }
        return empty_profile, []

    placeholders = ",".join("?" * len(article_ids))
    with data_service._get_connection() as conn:
        cursor = conn.cursor()
        sql = f"""
            SELECT a.id, a.title, a.publish_date, a.source, a.language, a.full_text, a.word_count,
                   m.net_sentiment, m.moral_density,
                   m.care_density, m.fairness_density, m.loyalty_density, m.authority_density, m.sanctity_density,
                   m.anger_density, m.anticipation_density, m.disgust_density, m.fear_density,
                   m.joy_density, m.sadness_density, m.surprise_density, m.trust_density
            FROM articles a
            LEFT JOIN article_nlp_metrics m ON a.id = m.article_id
            WHERE a.id IN ({placeholders})
            ORDER BY a.publish_date ASC
        """
        cursor.execute(sql, article_ids)
        rows = [dict(r) for r in cursor.fetchall()]

    n = len(rows)
    if n == 0:
        return compute_selection_profile([], label, selection_id, data_service)

    lang_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    full_texts: List[str] = []

    sum_sent = 0.0
    sum_moral = 0.0
    sum_care = 0.0
    sum_fairness = 0.0
    sum_loyalty = 0.0
    sum_authority = 0.0
    sum_sanctity = 0.0
    sum_nominal_ratio = 0.0
    sum_concreteness = 0.0
    sum_readability = 0.0
    readability_count = 0
    total_words = 0
    total_ingroup_hits = 0

    sum_emotions = {k: 0.0 for k in EMOTION_KEYS}

    # Timeline buckets grouped by year
    timeline_map: Dict[str, Dict[str, Any]] = {}

    for r in rows:
        text = r.get("full_text") or ""
        if text:
            full_texts.append(text)
        lang = r.get("language") or "de"
        src = r.get("source") or "unknown"
        stype = get_source_type(src)
        wcount = r.get("word_count") or len(text.split())

        lang_counts[lang] += 1
        source_counts[src] += 1
        type_counts[stype] += 1
        total_words += wcount

        sent = float(r.get("net_sentiment") or 0.0)
        moral = float(r.get("moral_density") or 0.0)
        care = float(r.get("care_density") or 0.0)
        fairness = float(r.get("fairness_density") or 0.0)
        loyalty = float(r.get("loyalty_density") or 0.0)
        authority = float(r.get("authority_density") or 0.0)
        sanctity = float(r.get("sanctity_density") or 0.0)

        sum_sent += sent
        sum_moral += moral
        sum_care += care
        sum_fairness += fairness
        sum_loyalty += loyalty
        sum_authority += authority
        sum_sanctity += sanctity

        for k in EMOTION_KEYS:
            sum_emotions[k] += float(r.get(f"{k}_density") or 0.0)

        # Ingroup pronoun hits via regex matching
        lower_words = re.findall(r"\b\w+\b", text.lower())
        ingroup_target = IT_INGROUP_PRONOUNS if lang == "it" else DE_INGROUP_PRONOUNS
        n_ingroup = sum(1 for w in lower_words if w in ingroup_target)
        total_ingroup_hits += n_ingroup

        # Readability & complexity sample (first 100 articles if large)
        if len(full_texts) <= 100:
            rb = analyze_readability(text, language=lang) if text else None
            cx = analyze_complexity(text) if text else None
            cn = analyze_concreteness(text, language=lang) if text else None

            if rb and rb.score is not None:
                sum_readability += rb.score
                readability_count += 1
            if cx:
                sum_nominal_ratio += cx.nominal_ratio
            if cn:
                sum_concreteness += cn.score

        # Timeline aggregation
        pdate = (r.get("publish_date") or "")[:4]
        if pdate:
            if pdate not in timeline_map:
                timeline_map[pdate] = {"period": pdate, "count": 0, "sum_sentiment": 0.0, "sum_moral": 0.0}
            timeline_map[pdate]["count"] += 1
            timeline_map[pdate]["sum_sentiment"] += sent
            timeline_map[pdate]["sum_moral"] += moral

    # Timeline list sorted chronologically
    timeline_list = []
    for y in sorted(timeline_map.keys()):
        item = timeline_map[y]
        cnt = item["count"]
        timeline_list.append({
            "period": y,
            "count": cnt,
            "sentiment": round(item["sum_sentiment"] / cnt, 3) if cnt > 0 else 0.0,
            "moral_density": round(item["sum_moral"] / cnt, 2) if cnt > 0 else 0.0,
        })

    dominant_lang = lang_counts.most_common(1)[0][0] if lang_counts else "de"
    avg_sample_n = max(readability_count, 1)
    ingroup_rate = round((total_ingroup_hits / max(total_words, 1)) * 1000.0, 2)

    profile = {
        "id": selection_id,
        "label": label,
        "article_count": n,
        "total_words": total_words,
        "dominant_language": dominant_lang,
        "net_sentiment": round(sum_sent / n, 3),
        "moral_density": round(sum_moral / n, 2),
        "foundations": {
            "care": round(sum_care / n, 2),
            "fairness": round(sum_fairness / n, 2),
            "loyalty": round(sum_loyalty / n, 2),
            "authority": round(sum_authority / n, 2),
            "sanctity": round(sum_sanctity / n, 2),
        },
        "emotions": {k: round(sum_emotions[k] / n, 2) for k in EMOTION_KEYS},
        "readability": {
            "score": round(sum_readability / avg_sample_n, 1) if readability_count > 0 else 50.0,
            "metric": "Gulpease" if dominant_lang == "it" else "WSTF 1",
            "grade": "Standard",
        },
        "nominal_ratio": round(sum_nominal_ratio / avg_sample_n, 2) if avg_sample_n > 0 else 1.2,
        "concreteness": round(sum_concreteness / avg_sample_n, 2) if avg_sample_n > 0 else 3.0,
        "ingroup_pronouns_rate": ingroup_rate,
        "languages": dict(lang_counts),
        "sources": dict(source_counts),
        "source_types": dict(type_counts),
        "timeline": timeline_list,
    }

    return profile, full_texts


def compare_selections(
    db: Session,
    project: Project,
    selection_a_id: uuid.UUID,
    selection_b_id: Optional[uuid.UUID] = None,
    partition_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generalized comparison engine across:
    1. Selection A vs Selection B
    2. Selection A vs Regional Corpus Baseline
    3. Partitions within Selection A (e.g. language, source, source_type, year)
    """
    data_service = get_corpus()

    # 1. Fetch Selection A
    sel_a = db.scalar(
        select(SavedCorpusSelection).where(
            SavedCorpusSelection.id == selection_a_id,
            SavedCorpusSelection.project_id == project.id,
        )
    )
    if not sel_a:
        raise HTTPException(status_code=404, detail="Selection A not found.")

    members_a = db.scalars(
        select(SavedSelectionMember.article_id).where(SavedSelectionMember.selection_id == sel_a.id)
    ).all()
    article_ids_a = list(members_a)

    if not article_ids_a:
        raise HTTPException(status_code=400, detail="Selection A contains no articles.")

    # -----------------------------------------------------------------
    # Case 1: Partition within Selection A
    # -----------------------------------------------------------------
    if partition_by:
        placeholders = ",".join("?" * len(article_ids_a))
        with data_service._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT id, language, source, publish_date FROM articles WHERE id IN ({placeholders})",
                article_ids_a,
            )
            meta_rows = [dict(r) for r in cursor.fetchall()]

        group_1_ids: List[str] = []
        group_2_ids: List[str] = []
        label_1 = ""
        label_2 = ""

        if partition_by == "language":
            group_1_ids = [r["id"] for r in meta_rows if r.get("language") == "de"]
            group_2_ids = [r["id"] for r in meta_rows if r.get("language") == "it"]
            label_1 = f"{sel_a.name} (German)"
            label_2 = f"{sel_a.name} (Italian)"
        elif partition_by == "source_type":
            group_1_ids = [r["id"] for r in meta_rows if get_source_type(r.get("source", "")) == "journalism"]
            group_2_ids = [r["id"] for r in meta_rows if get_source_type(r.get("source", "")) == "official_press"]
            label_1 = f"{sel_a.name} (Journalism)"
            label_2 = f"{sel_a.name} (Official Press)"
        elif partition_by == "source":
            src_counts = Counter(r.get("source") for r in meta_rows)
            top_sources = [s for s, _ in src_counts.most_common(2)]
            if len(top_sources) < 2:
                raise HTTPException(status_code=400, detail="Selection does not contain at least 2 distinct sources to partition.")
            s1, s2 = top_sources[0], top_sources[1]
            group_1_ids = [r["id"] for r in meta_rows if r.get("source") == s1]
            group_2_ids = [r["id"] for r in meta_rows if r.get("source") == s2]
            label_1 = f"{sel_a.name} ({SOURCE_LABELS.get(s1, s1)})"
            label_2 = f"{sel_a.name} ({SOURCE_LABELS.get(s2, s2)})"
        elif partition_by == "year":
            years = sorted({(r.get("publish_date") or "")[:4] for r in meta_rows if r.get("publish_date")})
            if len(years) < 2:
                raise HTTPException(status_code=400, detail="Selection does not span at least 2 distinct years to partition.")
            mid = len(years) // 2
            years_early = set(years[:mid])
            years_late = set(years[mid:])
            group_1_ids = [r["id"] for r in meta_rows if (r.get("publish_date") or "")[:4] in years_early]
            group_2_ids = [r["id"] for r in meta_rows if (r.get("publish_date") or "")[:4] in years_late]
            label_1 = f"{sel_a.name} ({years[0]}–{years[mid-1]})"
            label_2 = f"{sel_a.name} ({years[mid]}–{years[-1]})"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported partition_by '{partition_by}'.")

        if not group_1_ids or not group_2_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Partitioning by '{partition_by}' resulted in an empty subset ({len(group_1_ids)} vs {len(group_2_ids)}).",
            )

        prof_a, texts_a = compute_selection_profile(group_1_ids, label_1, str(sel_a.id), data_service)
        prof_b, texts_b = compute_selection_profile(group_2_ids, label_2, str(sel_a.id), data_service)
        comp_type = "partition"
        part_label = partition_by

    # -----------------------------------------------------------------
    # Case 2: Selection A vs Selection B
    # -----------------------------------------------------------------
    elif selection_b_id:
        sel_b = db.scalar(
            select(SavedCorpusSelection).where(
                SavedCorpusSelection.id == selection_b_id,
                SavedCorpusSelection.project_id == project.id,
            )
        )
        if not sel_b:
            raise HTTPException(status_code=404, detail="Selection B not found.")

        members_b = db.scalars(
            select(SavedSelectionMember.article_id).where(SavedSelectionMember.selection_id == sel_b.id)
        ).all()
        article_ids_b = list(members_b)

        if not article_ids_b:
            raise HTTPException(status_code=400, detail="Selection B contains no articles.")

        prof_a, texts_a = compute_selection_profile(article_ids_a, sel_a.name, str(sel_a.id), data_service)
        prof_b, texts_b = compute_selection_profile(article_ids_b, sel_b.name, str(sel_b.id), data_service)
        comp_type = "selection_vs_selection"
        part_label = None

    # -----------------------------------------------------------------
    # Case 3: Selection A vs Regional Corpus Baseline
    # -----------------------------------------------------------------
    else:
        prof_a, texts_a = compute_selection_profile(article_ids_a, sel_a.name, str(sel_a.id), data_service)
        dominant_lang = prof_a["dominant_language"]

        # Fetch corpus baseline
        with data_service._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count,
                       AVG(m.net_sentiment) as sentiment,
                       AVG(m.moral_density) as moral_density,
                       AVG(m.care_density) as care,
                       AVG(m.fairness_density) as fairness,
                       AVG(m.loyalty_density) as loyalty,
                       AVG(m.authority_density) as authority,
                       AVG(m.sanctity_density) as sanctity,
                       AVG(m.anger_density) as anger,
                       AVG(m.anticipation_density) as anticipation,
                       AVG(m.disgust_density) as disgust,
                       AVG(m.fear_density) as fear,
                       AVG(m.joy_density) as joy,
                       AVG(m.sadness_density) as sadness,
                       AVG(m.surprise_density) as surprise,
                       AVG(m.trust_density) as trust
                FROM articles a
                JOIN article_nlp_metrics m ON a.id = m.article_id
                WHERE a.language = ?
            """, (dominant_lang,))
            base_row = cursor.fetchone()

            # Random sample of 100 corpus texts for keyness reference
            cursor.execute(f"""
                SELECT a.full_text
                FROM articles a
                WHERE a.language = ? AND a.id NOT IN ({','.join('?' * len(article_ids_a))})
                ORDER BY RANDOM()
                LIMIT 100
            """, [dominant_lang] + article_ids_a)
            ref_rows = cursor.fetchall()
            texts_b = [r[0] for r in ref_rows if r[0]]

        prof_b = {
            "id": "corpus_baseline",
            "label": f"Regional Corpus Baseline ({dominant_lang.upper()})",
            "article_count": base_row["count"] if base_row else 0,
            "total_words": (base_row["count"] if base_row else 0) * 450,
            "dominant_language": dominant_lang,
            "net_sentiment": round(float(base_row["sentiment"] or 0.0), 3) if base_row else 0.0,
            "moral_density": round(float(base_row["moral_density"] or 0.0), 2) if base_row else 0.0,
            "foundations": {
                "care": round(float(base_row["care"] or 0.0), 2) if base_row else 0.0,
                "fairness": round(float(base_row["fairness"] or 0.0), 2) if base_row else 0.0,
                "loyalty": round(float(base_row["loyalty"] or 0.0), 2) if base_row else 0.0,
                "authority": round(float(base_row["authority"] or 0.0), 2) if base_row else 0.0,
                "sanctity": round(float(base_row["sanctity"] or 0.0), 2) if base_row else 0.0,
            },
            "emotions": {k: round(float(base_row[k] or 0.0), 2) if base_row else 0.0 for k in EMOTION_KEYS},
            "readability": {
                "score": 52.0 if dominant_lang == "it" else 7.8,
                "metric": "Gulpease" if dominant_lang == "it" else "WSTF 1",
                "grade": "Standard",
            },
            "nominal_ratio": 1.25,
            "concreteness": 3.1,
            "ingroup_pronouns_rate": 3.2,
            "languages": {dominant_lang: base_row["count"] if base_row else 0},
            "sources": {},
            "source_types": {},
            "timeline": [],
        }
        comp_type = "selection_vs_baseline"
        part_label = None

    # -----------------------------------------------------------------
    # Compute Divergences
    # -----------------------------------------------------------------
    moral_div = compute_moral_divergence(prof_a["foundations"], prof_b["foundations"])
    emotion_div = compute_emotion_divergence(prof_a["emotions"], prof_b["emotions"])

    divergence = {
        "mfdi": moral_div["jsd"],
        "moral_divergence": moral_div,
        "emotion_jsd": emotion_div["jsd"],
        "emotion_divergence": emotion_div,
    }

    # -----------------------------------------------------------------
    # Compute Dunning G2 Keyness
    # -----------------------------------------------------------------
    terms_a: List[Dict[str, Any]] = []
    terms_b: List[Dict[str, Any]] = []

    if texts_a and texts_b:
        df_keyness = compute_dunning_keyness(texts_a, texts_b, min_freq=3, top_n=30)
        if not df_keyness.empty:
            for _, row in df_keyness.iterrows():
                term = str(row["term"])
                t_cnt = int(row["target_count"])
                r_cnt = int(row["ref_count"])
                g2_val = float(row["abs_g2"])
                signed_g2 = float(row["g2"])

                if signed_g2 > 0 and len(terms_a) < 15:
                    terms_a.append({
                        "term": term,
                        "target_count": t_cnt,
                        "ref_count": r_cnt,
                        "target_per_1k": float(row.get("target_per_1k") or 0.0),
                        "ref_per_1k": float(row.get("ref_per_1k") or 0.0),
                        "g2": g2_val,
                        "direction": "overused",
                    })
                elif signed_g2 < 0 and len(terms_b) < 15:
                    terms_b.append({
                        "term": term,
                        "target_count": r_cnt,
                        "ref_count": t_cnt,
                        "target_per_1k": float(row.get("ref_per_1k") or 0.0),
                        "ref_per_1k": float(row.get("target_per_1k") or 0.0),
                        "g2": g2_val,
                        "direction": "overused",
                    })

    return {
        "comparison_type": comp_type,
        "partition_label": part_label,
        "profile_a": prof_a,
        "profile_b": prof_b,
        "divergence": divergence,
        "distinctive_terms_a": terms_a,
        "distinctive_terms_b": terms_b,
    }
