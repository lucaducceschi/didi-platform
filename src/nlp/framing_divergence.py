"""
Event-Driven Framing & Discursive Meaning-Making Engine for DIDI Platform.
Grounding: Hurtado-Bodell & Menshikova (2026), "Mechanisms of change: How focus events reshape online meaning-making" (Poetics).

Implements:
1. Jensen-Shannon Divergence (JSD) for Moral Foundations profiles.
2. Dunning's Log-Likelihood Keyness (G²) for cross-corpus / cross-lingual differential vocabulary.
3. Temporal Focus Event windowing and framing shift analysis.
"""

import math
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

FOUNDATION_KEYS = ["care", "fairness", "loyalty", "authority", "sanctity"]

# Curated regional focus events for South Tyrol (2018–2024)
FOCUS_EVENTS = {
    "2018-10-21": {
        "title": "2018 Provincial Election (Landtagswahl)",
        "description": "SVP loses historic absolute majority (41.9%), leading to the first SVP-Lega regional coalition.",
        "category": "electoral",
        "default_window": 30
    },
    "2019-12-19": {
        "title": "Austrian Dual Citizenship Debate Peak",
        "description": "Austrian government program renews proposal for dual passports for German and Ladin South Tyroleans, sparking fierce debate with Rome.",
        "category": "autonomy",
        "default_window": 30
    },
    "2020-03-10": {
        "title": "COVID-19 First Lockdown & Brenner Controls",
        "description": "National lockdown in Italy followed by Austrian health checks and temporary restrictions at the Brenner border pass.",
        "category": "crisis",
        "default_window": 45
    },
    "2021-10-15": {
        "title": "Green Pass Workplace Mandate",
        "description": "Introduction of mandatory COVID health pass across Italian workplaces, mobilizing regional protests and civil resistance.",
        "category": "crisis",
        "default_window": 30
    },
    "2022-09-25": {
        "title": "Italian National General Election",
        "description": "Meloni-led right-wing coalition wins parliamentary majority in Rome, altering institutional relations with the Autonomous Province.",
        "category": "political",
        "default_window": 30
    },
    "2023-10-22": {
        "title": "2023 Provincial Election & Coalition Realignment",
        "description": "Major political fragmentation: SVP drops to 34.5%, subsequent formation of controversial SVP-Fratelli d'Italia-Freiheitliche government.",
        "category": "electoral",
        "default_window": 45
    },
    "2024-03-01": {
        "title": "Autonomy Statute Reform Proposals",
        "description": "Drafting of constitutional amendments to restore pre-2001 regional competences eroded by Constitutional Court jurisprudence.",
        "category": "autonomy",
        "default_window": 30
    }
}

# Core multilingual stopword list (DE, IT, LLD) to isolate semantic content words
STOPWORDS = {
    # German
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines", "einem", "einen",
    "und", "oder", "aber", "in", "im", "an", "am", "auf", "aus", "bei", "mit", "nach", "von",
    "zu", "zum", "zur", "für", "über", "unter", "vor", "zwischen", "durch", "gegen", "um",
    "ist", "sind", "war", "waren", "wird", "werden", "wurde", "wurden", "hat", "haben", "hatte",
    "hatten", "sein", "seine", "seiner", "seinem", "seinen", "ihr", "ihre", "ihrem", "ihren",
    "ich", "du", "er", "sie", "es", "wir", "ihr", "man", "nicht", "auch", "so", "wie", "als",
    "noch", "nur", "schon", "da", "dass", "daß", "wenn", "weil", "doch", "dann", "sehr",
    "mehr", "immer", "wieder", "hier", "dort", "dies", "diese", "dieser", "dieses", "diesem",
    # Italian
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "un'",
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra", "del", "dello", "della", "dei",
    "degli", "delle", "al", "allo", "alla", "ai", "agli", "alle", "dal", "dallo", "dalla",
    "dai", "dagli", "dalle", "nel", "nello", "nella", "nei", "negli", "nelle", "sul", "sullo",
    "sulla", "sui", "sugli", "sulle", "e", "ed", "o", "ma", "se", "perché", "come", "quando",
    "anche", "non", "più", "molto", "poco", "tutto", "tutti", "tutta", "tutte", "questo",
    "questa", "questi", "queste", "quello", "quella", "quelli", "quelle", "è", "sono", "era",
    "erano", "stato", "stata", "stati", "state", "ha", "hanno", "aveva", "avevano", "ci",
    "vi", "si", "ne", "che", "chi", "cui", "quale", "quali", "cosa", "loro", "suo", "sua",
    # Ladin & Common
    "y", "te", "de", "del", "dla", "dles", "sun", "por", "cun", "nia", "dut", "duta", "chësc",
    "chësta", "é", "fo", "fova", "á", "lausc", "salto", "tageszeitung", "didi"
}


def compute_jsd(p: np.ndarray, q: np.ndarray, eps: float = 1e-12) -> float:
    """
    Compute Jensen-Shannon Divergence between two probability distributions.
    Bounded strictly in [0.0, 1.0] when using base-2 logarithm.
    0.0 = identical moral profile, 1.0 = completely divergent moral emphasis.
    """
    p = np.asarray(p, dtype=float) + eps
    q = np.asarray(q, dtype=float) + eps
    p = p / np.sum(p)
    q = q / np.sum(q)

    m = 0.5 * (p + q)
    kl_pm = np.sum(p * np.log2(p / m))
    kl_qm = np.sum(q * np.log2(q / m))
    jsd_val = 0.5 * kl_pm + 0.5 * kl_qm
    return float(np.clip(jsd_val, 0.0, 1.0))


def compute_moral_divergence(
    profile_a: Dict[str, float],
    profile_b: Dict[str, float]
) -> Dict[str, Any]:
    """
    Calculate Moral Foundations Divergence Index (MFDI) and foundation-level deltas.
    """
    vec_a = np.array([profile_a.get(f"{k}_density", profile_a.get(k, 0.0)) for k in FOUNDATION_KEYS])
    vec_b = np.array([profile_b.get(f"{k}_density", profile_b.get(k, 0.0)) for k in FOUNDATION_KEYS])

    sum_a = np.sum(vec_a)
    sum_b = np.sum(vec_b)

    if sum_a == 0 or sum_b == 0:
        return {
            "jsd": 0.0,
            "norm_vec_a": {k: 0.0 for k in FOUNDATION_KEYS},
            "norm_vec_b": {k: 0.0 for k in FOUNDATION_KEYS},
            "deltas": {k: 0.0 for k in FOUNDATION_KEYS},
            "primary_divergence_foundation": "none"
        }

    norm_a = vec_a / sum_a
    norm_b = vec_b / sum_b
    jsd_score = compute_jsd(norm_a, norm_b)

    deltas = {k: float(norm_a[i] - norm_b[i]) for i, k in enumerate(FOUNDATION_KEYS)}
    primary_k = max(deltas.keys(), key=lambda k: abs(deltas[k]))

    return {
        "jsd": round(jsd_score, 4),
        "norm_vec_a": {k: round(float(norm_a[i]), 4) for i, k in enumerate(FOUNDATION_KEYS)},
        "norm_vec_b": {k: round(float(norm_b[i]), 4) for i, k in enumerate(FOUNDATION_KEYS)},
        "deltas": {k: round(v, 4) for k, v in deltas.items()},
        "primary_divergence_foundation": primary_k
    }


def tokenize_text(text: str) -> List[str]:
    """Fast regex tokenization with stopword and punctuation removal."""
    tokens = re.findall(r"\b[A-Za-zÄÖÜäöüßéèàòùìëç]+(?:'[A-Za-zÄÖÜäöüß]+)?\b", text.lower())
    return [t for t in tokens if len(t) >= 3 and t not in STOPWORDS]


def compute_dunning_keyness(
    texts_target: List[str],
    texts_reference: List[str],
    min_freq: int = 3,
    top_n: int = 25
) -> pd.DataFrame:
    """
    Compute Dunning's Log-Likelihood Keyness (G²) comparing Target corpus against Reference corpus.
    Identifies terms significantly overused or underused in Target vs Reference.
    """
    target_counts = Counter()
    for t in texts_target:
        target_counts.update(tokenize_text(t))

    ref_counts = Counter()
    for t in texts_reference:
        ref_counts.update(tokenize_text(t))

    n1 = sum(target_counts.values())
    n2 = sum(ref_counts.values())

    if n1 == 0 or n2 == 0:
        return pd.DataFrame()

    all_vocab = set(target_counts.keys()).union(set(ref_counts.keys()))
    results = []

    for word in all_vocab:
        o1 = target_counts.get(word, 0)
        o2 = ref_counts.get(word, 0)
        total_word = o1 + o2

        if total_word < min_freq:
            continue

        e1 = n1 * total_word / (n1 + n2)
        e2 = n2 * total_word / (n1 + n2)

        # G² = 2 * sum(O_i * ln(O_i / E_i))
        term1 = o1 * math.log(o1 / e1) if o1 > 0 else 0.0
        term2 = o2 * math.log(o2 / e2) if o2 > 0 else 0.0
        g2 = 2.0 * (term1 + term2)

        # Direction: Overused in Target (+) vs Underused in Target / Overused in Ref (-)
        target_rate = (o1 / n1) * 1000.0
        ref_rate = (o2 / n2) * 1000.0
        direction = 1 if target_rate >= ref_rate else -1

        # Percent difference (%DIFF) effect size
        pct_diff = ((target_rate - ref_rate) / ref_rate * 100.0) if ref_rate > 0 else 100.0

        results.append({
            "term": word,
            "target_count": o1,
            "ref_count": o2,
            "target_per_1k": round(target_rate, 2),
            "ref_per_1k": round(ref_rate, 2),
            "g2": round(g2 * direction, 2),
            "abs_g2": round(g2, 2),
            "pct_diff": round(pct_diff, 1)
        })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values(by="abs_g2", ascending=False).head(top_n)
    return df


class FocusEventManager:
    """Manages focus event analysis against local SQLite database."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def analyze_event_window(
        self,
        event_date_str: str,
        window_days: int = 30,
        query: str = ""
    ) -> Dict[str, Any]:
        """
        Extract articles before and after a focus event and compute framing shifts.
        """
        event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
        pre_start = (event_date - timedelta(days=window_days)).strftime("%Y-%m-%d")
        pre_end = event_date.strftime("%Y-%m-%d")
        post_start = event_date.strftime("%Y-%m-%d")
        post_end = (event_date + timedelta(days=window_days)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        sql_base = """
            SELECT 
                a.id, a.source, a.language, a.title, a.publish_date, a.full_text, a.word_count,
                m.net_sentiment, m.moral_density,
                m.care_density, m.fairness_density, m.loyalty_density, m.authority_density, m.sanctity_density
            FROM articles a
            JOIN article_nlp_metrics m ON a.id = m.article_id
            WHERE a.publish_date >= ? AND a.publish_date <= ?
        """
        params_pre = [pre_start, pre_end]
        params_post = [post_start, post_end]

        if query:
            sql_base += " AND a.id IN (SELECT id FROM articles_fts WHERE articles_fts MATCH ?)"
            params_pre.append(query)
            params_post.append(query)

        cur = conn.cursor()
        cur.execute(sql_base, params_pre)
        pre_articles = [dict(r) for r in cur.fetchall()]

        cur.execute(sql_base, params_post)
        post_articles = [dict(r) for r in cur.fetchall()]
        conn.close()

        pre_df = pd.DataFrame(pre_articles)
        post_df = pd.DataFrame(post_articles)

        # Baseline metrics
        pre_count = len(pre_df)
        post_count = len(post_df)
        pct_surge = ((post_count - pre_count) / pre_count * 100.0) if pre_count > 0 else 0.0

        pre_sent = float(pre_df["net_sentiment"].mean()) if pre_count > 0 else 0.0
        post_sent = float(post_df["net_sentiment"].mean()) if post_count > 0 else 0.0
        delta_sent = post_sent - pre_sent

        # Moral vectors
        pre_moral = {k: float(pre_df[f"{k}_density"].mean()) if pre_count > 0 else 0.0 for k in FOUNDATION_KEYS}
        post_moral = {k: float(post_df[f"{k}_density"].mean()) if post_count > 0 else 0.0 for k in FOUNDATION_KEYS}

        divergence = compute_moral_divergence(post_moral, pre_moral)

        # Top distinctive terms post-event
        pre_texts = pre_df["full_text"].tolist() if pre_count > 0 else []
        post_texts = post_df["full_text"].tolist() if post_count > 0 else []
        keyness_df = compute_dunning_keyness(post_texts, pre_texts, min_freq=3, top_n=15)

        return {
            "event_date": event_date_str,
            "window_days": window_days,
            "pre_period": f"{pre_start} to {pre_end}",
            "post_period": f"{post_start} to {post_end}",
            "pre_count": pre_count,
            "post_count": post_count,
            "pct_surge": round(pct_surge, 1),
            "pre_sentiment": round(pre_sent, 3),
            "post_sentiment": round(post_sent, 3),
            "delta_sentiment": round(delta_sent, 3),
            "moral_divergence": divergence,
            "pre_moral": pre_moral,
            "post_moral": post_moral,
            "keyness_df": keyness_df,
            "pre_articles": pre_articles,
            "post_articles": post_articles
        }

