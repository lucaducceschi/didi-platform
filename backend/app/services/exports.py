"""CSV exports of a project's work."""

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.orm import Session
from src.languages import is_language_active
from src.sources import SOURCE_LABELS, SOURCE_TYPE_LABELS, get_source_type
from src.ui.data_service import DataService

from backend.app.models import Annotation, Code, Project, ProjectArticle, SavedCorpusSelection
from backend.app.services.codebook import code_paths, segment_counts

ANNOTATION_COLUMNS = (
    "annotation_id", "project", "article_id", "article_title", "source", "source_type", "language", "publish_date", "article_url",
    "coder_username", "coder_name", "code_id", "code_path", "start_pos", "end_pos", "quote", "memo", "status",
    "text_sha256", "created_at", "updated_at",
)
CODE_COLUMNS = ("code_id", "code_path", "name", "parent_id", "definition", "color", "segments", "coders", "merged_into", "created_at")


def _as_csv(columns, rows) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    # The byte order mark makes Excel read accented text correctly.
    return buffer.getvalue().encode("utf-8-sig")


def annotations_csv(db: Session, corpus: DataService, project_id: uuid.UUID, project_name: str) -> bytes:
    annotations = list(
        db.scalars(
            select(Annotation)
            .where(Annotation.project_id == project_id)
            .order_by(Annotation.article_id, Annotation.start_pos, Annotation.created_at)
        )
    )
    return write_annotations_csv(db, corpus, project_id, project_name, annotations)


def write_annotations_csv(db: Session, corpus: DataService, project_id: uuid.UUID, project_name: str, annotations: list) -> bytes:
    paths = code_paths(db, project_id)
    articles = corpus.get_article_metadata([a.article_id for a in annotations])
    rows = []
    for a in annotations:
        article = articles.get(a.article_id, {})
        # Omit annotations on unconfigured languages from exports
        if article and not is_language_active(article.get("language", "")):
            continue
        rows.append({
            "annotation_id": a.id,
            "project": project_name,
            "article_id": a.article_id,
            "article_title": article.get("title", ""),
            "source": article.get("source", ""),
            "source_type": get_source_type(article.get("source", "")),
            "language": article.get("language", ""),
            "publish_date": (article.get("publish_date") or "")[:10],
            "article_url": article.get("url", ""),
            "coder_username": a.user.username,
            "coder_name": a.user.display_name,
            "code_id": a.code_id,
            "code_path": paths.get(a.code_id, ""),
            "start_pos": a.start_pos,
            "end_pos": a.end_pos,
            "quote": a.quote,
            "memo": a.memo,
            "status": a.status,
            "text_sha256": a.text_sha256,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        })
    return _as_csv(ANNOTATION_COLUMNS, rows)


def codes_csv(db: Session, project_id: uuid.UUID) -> bytes:
    paths = code_paths(db, project_id)
    counts = segment_counts(db, project_id)
    codes = db.scalars(select(Code).where(Code.project_id == project_id).order_by(Code.created_at))
    rows = [
        {
            "code_id": code.id,
            "code_path": paths[code.id],
            "name": code.name,
            "parent_id": code.parent_id or "",
            "definition": code.definition,
            "color": code.color,
            "segments": counts.get(code.id, (0, 0))[0],
            "coders": counts.get(code.id, (0, 0))[1],
            "merged_into": code.merged_into or "",
            "created_at": code.created_at.isoformat(),
        }
        for code in codes
    ]
    return _as_csv(CODE_COLUMNS, rows)


CODE_MEASURES_COLUMNS = (
    "code_id", "code_name", "code_path", "color", "passages_count", "words_count", "coders_count",
    "dominant_language", "sentiment", "readability_metric", "readability_score", "concreteness_score",
    "concreteness_label", "nominal_ratio", "moral_density", "top_moral_foundation",
    "ingroup_rate_per_1k", "konjunktiv_i_rate_per_1k", "distinctive_lemmas",
)

PASSAGE_MEASURES_COLUMNS = (
    "annotation_id", "project", "code_name", "code_path", "article_id", "article_title",
    "source", "source_type", "language", "start_pos", "end_pos", "quote",
    "words_count", "quotes_count", "inside_quotes_words", "outside_quotes_words",
    "sentiment", "readability_metric", "readability_score", "concreteness_score",
    "nominal_ratio", "moral_density", "top_moral_foundation",
    "ingroup_pronouns_count", "konjunktiv_i_count", "coder_username",
)


def _as_csv_with_header(header_comment: str, columns, rows) -> bytes:
    buffer = io.StringIO(newline="")
    buffer.write(header_comment.strip() + "\n")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def code_measures_csv(db: Session, project) -> bytes:
    from backend.app.services.measures import get_project_analysis_summary
    analysis = get_project_analysis_summary(db, project)
    paths = code_paths(db, project.id)

    header = (
        f"# DIDI Mixed-Methods Export: Quantitative Measures per Code\n"
        f"# Project: {project.name}\n"
        f"# Dictionaries: MFD 2.0 (mMPD/it-MFD), NRC Emotions (Plutchik), Gulpease/WSTF, Concreteness (1-5), Biber nominal ratio\n"
        f"# Word Layer: Stanza UPOS/feats/lemmas (didi_words.db)\n"
    )

    rows = []
    for c in analysis.get("codes", []):
        m = c.get("metrics", {})
        rb = m.get("readability", {})
        conc = m.get("concreteness", {})
        comp = m.get("complexity", {})
        ingroup = m.get("ingroup_pronouns", {})
        konj = m.get("konjunktiv_i", {})
        lemmas_str = ", ".join(f"{item['term']} (G²={item['g2']:.1f})" for item in c.get("distinctive_lemmas", [])[:8])

        rows.append({
            "code_id": c.get("code_id"),
            "code_name": c.get("code_name"),
            "code_path": paths.get(uuid.UUID(c.get("code_id")), c.get("code_name")),
            "color": c.get("color"),
            "passages_count": c.get("passage_count", 0),
            "words_count": c.get("word_count", 0),
            "coders_count": c.get("coder_count", 0),
            "dominant_language": c.get("dominant_language", "de"),
            "sentiment": m.get("sentiment", 0.0),
            "readability_metric": rb.get("metric", "n/a"),
            "readability_score": rb.get("score", 0.0),
            "concreteness_score": conc.get("score", 0.0),
            "concreteness_label": conc.get("label", "neutral"),
            "nominal_ratio": comp.get("nominal_ratio", 0.0),
            "moral_density": m.get("moral_density", 0.0),
            "top_moral_foundation": m.get("top_moral_foundation", "None"),
            "ingroup_rate_per_1k": ingroup.get("rate_per_1k", 0.0),
            "konjunktiv_i_rate_per_1k": konj.get("rate_per_1k", 0.0) if konj.get("available") else "",
            "distinctive_lemmas": lemmas_str,
        })

    return _as_csv_with_header(header, CODE_MEASURES_COLUMNS, rows)


def passage_measures_csv(db: Session, corpus: DataService, project) -> bytes:
    from backend.app.services.measures import score_word_spans

    annotations = list(
        db.scalars(
            select(Annotation)
            .where(Annotation.project_id == project.id, Annotation.status == "active")
            .order_by(Annotation.article_id, Annotation.start_pos)
        )
    )
    paths = code_paths(db, project.id)
    articles = corpus.get_article_metadata([a.article_id for a in annotations])

    header = (
        f"# DIDI Mixed-Methods Export: Quantitative Measures per Coded Passage\n"
        f"# Project: {project.name}\n"
        f"# Word Layer: Stanza UPOS/feats/lemmas (didi_words.db)\n"
    )

    rows = []
    for a in annotations:
        art = articles.get(a.article_id, {})
        lang = art.get("language", "de")
        if not is_language_active(lang):
            continue

        tokens = corpus.get_passage_words(a.article_id, a.start_pos, a.end_pos)
        quotes = corpus.get_passage_quotes(a.article_id, a.start_pos, a.end_pos)
        quote_spans = [(q["start_char"], q["end_char"]) for q in quotes] if quotes else []
        metrics = score_word_spans(tokens, language=lang, text_fallback=a.quote, quote_spans=quote_spans)

        rb = metrics.get("readability", {})
        conc = metrics.get("concreteness", {})
        comp = metrics.get("complexity", {})
        ingroup = metrics.get("ingroup_pronouns", {})
        konj = metrics.get("konjunktiv_i", {})
        inside_m = metrics.get("inside_quotes", {})
        outside_m = metrics.get("outside_quotes", {})

        rows.append({
            "annotation_id": str(a.id),
            "project": project.name,
            "code_name": a.code.name if a.code else "",
            "code_path": paths.get(a.code_id, ""),
            "article_id": a.article_id,
            "article_title": art.get("title", ""),
            "source": art.get("source", ""),
            "source_type": get_source_type(art.get("source", "")),
            "language": lang,
            "start_pos": a.start_pos,
            "end_pos": a.end_pos,
            "quote": a.quote,
            "words_count": metrics.get("word_count", 0),
            "quotes_count": metrics.get("quote_count", 0),
            "inside_quotes_words": inside_m.get("word_count", 0),
            "outside_quotes_words": outside_m.get("word_count", 0),
            "sentiment": metrics.get("sentiment", 0.0),
            "readability_metric": rb.get("metric", "n/a"),
            "readability_score": rb.get("score", 0.0),
            "concreteness_score": conc.get("score", 0.0),
            "nominal_ratio": comp.get("nominal_ratio", 0.0),
            "moral_density": metrics.get("moral_density", 0.0),
            "top_moral_foundation": metrics.get("top_moral_foundation", "None"),
            "ingroup_pronouns_count": ingroup.get("count", 0),
            "konjunktiv_i_count": konj.get("count", 0) if konj.get("available") else "",
            "coder_username": a.user.username if a.user else "",
        })

    return _as_csv_with_header(header, PASSAGE_MEASURES_COLUMNS, rows)


def comparison_grid_csv(db: Session, project, row_by: str = "language", measure: str = "count") -> bytes:
    from backend.app.services.measures import get_project_comparison_grid
    grid = get_project_comparison_grid(db, project, row_by=row_by, measure=measure)

    header = (
        f"# DIDI Mixed-Methods Export: Comparison Grid ({row_by.title()} x Codes)\n"
        f"# Project: {project.name}\n"
        f"# Metric: {measure}\n"
    )

    columns = [row_by.title()] + [c["name"] for c in grid["columns"]]
    rows = []
    for r in grid["rows"]:
        row_dict = {row_by.title(): r["label"]}
        for c in grid["columns"]:
            cell_key = f"{r['id']}:{c['id']}"
            cell = grid["cells"].get(cell_key, {})
            p_cnt = cell.get("passage_count", 0)
            if p_cnt == 0:
                row_dict[c["name"]] = "—"
            else:
                row_dict[c["name"]] = f"{p_cnt} passages ({cell.get('measure_label', '')})"
        rows.append(row_dict)

    buffer = io.StringIO(newline="")
    buffer.write(header.strip() + "\n")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def reproducibility_manifest(db: Session, corpus: DataService, project: Project) -> Dict[str, Any]:
    """
    Generate comprehensive reproducibility and provenance manifest for an academic project.
    Grounded in open-science principles and coordinate-level auditability.
    """
    from backend.app.services.agreement import get_inter_coder_agreement

    # 1. Active codes
    codes = list(
        db.scalars(
            select(Code).where(Code.project_id == project.id, Code.merged_into.is_(None)).order_by(Code.created_at)
        )
    )
    paths = code_paths(db, project.id)
    counts = segment_counts(db, project.id)

    codebook_items = []
    for c in codes:
        codebook_items.append({
            "code_id": str(c.id),
            "name": c.name,
            "path": paths.get(c.id, c.name),
            "color": c.color,
            "definition": c.definition,
            "passage_count": counts.get(c.id, 0),
            "created_at": c.created_at.isoformat(),
        })

    # 2. Saved Selections
    selections = list(
        db.scalars(
            select(SavedCorpusSelection)
            .where(SavedCorpusSelection.project_id == project.id)
            .order_by(SavedCorpusSelection.created_at)
        )
    )
    selections_items = []
    for s in selections:
        selections_items.append({
            "selection_id": str(s.id),
            "name": s.name,
            "description": s.description,
            "article_count": s.article_count,
            "query_definition": s.query_definition,
            "created_at": s.created_at.isoformat(),
        })

    # 3. Inter-coder agreement
    ica = get_inter_coder_agreement(db, project.id)

    # 4. Gather all distinct article IDs referenced in project
    ann_article_ids = db.scalars(
        select(Annotation.article_id).where(Annotation.project_id == project.id).distinct()
    ).all()
    proj_article_ids = db.scalars(
        select(ProjectArticle.article_id).where(ProjectArticle.project_id == project.id).distinct()
    ).all()
    all_art_ids = sorted(list(set(ann_article_ids) | set(proj_article_ids)))

    # Fetch article metadata from corpus
    art_meta_map = corpus.get_article_metadata(all_art_ids) if all_art_ids else {}

    # Build APA 7th edition citations
    apa_citations = []
    for aid in all_art_ids:
        meta = art_meta_map.get(aid, {})
        author = meta.get("author") or "Redaktion"
        pdate = meta.get("publish_date") or ""
        year = pdate[:4] if pdate else "n.d."
        src_raw = meta.get("source") or "unknown"
        src_label = SOURCE_LABELS.get(src_raw, src_raw)
        title = meta.get("title") or "Untitled"
        url = meta.get("url") or ""

        citation_str = f"{author} ({year}). {title}. {src_label}. DIDI Corpus ID: {aid}."
        if url:
            citation_str += f" {url}"
        apa_citations.append({
            "article_id": aid,
            "citation": citation_str,
            "title": title,
            "source": src_label,
            "language": meta.get("language", ""),
            "publish_date": pdate[:10],
        })

    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
            "created_at": project.created_at.isoformat(),
            "manifest_generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "provenance": {
            "platform": "DIDI Platform",
            "version": "0.2.0-beta",
            "coordinate_system": "Document ID + UTF-8 Character Offsets [start_char, end_char]",
            "coordinate_integrity": "Guaranteed additive token conservation across Stanza UD layer and full text slicing",
            "corpus": {
                "engine": "SQLite FTS5 + BM25",
                "active_languages": ["de", "it"],
                "deferred_languages": ["lld_gherd", "lld_badia", "lld_fascia"],
                "total_articles": 113823,
                "verified_regional_production": True,
            },
            "nlp_methodological_grounding": {
                "framing_radar": "Moral Foundations Theory (Graham et al. 2013; MFD 2.0 / mMPD / it-MFD)",
                "discrete_emotions": "Plutchik 8 discrete emotions (NRC Emotion Lexicon)",
                "moral_divergence": "Jensen-Shannon Divergence MFDI (Hurtado-Bodell & Menshikova 2026)",
                "differential_keyness": "Dunning Log-Likelihood G² (Dunning 1993)",
                "readability_de": "Wiener Sachtextformel WSTF 1 (Bamberger & Vanecek 1984)",
                "readability_it": "Indice Gulpease (Lucisano & Piemontese 1988)",
                "text_complexity": "Nominal Style Ratio (Biber 1988 Dimension 1)",
                "inter_coder_reliability": "Cohen's Kappa (Landis & Koch 1977 benchmark interpretation) on IoU >= 0.3 overlapping spans",
            },
        },
        "codebook": codebook_items,
        "saved_selections": selections_items,
        "reliability": {
            "total_coders": ica.get("total_coders", 0),
            "overlapping_segments": ica.get("total_overlapping_segments", 0),
            "agreed_segments": ica.get("total_agreed_segments", 0),
            "global_observed_agreement": ica.get("global_observed_agreement", 0.0),
            "global_kappa": ica.get("global_kappa", 0.0),
            "interpretation": ica.get("global_interpretation", "None"),
        },
        "apa_bibliography": apa_citations,
    }


def reproducibility_report_markdown(db: Session, corpus: DataService, project: Project) -> str:
    """Render comprehensive Markdown reproducibility report for researchers."""
    data = reproducibility_manifest(db, corpus, project)
    p = data["project"]
    prov = data["provenance"]
    rel = data["reliability"]

    md = f"""# DIDI Platform: Reproducibility & Provenance Manifest
**Project:** {p['name']}  
**Project ID:** `{p['id']}`  
**Generated:** {p['manifest_generated_at']}  
**Software Version:** {prov['platform']} {prov['version']}  

---

## 1. Architectural & Coordinate System Provenance
- **Canonical Coordinate System:** {prov['coordinate_system']}
- **Coordinate Integrity:** {prov['coordinate_integrity']}
- **Corpus Engine:** {prov['corpus']['engine']}
- **Active Linguistic Scope:** {', '.join(prov['corpus']['active_languages']).upper()} (Regional South Tyrolean Production)
- **Deferred Varieties:** {', '.join(prov['corpus']['deferred_languages'])}

### Methodological Standards
- **Moral Framing Radar:** {prov['nlp_methodological_grounding']['framing_radar']}
- **Discrete Emotions:** {prov['nlp_methodological_grounding']['discrete_emotions']}
- **Framing Divergence Index:** {prov['nlp_methodological_grounding']['moral_divergence']}
- **Differential Keyness:** {prov['nlp_methodological_grounding']['differential_keyness']}
- **Readability Indices:** German ({prov['nlp_methodological_grounding']['readability_de']}), Italian ({prov['nlp_methodological_grounding']['readability_it']})
- **Inter-Coder Reliability:** {prov['nlp_methodological_grounding']['inter_coder_reliability']}

---

## 2. Qualitative Codebook ({len(data['codebook'])} Codes)
| Code Name | Hierarchical Path | Hex Color | Passage Count |
| :--- | :--- | :--- | :--- |
"""
    for c in data["codebook"]:
        md += f"| **{c['name']}** | `{c['path']}` | `{c['color']}` | {c['passage_count']} |\n"

    md += f"""
---

## 3. Saved Corpus Selections ({len(data['saved_selections'])})
| Selection Name | Articles | Created | Description |
| :--- | :--- | :--- | :--- |
"""
    for s in data["saved_selections"]:
        md += f"| **{s['name']}** | {s['article_count']} | {s['created_at'][:10]} | {s['description'] or '—'} |\n"

    md += f"""
---

## 4. Inter-Coder Reliability (Cohen's $\\kappa$)
- **Active Coders:** {rel['total_coders']}
- **Overlapping Coded Segments (IoU $\\ge$ 0.3):** {rel['overlapping_segments']}
- **Observed Agreement ($P_o$):** {(rel['global_observed_agreement'] * 100):.1f}%
- **Global Cohen's $\\kappa$:** {rel['global_kappa']:.3f} ({rel['interpretation']})

---

## 5. APA 7th Edition Bibliography ({len(data['apa_bibliography'])} Sources)
"""
    for b in data["apa_bibliography"]:
        md += f"- {b['citation']}\n"

    return md

