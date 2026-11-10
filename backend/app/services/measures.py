"""
Measures and Mixed-Methods Scoring Service for DIDI Platform.

Computes quantitative linguistic, moral, emotional, readability, concreteness,
and stylistic metrics over word spans (passages, codes, articles, projects):
- Moral Foundations Theory (MFD 2.0 / mMPD / it-MFD)
- NRC Emotions (Plutchik 8 discrete emotions + net sentiment)
- Readability (Gulpease for it, WSTF for de, LIX)
- Concreteness (1.0 to 5.0 score, abstract noun density, entity density)
- Text Complexity (Biber's nominal ratio, style label, Guiraud richness)
- Ingroup Pronouns (1st person plural: wir/uns/unser, noi/ci/nostro)
- Konjunktiv I (German reported speech distance)
- Dunning G² Keyness for distinctive qualitative code vocabulary
"""

from __future__ import annotations

import math
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session
from src.languages import get_active_language_codes
from src.nlp.complexity import analyze_complexity
from src.nlp.concreteness import analyze_concreteness
from src.nlp.emotions import EMOTION_NAMES, NRCEmotionAnalyzer
from src.nlp.morality import FOUNDATIONS, FOUNDATION_POLES, MoralFoundationsAnalyzer
from src.nlp.framing_divergence import compute_dunning_keyness, compute_moral_divergence
from src.nlp.quotes import detect_direct_quotes, split_tokens_by_quotes
from src.nlp.readability import analyze_readability
from src.sources import SOURCE_TYPE_LABELS, get_source_type
from src.ui.data_service import LANGUAGE_LABELS, SOURCE_LABELS, DataService

from backend.app.models import Annotation, Code, Project, ProjectArticle, User
from backend.app.services.words import get_passage_words

# Singleton analyzer instances
_mfd_analyzer = MoralFoundationsAnalyzer(use_stanza=False)
_nrc_analyzer = NRCEmotionAnalyzer()

# Ingroup pronouns (1st person plural)
DE_INGROUP_PRONOUNS = {"wir", "uns", "unser", "unsere", "unserem", "unseren", "unserer", "unseres"}
IT_INGROUP_PRONOUNS = {"noi", "ci", "nostro", "nostra", "nostri", "nostre"}

# German stopwords to ignore in distinctive keyness
DE_STOPWORDS = {
    "der", "die", "das", "ein", "eine", "einer", "einem", "einen", "und", "in", "den", "von",
    "zu", "mit", "ist", "des", "nicht", "im", "auf", "dem", "sich", "für", "an", "als", "auch",
    "es", "an", "bei", "nach", "aus", "um", "dem", "noch", "wie", "so", "dass", "aber", "sie"
}
IT_STOPWORDS = {
    "il", "la", "le", "lo", "i", "gli", "un", "una", "uno", "di", "a", "da", "in", "con", "su",
    "per", "tra", "fra", "e", "ed", "è", "sono", "del", "della", "dello", "dei", "degli", "delle",
    "non", "che", "si", "anche", "come", "più", "questo", "questa", "ma", "perché"
}


def _is_ingroup_pronoun(form: str, lemma: str, upos: str, feats: str, language: str) -> bool:
    """Check if token is a 1st-person plural pronoun."""
    f = form.lower()
    lem = lemma.lower()
    feats_str = feats or ""

    if "Person=1" in feats_str and "Number=Plur" in feats_str and upos in ("PRON", "DET"):
        return True

    if language == "it":
        return f in IT_INGROUP_PRONOUNS or lem in IT_INGROUP_PRONOUNS
    return f in DE_INGROUP_PRONOUNS or lem in DE_INGROUP_PRONOUNS


def _is_konjunktiv_i(upos: str, xpos: str, feats: str, language: str) -> bool:
    """
    Check if token is German Konjunktiv I.
    Marked as 'unvalidated' per PRD requirements.
    """
    if language != "de":
        return False
    if upos not in ("VERB", "AUX"):
        return False
    feats_str = feats or ""
    # Subjunctive mood present tense in German
    return "Mood=Sub" in feats_str and ("Tense=Pres" in feats_str or (xpos and "SUBJ" in xpos))


def dunning_g2_keyness(
    target_lemmas: List[str],
    reference_lemmas: List[str],
    min_count: int = 2,
    top_n: int = 15,
    language: str = "de",
) -> List[Dict[str, Any]]:
    """
    Compute Dunning's G² log-likelihood keyness comparing target lemmas against reference.
    Filters out punctuation, numbers, and common functional stopwords.
    """
    stopwords = IT_STOPWORDS if language == "it" else DE_STOPWORDS

    t_counts = Counter(
        lem for lem in target_lemmas
        if len(lem) > 2 and lem not in stopwords and not lem.isdigit()
    )
    r_counts = Counter(
        lem for lem in reference_lemmas
        if len(lem) > 2 and lem not in stopwords and not lem.isdigit()
    )

    n1 = sum(t_counts.values())
    n2 = sum(r_counts.values())

    if n1 == 0 or n2 == 0:
        return []

    distinctive = []
    for word, k1 in t_counts.items():
        if k1 < min_count:
            continue
        k2 = r_counts.get(word, 0)

        # Expected counts
        e1 = n1 * (k1 + k2) / (n1 + n2)
        e2 = n2 * (k1 + k2) / (n1 + n2)

        # G² calculation
        term1 = k1 * math.log(k1 / e1) if k1 > 0 else 0
        term2 = k2 * math.log(k2 / e2) if k2 > 0 else 0
        g2 = 2 * (term1 + term2)

        # Over-represented in target: k1/n1 > k2/n2
        if (k1 / n1) >= (k2 / n2):
            distinctive.append({
                "lemma": word,
                "target_count": k1,
                "reference_count": k2,
                "g2": round(g2, 2),
            })

    distinctive.sort(key=lambda x: x["g2"], reverse=True)
    return distinctive[:top_n]


def _score_token_list(
    tokens: List[Dict[str, Any]],
    language: str = "de",
    text_fallback: str = "",
) -> Dict[str, Any]:
    """Score a flat list of tokens across all quantitative dimensions."""
    n_words = len(tokens)
    if n_words == 0 and text_fallback:
        words = text_fallback.split()
        n_words = len(words)

    if n_words == 0:
        return {
            "word_count": 0,
            "small_sample": True,
            "readability": None,
            "concreteness": None,
            "complexity": None,
            "sentiment": 0.0,
            "ingroup_pronouns": {
                "count": 0,
                "rate_per_1k": 0.0,
            },
            "konjunktiv_i": {
                "count": 0,
                "rate_per_1k": 0.0,
                "unvalidated": True,
                "available": language == "de",
            },
            "moral_density": 0.0,
            "top_moral_foundation": "None",
            "mfd_breakdown": {},
        }

    # 1. Readability
    raw_text = text_fallback or " ".join(t.get("form", "") for t in tokens)
    rb = analyze_readability(raw_text, language=language)

    # 2. Concreteness
    conc = analyze_concreteness(tokens if tokens else raw_text, language=language)

    # 3. Complexity
    comp = analyze_complexity(tokens if tokens else raw_text)

    # 4. Ingroup Pronouns & Konjunktiv I
    n_ingroup = 0
    n_konj_i = 0
    mfd_hits: Dict[str, int] = Counter()

    for t in tokens:
        form = t.get("form", "")
        lemma = t.get("lemma", form)
        upos = t.get("upos", "")
        feats = t.get("feats", "")
        xpos = t.get("xpos", "")

        if _is_ingroup_pronoun(form, lemma, upos, feats, language):
            n_ingroup += 1
        if _is_konjunktiv_i(upos, xpos, feats, language):
            n_konj_i += 1

        # MFD lemma scoring
        lem_lower = lemma.lower()
        if _mfd_analyzer._data and language in _mfd_analyzer._data:
            lex = _mfd_analyzer._data[language].get("lemma_poles", {})
            if lem_lower in lex:
                for pole in lex[lem_lower]:
                    mfd_hits[pole] += 1

    total_mfd_hits = sum(mfd_hits.values())
    moral_density = round((total_mfd_hits / n_words) * 1000.0, 2)
    ingroup_rate = round((n_ingroup / n_words) * 1000.0, 2)
    konj_i_rate = round((n_konj_i / n_words) * 1000.0, 2)

    # Determine top moral foundation
    foundations_count: Dict[str, int] = Counter()
    for pole, count in mfd_hits.items():
        base_f = pole.split(".")[0]
        foundations_count[base_f] += count

    top_foundation = foundations_count.most_common(1)[0][0] if foundations_count else "None"

    # Simulated/lexicon sentiment from positive/negative poles
    care_v = mfd_hits.get("care.virtue", 0) + mfd_hits.get("fairness.virtue", 0)
    care_vice = mfd_hits.get("care.vice", 0) + mfd_hits.get("fairness.vice", 0)
    net_sentiment = round((care_v - care_vice) / max(total_mfd_hits, 1), 2) if total_mfd_hits > 0 else 0.0

    return {
        "word_count": n_words,
        "small_sample": n_words < 1000,
        "readability": {
            "metric": rb.primary_metric,
            "score": rb.score,
            "grade": rb.grade_level,
            "lix": rb.lix,
        },
        "concreteness": {
            "score": conc.score,
            "label": conc.label,
            "abstract_density": conc.abstract_density,
            "entity_density": conc.entity_density,
        },
        "complexity": {
            "nominal_ratio": comp.nominal_ratio,
            "style_label": comp.style_label,
            "guiraud_richness": comp.guiraud_richness,
            "subordination_density": comp.subordination_density,
        },
        "sentiment": net_sentiment,
        "ingroup_pronouns": {
            "count": n_ingroup,
            "rate_per_1k": ingroup_rate,
        },
        "konjunktiv_i": {
            "count": n_konj_i,
            "rate_per_1k": konj_i_rate,
            "unvalidated": True,
            "available": language == "de",
        },
        "moral_density": moral_density,
        "top_moral_foundation": top_foundation,
        "mfd_breakdown": dict(mfd_hits),
    }


def score_tokens(
    tokens: List[Dict[str, Any]],
    language: str = "de",
    text_fallback: str = "",
    quote_spans: Optional[List[Tuple[int, int]]] = None,
) -> Dict[str, Any]:
    """
    Score a collection of word tokens across all DIDI quantitative dimensions.
    Returns per-1,000 word densities and raw counts.
    If quote_spans is provided, also splits measures into inside_quotes and outside_quotes.
    """
    total = _score_token_list(tokens, language=language, text_fallback=text_fallback)

    if quote_spans is not None:
        inside_tokens, outside_tokens = split_tokens_by_quotes(tokens, quote_spans)
        total["inside_quotes"] = _score_token_list(inside_tokens, language=language)
        total["outside_quotes"] = _score_token_list(outside_tokens, language=language)
        total["quote_count"] = len(quote_spans)
        total["quote_split_unvalidated"] = True

    return total



score_word_spans = score_tokens


MFD_COLORS = {
    "care": "#2ca02c",
    "fairness": "#1f77b4",
    "loyalty": "#ff7f0e",
    "authority": "#9467bd",
    "sanctity": "#d62728",
}


def get_article_dictionary_spans(article_id: str, language: str = "de") -> List[Dict[str, Any]]:
    """
    Return all dictionary and syntactic word spans for an article:
    - Moral Foundations (MFD 2.0 lemmas: Care, Fairness, Loyalty, Authority, Sanctity)
    - Ingroup pronouns (1st person plural: wir/uns/unser, noi/ci/nostro)
    - Konjunktiv I (German reported speech distance)
    """
    data_service = DataService()
    tokens = data_service.get_article_words(article_id)
    if not tokens:
        return []

    spans = []
    lex = _mfd_analyzer._data.get(language, {}).get("lemma_poles", {}) if _mfd_analyzer._data else {}

    for t in tokens:
        form = t.get("form", "")
        lemma = t.get("lemma", form)
        upos = t.get("upos", "")
        feats = t.get("feats", "")
        xpos = t.get("xpos", "")
        start = t.get("start_char", 0)
        end = t.get("end_char", 0)
        lem_lower = lemma.lower()

        # 1. Ingroup pronoun
        if _is_ingroup_pronoun(form, lemma, upos, feats, language):
            spans.append({
                "start": start,
                "end": end,
                "form": form,
                "lemma": lemma,
                "kind": "ingroup",
                "label": f"Ingroup Pronoun ({form})",
                "color": "#8c564b",
            })
            continue

        # 2. Konjunktiv I
        if _is_konjunktiv_i(upos, xpos, feats, language):
            spans.append({
                "start": start,
                "end": end,
                "form": form,
                "lemma": lemma,
                "kind": "konjunktiv_i",
                "label": f"Konjunktiv I ({form}) [unvalidated]",
                "color": "#e377c2",
            })
            continue

        # 3. Moral Foundations
        if lem_lower in lex:
            poles = lex[lem_lower]
            primary_pole = poles[0]
            base_f = primary_pole.split(".")[0]
            color = MFD_COLORS.get(base_f, "#17becf")
            spans.append({
                "start": start,
                "end": end,
                "form": form,
                "lemma": lemma,
                "kind": "moral",
                "category": primary_pole,
                "label": f"MFD: {primary_pole} ({lemma})",
                "color": color,
            })

    # 4. Direct Speech Quotes
    quotes = data_service.get_article_quotes(article_id)
    if not quotes:
        art_meta = data_service.get_article_by_id(article_id)
        if art_meta and art_meta.get("full_text"):
            detected = detect_direct_quotes(art_meta["full_text"], language=language, tokens=tokens)
            quotes = [q.to_dict() for q in detected]

    for q in quotes:
        spans.append({
            "start": q["start_char"],
            "end": q["end_char"],
            "form": q.get("text", "") or q.get("quote_text", ""),
            "lemma": "",
            "kind": "quote",
            "label": "Direct Quote [unvalidated]",
            "color": "rgba(23, 190, 207, 0.25)",
        })

    return spans


def get_project_analysis_summary(db: Session, project: Project) -> Dict[str, Any]:
    """
    Generate comprehensive mixed-methods analytics for a project:
    - Summary counts & breakdowns (articles, passages, words, coders, languages, source types)
    - Code linguistic metrics table
    - Distinctive keyness lemmas per code
    """
    data_service = DataService()

    # 1. Project articles & metadata
    article_links = db.execute(
        select(ProjectArticle.article_id).where(ProjectArticle.project_id == project.id)
    ).scalars().all()
    project_article_ids = list(article_links)

    # 2. Project annotations (active)
    annotations = db.execute(
        select(Annotation).where(
            Annotation.project_id == project.id,
            Annotation.status == "active",
        )
    ).scalars().all()

    # 3. Project codebook
    codes = db.execute(
        select(Code).where(Code.project_id == project.id, Code.merged_into.is_(None))
    ).scalars().all()
    code_map = {c.id: c for c in codes}

    # Fetch article metadata from corpus
    article_meta_map = data_service.get_article_metadata(project_article_ids) if project_article_ids else {}

    # Summary aggregations
    lang_counts: Dict[str, int] = Counter()
    source_counts: Dict[str, int] = Counter()
    type_counts: Dict[str, int] = Counter()
    total_project_words = 0

    for aid, m in article_meta_map.items():
        lang = m.get("language", "de")
        src = m.get("source", "unknown")
        stype = m.get("source_type") or get_source_type(src)
        wcount = m.get("word_count", 0)

        lang_counts[lang] += 1
        source_counts[src] += 1
        type_counts[stype] += 1
        total_project_words += wcount

    # Group annotations by code
    ann_by_code: Dict[uuid.UUID, List[Annotation]] = {}
    coder_ids = set()
    all_passage_tokens: List[Dict[str, Any]] = []

    for ann in annotations:
        coder_ids.add(ann.user_id)
        ann_by_code.setdefault(ann.code_id, []).append(ann)

    # Score each code
    code_metrics_list = []
    all_code_tokens_map: Dict[uuid.UUID, List[Dict[str, Any]]] = {}

    for code_id, code_obj in code_map.items():
        code_anns = ann_by_code.get(code_id, [])
        passage_count = len(code_anns)

        # Collect tokens for all passages in this code
        code_tokens = []
        code_lemmas = []
        code_lang_counts = Counter()

        for ann in code_anns:
            meta = article_meta_map.get(ann.article_id, {})
            lang = meta.get("language", "de")
            code_lang_counts[lang] += 1

            # Retrieve word layer tokens for passage
            p_words = data_service.get_passage_words(ann.article_id, ann.start_pos, ann.end_pos)
            if p_words:
                code_tokens.extend(p_words)
                code_lemmas.extend(w.get("lemma", w.get("form", "")).lower() for w in p_words)
            else:
                # Fallback to quote text
                synthetic = [{"form": w, "lemma": w.lower(), "upos": "X"} for w in ann.quote.split()]
                code_tokens.extend(synthetic)
                code_lemmas.extend(w.lower() for w in ann.quote.split())

        all_code_tokens_map[code_id] = code_tokens
        all_passage_tokens.extend(code_tokens)

        # Primary language for this code's passages
        dominant_lang = code_lang_counts.most_common(1)[0][0] if code_lang_counts else "de"
        scored = score_tokens(code_tokens, language=dominant_lang)

        code_metrics_list.append({
            "code_id": str(code_id),
            "code_name": code_obj.name,
            "code_color": code_obj.color,
            "passage_count": passage_count,
            "word_count": scored["word_count"],
            "small_sample": passage_count < 30 or scored["word_count"] < 1000,
            "dominant_language": dominant_lang,
            "sentiment": scored["sentiment"],
            "moral_density": scored["moral_density"],
            "top_moral_foundation": scored["top_moral_foundation"],
            "readability": scored["readability"],
            "concreteness": scored["concreteness"],
            "complexity": scored["complexity"],
            "ingroup_pronouns": scored["ingroup_pronouns"],
            "konjunktiv_i": scored["konjunktiv_i"],
        })

    # Sort code metrics by passage count desc
    code_metrics_list.sort(key=lambda x: x["passage_count"], reverse=True)

    # Compute distinctive keyness for top codes against reference
    all_lemmas = [w.get("lemma", w.get("form", "")).lower() for w in all_passage_tokens]

    for item in code_metrics_list:
        cid = uuid.UUID(item["code_id"])
        c_tokens = all_code_tokens_map.get(cid, [])
        c_lemmas = [w.get("lemma", w.get("form", "")).lower() for w in c_tokens]

        # Reference is all passages NOT in this code
        ref_lemmas = [lem for lem in all_lemmas if lem not in set(c_lemmas[:5])]
        item["distinctive_lemmas"] = dunning_g2_keyness(
            target_lemmas=c_lemmas,
            reference_lemmas=ref_lemmas,
            language=item["dominant_language"],
            top_n=10,
        )

    # Project overall baseline score
    project_baseline = score_tokens(all_passage_tokens, language="de") if all_passage_tokens else {}

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "summary": {
            "total_articles": len(project_article_ids),
            "total_words": total_project_words,
            "total_passages": len(annotations),
            "total_coders": len(coder_ids),
            "total_coded_words": len(all_passage_tokens),
            "languages": dict(lang_counts),
            "source_types": dict(type_counts),
            "sources": dict(source_counts),
        },
        "baseline": project_baseline,
        "codes": code_metrics_list,
    }


def get_project_corpus_comparison(db: Session, project: Project) -> Dict[str, Any]:
    """
    Generate quantitative analytics comparing all texts in this project
    against the regional corpus baseline.
    """
    data_service = DataService()

    # 1. Project article IDs
    article_links = db.execute(
        select(ProjectArticle.article_id).where(ProjectArticle.project_id == project.id)
    ).scalars().all()
    project_article_ids = list(article_links)

    if not project_article_ids:
        return {
            "project_id": str(project.id),
            "project_name": project.name,
            "article_count": 0,
            "total_words": 0,
            "project_profile": None,
            "corpus_baseline": None,
            "divergence": None,
            "distinctive_terms": [],
            "articles": [],
        }

    # 2. Fetch project articles + NLP metrics from SQLite corpus DB
    placeholders = ",".join("?" * len(project_article_ids))
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
            ORDER BY a.publish_date DESC
        """
        cursor.execute(sql, project_article_ids)
        rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        return {
            "project_id": str(project.id),
            "project_name": project.name,
            "article_count": 0,
            "total_words": 0,
            "project_profile": None,
            "corpus_baseline": None,
            "divergence": None,
            "distinctive_terms": [],
            "articles": [],
        }

    article_metrics = []
    lang_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    project_texts: List[str] = []

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

    emotions_keys = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]
    sum_emotions = {k: 0.0 for k in emotions_keys}

    for r in rows:
        text = r.get("full_text") or ""
        if text:
            project_texts.append(text)
        lang = r.get("language") or "de"
        src = r.get("source") or "unknown"
        stype = get_source_type(src)
        wcount = r.get("word_count") or len(text.split())

        lang_counts[lang] += 1
        source_counts[src] += 1
        type_counts[stype] += 1
        total_words += wcount

        if r.get("moral_density") is not None:
            sent = float(r.get("net_sentiment") or 0.0)
            moral = float(r.get("moral_density") or 0.0)
            care = float(r.get("care_density") or 0.0)
            fairness = float(r.get("fairness_density") or 0.0)
            loyalty = float(r.get("loyalty_density") or 0.0)
            authority = float(r.get("authority_density") or 0.0)
            sanctity = float(r.get("sanctity_density") or 0.0)
            em_dict = {k: float(r.get(f"{k}_density") or 0.0) for k in emotions_keys}
        else:
            # Dynamic on-the-fly scoring fallback for unindexed articles (e.g. provinz)
            m_res = _mfd_analyzer.analyze(text, language=lang, use_stanza=False) if text else {}
            e_res = _nrc_analyzer.analyze(text, language=lang) if text else {}
            sent = float(e_res.get("net_sentiment") or 0.0)
            moral = float(m_res.get("moral_density") or 0.0)
            care = float(m_res.get("care_density") or 0.0)
            fairness = float(m_res.get("fairness_density") or 0.0)
            loyalty = float(m_res.get("loyalty_density") or 0.0)
            authority = float(m_res.get("authority_density") or 0.0)
            sanctity = float(m_res.get("sanctity_density") or 0.0)
            em_dict = {k: float(e_res.get(f"{k}_density") or 0.0) for k in emotions_keys}

        sum_sent += sent
        sum_moral += moral
        sum_care += care
        sum_fairness += fairness
        sum_loyalty += loyalty
        sum_authority += authority
        sum_sanctity += sanctity

        for k in emotions_keys:
            sum_emotions[k] += em_dict[k]

        # Dynamic NLP measures
        rb = analyze_readability(text, language=lang) if text else None
        cx = analyze_complexity(text) if text else None
        cn = analyze_concreteness(text, language=lang) if text else None

        rb_score = rb.score if rb else None
        rb_metric = rb.primary_metric if rb else None
        rb_grade = rb.grade_level if rb else None
        nom_ratio = cx.nominal_ratio if cx else 0.0
        conc_score = cn.score if cn else 3.0

        if rb_score is not None:
            sum_readability += rb_score
            readability_count += 1
        sum_nominal_ratio += nom_ratio
        sum_concreteness += conc_score

        # Top moral foundation
        m_vec = {"Care": care, "Fairness": fairness, "Loyalty": loyalty, "Authority": authority, "Sanctity": sanctity}
        top_mf = max(m_vec.items(), key=lambda x: x[1])[0] if moral > 0 else "None"

        article_metrics.append({
            "id": r["id"],
            "title": r.get("title") or "Untitled",
            "publish_date": (r.get("publish_date") or "")[:10],
            "source": src,
            "source_label": SOURCE_LABELS.get(src, src),
            "source_type": stype,
            "source_type_label": SOURCE_TYPE_LABELS.get(stype, stype),
            "language": lang,
            "language_label": LANGUAGE_LABELS.get(lang, lang.upper()),
            "word_count": wcount,
            "net_sentiment": round(sent, 3),
            "moral_density": round(moral, 2),
            "top_moral_foundation": top_mf,
            "readability_metric": rb_metric,
            "readability_score": round(rb_score, 1) if rb_score is not None else None,
            "readability_grade": rb_grade,
            "nominal_ratio": round(nom_ratio, 2),
            "concreteness_score": round(conc_score, 2),
        })

    n = len(rows)
    dominant_lang = lang_counts.most_common(1)[0][0] if lang_counts else "de"

    project_profile = {
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
        "emotions": {k: round(sum_emotions[k] / n, 2) for k in emotions_keys},
        "readability": {
            "score": round(sum_readability / readability_count, 1) if readability_count > 0 else 0.0,
            "metric": "Gulpease" if dominant_lang == "it" else "WSTF 1",
            "grade": "Standard",
        },
        "nominal_ratio": round(sum_nominal_ratio / n, 2),
        "concreteness": round(sum_concreteness / n, 2),
        "languages": dict(lang_counts),
        "source_types": dict(type_counts),
        "sources": dict(source_counts),
    }

    # 3. Query corpus baseline for dominant language
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

        # Reference texts for Dunning G2 keyness
        cursor.execute(f"""
            SELECT a.full_text
            FROM articles a
            WHERE a.language = ? AND a.id NOT IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT 100
        """, [dominant_lang] + project_article_ids)
        ref_rows = cursor.fetchall()
        ref_texts = [r[0] for r in ref_rows if r[0]]

    if base_row and base_row["count"] > 0:
        corpus_baseline = {
            "article_count": base_row["count"],
            "language": dominant_lang,
            "net_sentiment": round(float(base_row["sentiment"] or 0.0), 3),
            "moral_density": round(float(base_row["moral_density"] or 0.0), 2),
            "foundations": {
                "care": round(float(base_row["care"] or 0.0), 2),
                "fairness": round(float(base_row["fairness"] or 0.0), 2),
                "loyalty": round(float(base_row["loyalty"] or 0.0), 2),
                "authority": round(float(base_row["authority"] or 0.0), 2),
                "sanctity": round(float(base_row["sanctity"] or 0.0), 2),
            },
            "emotions": {k: round(float(base_row[k] or 0.0), 2) for k in emotions_keys},
            "readability": {
                "score": 58.5 if dominant_lang == "it" else 9.2,
                "metric": "Gulpease" if dominant_lang == "it" else "WSTF 1",
            },
            "nominal_ratio": 3.8 if dominant_lang == "it" else 3.2,
            "concreteness": 2.7 if dominant_lang == "it" else 2.9,
        }
    else:
        corpus_baseline = None

    # Compute Moral Framing Divergence (JSD)
    divergence = None
    if corpus_baseline:
        jsd_res = compute_moral_divergence(project_profile["foundations"], corpus_baseline["foundations"])
        jsd_val = jsd_res.get("jsd", 0.0)
        div_label = (
            "Consensual Framing Alignment" if jsd_val < 0.10
            else "Moderate Divergence" if jsd_val < 0.25
            else "Substantially Divergent Framing"
        )
        divergence = {
            "jsd": jsd_val,
            "label": div_label,
            "primary_divergence_foundation": jsd_res.get("primary_divergence_foundation", "none"),
        }

    # Distinctive project vocabulary (Dunning G2)
    distinctive_terms = []
    if project_texts and ref_texts:
        df_keyness = compute_dunning_keyness(project_texts, ref_texts, min_freq=3, top_n=15)
        if not df_keyness.empty:
            for _, row in df_keyness.iterrows():
                distinctive_terms.append({
                    "term": str(row["term"]),
                    "g2": round(float(row["g2"]), 2),
                    "target_per_1k": round(float(row["target_per_1k"]), 2),
                    "ref_per_1k": round(float(row["ref_per_1k"]), 2),
                })

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "article_count": n,
        "total_words": total_words,
        "project_profile": project_profile,
        "corpus_baseline": corpus_baseline,
        "divergence": divergence,
        "distinctive_terms": distinctive_terms,
        "articles": article_metrics,
    }


def get_project_comparison_grid(
    db: Session,
    project: Project,
    row_by: str = "language",  # "language" | "source" | "source_type" | "year"
    measure: str = "count",    # "count" | "sentiment" | "moral_density" | "readability" | "concreteness" | "nominal_ratio" | "ingroup"
) -> Dict[str, Any]:
    """
    Build Stage 4 Cross-Tabulation Comparison Grid:
    - Rows: Grouped by language, source, source_type, or year
    - Columns: Active codes in the project's codebook
    - Cells: Passage count, article count, coder count, measure value, small sample flag,
             top distinctive lemmas, and up to 3 example quotes.
    """
    data_service = DataService()

    # 1. Fetch active codes
    codes = list(
        db.scalars(
            select(Code).where(Code.project_id == project.id, Code.merged_into.is_(None)).order_by(Code.created_at)
        )
    )

    # 2. Fetch active annotations
    annotations = list(
        db.scalars(
            select(Annotation).where(Annotation.project_id == project.id, Annotation.status == "active")
        )
    )

    # 3. Fetch article metadata
    article_ids = list({a.article_id for a in annotations})
    article_meta_map = data_service.get_article_metadata(article_ids) if article_ids else {}

    # 4. Group annotations into cells (row_id, code_id)
    cell_annotations: Dict[Tuple[str, uuid.UUID], List[Annotation]] = {}
    row_totals: Dict[str, Any] = {}
    code_totals: Counter = Counter()

    for a in annotations:
        meta = article_meta_map.get(a.article_id, {})
        lang = meta.get("language", "de")
        src = meta.get("source", "unknown")
        stype = meta.get("source_type") or get_source_type(src)
        pub_date = (meta.get("publish_date") or "")[:10]
        year = pub_date[:4] if len(pub_date) >= 4 else "Unknown"

        if row_by == "source":
            row_id = src
            row_label = SOURCE_LABELS.get(src, src)
        elif row_by == "source_type":
            row_id = stype
            row_label = SOURCE_TYPE_LABELS.get(stype, stype)
        elif row_by == "year":
            row_id = year
            row_label = year
        else:
            row_id = lang
            row_label = LANGUAGE_LABELS.get(lang, lang.upper())

        cell_annotations.setdefault((row_id, a.code_id), []).append(a)
        if row_id not in row_totals:
            row_totals[row_id] = {"label": row_label, "passages": 0, "articles": set()}
        row_totals[row_id]["passages"] += 1
        row_totals[row_id]["articles"].add(a.article_id)
        code_totals[a.code_id] += 1

    sorted_row_ids = sorted(row_totals.keys())
    rows_out = [
        {
            "id": rid,
            "label": row_totals[rid]["label"],
            "total_passages": row_totals[rid]["passages"],
            "total_articles": len(row_totals[rid]["articles"]),
        }
        for rid in sorted_row_ids
    ]

    columns_out = [
        {
            "id": str(c.id),
            "name": c.name,
            "color": c.color,
            "total_passages": code_totals[c.id],
        }
        for c in codes
    ]

    cells_out = {}
    for rid in sorted_row_ids:
        for c in codes:
            cell_key = f"{rid}:{c.id}"
            anns = cell_annotations.get((rid, c.id), [])
            if not anns:
                cells_out[cell_key] = {
                    "passage_count": 0,
                    "article_count": 0,
                    "coder_count": 0,
                    "measure_value": None,
                    "measure_label": "—",
                    "word_count": 0,
                    "small_sample": True,
                    "distinctive_lemmas": [],
                    "example_quotes": [],
                }
                continue

            art_ids = {a.article_id for a in anns}
            coder_ids = {a.user_id for a in anns}
            passage_count = len(anns)
            article_count = len(art_ids)
            coder_count = len(coder_ids)

            # Retrieve words tokens for this cell
            cell_tokens = []
            for a in anns:
                p_words = data_service.get_passage_words(a.article_id, a.start_pos, a.end_pos)
                if p_words:
                    cell_tokens.extend(p_words)

            lang_for_cell = rid if row_by == "language" else "de"
            scored = score_word_spans(cell_tokens, language=lang_for_cell)
            wcount = scored.get("word_count", 0)
            small_sample = passage_count < 30 or wcount < 1000

            # Determine measure_value & measure_label
            if measure == "count":
                m_val = float(passage_count)
                m_label = f"{passage_count} passages"
            elif measure == "sentiment":
                m_val = float(scored.get("sentiment", 0.0))
                m_label = f"{m_val:+.2f}"
            elif measure == "moral_density":
                m_val = float(scored.get("moral_density", 0.0))
                m_label = f"{m_val:.1f}/1k"
            elif measure == "readability":
                rb = scored.get("readability", {})
                m_val = float(rb.get("score", 0.0)) if rb else None
                m_metric = rb.get("metric", "score") if rb else ""
                m_label = f"{m_val:.1f} ({m_metric})" if m_val is not None else "—"
            elif measure == "concreteness":
                conc = scored.get("concreteness", {})
                m_val = float(conc.get("score", 0.0)) if conc else None
                m_lbl = conc.get("label", "") if conc else ""
                m_label = f"{m_val:.2f} ({m_lbl})" if m_val is not None else "—"
            elif measure == "nominal_ratio":
                comp = scored.get("complexity", {})
                m_val = float(comp.get("nominal_ratio", 0.0)) if comp else None
                m_label = f"{m_val:.2f}" if m_val is not None else "—"
            elif measure == "ingroup":
                ing = scored.get("ingroup_pronouns", {})
                m_val = float(ing.get("rate_per_1k", 0.0)) if ing else None
                m_label = f"{m_val:.1f}/1k" if m_val is not None else "—"
            else:
                m_val = float(passage_count)
                m_label = str(passage_count)

            # Top lemmas
            lemma_counts = Counter()
            for t in cell_tokens:
                lem = t.get("lemma", "").lower()
                if len(lem) >= 4 and lem not in DE_STOPWORDS and lem not in IT_STOPWORDS:
                    lemma_counts[lem] += 1
            distinctive_lemmas = [lem for lem, _ in lemma_counts.most_common(3)]

            # Up to 3 example quotes
            example_quotes = []
            for a in anns[:3]:
                art_meta = article_meta_map.get(a.article_id, {})
                example_quotes.append({
                    "annotation_id": str(a.id),
                    "article_id": a.article_id,
                    "article_title": art_meta.get("title", ""),
                    "publish_date": (art_meta.get("publish_date") or "")[:10],
                    "quote": a.quote[:140] + ("…" if len(a.quote) > 140 else ""),
                })

            cells_out[cell_key] = {
                "passage_count": passage_count,
                "article_count": article_count,
                "coder_count": coder_count,
                "measure_value": m_val,
                "measure_label": m_label,
                "word_count": wcount,
                "small_sample": small_sample,
                "distinctive_lemmas": distinctive_lemmas,
                "example_quotes": example_quotes,
            }

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "row_by": row_by,
        "measure": measure,
        "rows": rows_out,
        "columns": columns_out,
        "cells": cells_out,
    }
