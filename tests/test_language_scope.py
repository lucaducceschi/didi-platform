"""Tests for Stage 1: Pluggable Language Scope and Unconfigured Language Hiding.

Verifies that:
1. German (de) and Italian (it) are active; Ladin varieties are marked deferred.
2. Every user-facing list, filter, facet and chart shows active languages only.
3. Unconfigured language articles and coded segments are preserved untouched in DB.
4. A project library, search, or passages view hiding unconfigured items reports
   hidden_articles / hidden_passages counts.
5. Exports omit unconfigured languages.
"""

import csv
import io
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_engine
from backend.app.models import Annotation, ProjectArticle
from src.languages import (
    LANGUAGES,
    get_active_language_codes,
    get_all_language_codes,
    get_language,
    get_language_label,
    is_language_active,
)


def test_language_registry_configuration():
    assert is_language_active("de") is True
    assert is_language_active("it") is True
    assert is_language_active("lld_gherd") is False
    assert is_language_active("lld_badia") is False
    assert is_language_active("lld_fascia") is False

    assert get_active_language_codes() == {"de", "it"}
    assert "lld_gherd" in get_all_language_codes()
    assert "lld_badia" in get_all_language_codes()
    assert "lld_fascia" in get_all_language_codes()

    de = get_language("de")
    assert de is not None
    assert de.active is True
    assert "wir" in de.ingroup_pronouns
    assert ("„", "“") in de.quotation_marks
    assert "konjunktiv_1" in de.available_measures

    it = get_language("it")
    assert it is not None
    assert it.active is True
    assert "noi" in it.ingroup_pronouns
    assert ("«", "»") in it.quotation_marks
    assert "konjunktiv_1" not in it.available_measures  # only de has konjunktiv_1


def test_corpus_summary_shows_active_languages_only(client):
    summary = client.get("/api/corpus/summary").json()
    language_ids = {item["id"] for item in summary["languages"]}
    assert language_ids == {"de", "it"}
    assert not any(lid.startswith("lld") for lid in language_ids)


def test_corpus_search_hides_unconfigured_languages(client):
    # Default search only returns active languages (de and it)
    body = client.get("/api/articles/search").json()
    result_langs = {r["language"] for r in body["results"]}
    assert result_langs.issubset({"de", "it"})
    assert not any(lang.startswith("lld") for lang in result_langs)

    # Explicitly requesting an unconfigured language returns 0 results
    deferred = client.get("/api/articles/search", params={"language": ["lld_gherd"]}).json()
    assert deferred["total"] == 0
    assert deferred["results"] == []


def test_unconfigured_language_data_preserved_and_hidden_in_library(world):
    # fx_lld_nfd and fx_lld_crlf exist in SQLite fixture corpus
    article = world.coder.get("/api/articles/fx_lld_nfd").json()
    assert article["id"] == "fx_lld_nfd"
    assert article["language"] == "lld_gherd"
    assert "Gherdëina" in article["full_text"]

    # Add fx_lld_nfd to the project in PostgreSQL
    with Session(get_engine()) as db:
        db.add(ProjectArticle(project_id=world.ids["project"], article_id="fx_lld_nfd", added_by=world.ids["admin"]))
        db.commit()

    # The article exists in PostgreSQL project_articles
    with Session(get_engine()) as db:
        in_db = db.scalar(
            select(ProjectArticle.article_id).where(
                ProjectArticle.project_id == world.ids["project"],
                ProjectArticle.article_id == "fx_lld_nfd",
            )
        )
        assert in_db == "fx_lld_nfd"

    # In library view, fx_lld_nfd is hidden from results and facets, but reported as hidden_articles to lead
    lib = world.lead.get(f"{world.url}/library").json()
    result_ids = {a["id"] for a in lib["results"]}
    assert "fx_lld_nfd" not in result_ids
    assert {f["id"] for f in lib["languages"]} == {"de", "it"}
    assert lib["hidden_articles"] == 1
    assert lib["project_total"] == 6  # 5 active + 1 deferred in project

    # A regular coder gets hidden_articles == 0
    coder_lib = world.coder.get(f"{world.url}/library").json()
    assert coder_lib["hidden_articles"] == 0


def test_unconfigured_language_passages_and_exports_hidden_but_preserved(world):
    # Create a code
    code = world.coder.post(f"{world.url}/codes", json={"name": "ScopeTestCode"}).json()

    # Add segment directly on fx_lld_nfd
    with Session(get_engine()) as db:
        db.add(ProjectArticle(project_id=world.ids["project"], article_id="fx_lld_nfd", added_by=world.ids["admin"]))
        db.add(
            Annotation(
                project_id=world.ids["project"],
                article_id="fx_lld_nfd",
                user_id=world.ids["coder"],
                code_id=code["id"],
                start_pos=0,
                end_pos=9,
                quote="Gherdëina",
                memo="Deferred test note",
                status="active",
                text_sha256="test",
            )
        )
        db.commit()

    # Verify annotation is preserved in PostgreSQL
    with Session(get_engine()) as db:
        annot = db.scalar(
            select(Annotation.quote).where(
                Annotation.project_id == world.ids["project"],
                Annotation.article_id == "fx_lld_nfd",
            )
        )
        assert annot == "Gherdëina"

    # Passages view hides the passage: lead gets hidden_passages count, coder gets 0
    lead_passages = world.lead.get(f"{world.url}/passages").json()
    passage_articles = {p["article_id"] for p in lead_passages["results"]}
    assert "fx_lld_nfd" not in passage_articles
    assert lead_passages["hidden_passages"] >= 1
    assert all(f["id"] in {"de", "it"} for f in lead_passages["languages"])

    coder_passages = world.coder.get(f"{world.url}/passages").json()
    assert coder_passages["hidden_passages"] == 0

    # Export CSV omits annotations on unconfigured languages
    csv_bytes = world.lead.get(f"{world.url}/exports/annotations.csv").content
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    exported_articles = {row["article_id"] for row in reader}
    assert "fx_lld_nfd" not in exported_articles


def test_streamlit_path_sees_ladin_by_default(fixture_corpus):
    from src.ui.data_service import DataService

    service = DataService(db_path=fixture_corpus, enable_hybrid=False)
    summary = service.get_corpus_summary()  # default active_only=False
    lang_keys = set(summary["languages"].keys())
    assert "lld_gherd" in lang_keys
    assert "lld_badia" in lang_keys
    assert summary["total_articles"] == 7

    # search_articles default also includes all languages
    rows, total = service.search_articles(query="Gherdëina")
    assert total >= 1
    assert any(r["language"] == "lld_gherd" for r in rows)


def test_search_synonyms_expand_identically():
    from src.languages import get_thesaurus
    from src.ui.data_service import DataService

    thesaurus = get_thesaurus(active_only=False)

    # Check key concepts exist across languages
    assert "schule" in thesaurus
    assert "scuola" in thesaurus
    assert "scola" in thesaurus
    assert "autonomie" in thesaurus
    assert "autonomia" in thesaurus
    assert "lupo" in thesaurus
    assert "wolf" in thesaurus

    # Check German, Italian and Ladin expand identically for concept
    school_expansion = "scuola* OR scuole* OR scolast* OR schule* OR schul* OR scola* OR bildung* OR istruzion*"
    assert thesaurus["schule"] == school_expansion
    assert thesaurus["scuola"] == school_expansion
    assert thesaurus["scola"] == school_expansion

    autonomy_expansion = "autonom* OR zuständig* OR competenz* OR cumpetënz* OR statut*"
    assert thesaurus["autonomie"] == autonomy_expansion
    assert thesaurus["autonomia"] == autonomy_expansion

    # DataService.build_fts_query expands keywords using this unified thesaurus
    service = DataService.__new__(DataService)
    service.last_query_expansion = None
    q_de, desc_de = service.build_fts_query("schule", expand_trilingual=True)
    q_it, desc_it = service.build_fts_query("scuola", expand_trilingual=True)
    q_lld, desc_lld = service.build_fts_query("scola", expand_trilingual=True)
    assert q_de == school_expansion
    assert q_it == school_expansion
    assert q_lld == school_expansion




def test_search_synonyms_match_the_original_table():
    """The merged per-language synonyms must expand every term exactly as the old TRILINGUAL_THESAURUS did."""
    import json
    from pathlib import Path
    from src.languages import get_thesaurus

    snapshot = json.loads((Path(__file__).parent / "fixtures" / "search_synonyms_snapshot.json").read_text(encoding="utf-8"))
    assert get_thesaurus(active_only=False) == snapshot
