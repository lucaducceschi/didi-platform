from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.services import library
from tests.test_codebook import add_segment, make_code


def set_progress(world, username, article_id, status):
    with Session(get_engine()) as db:
        library.set_progress(db, world.ids["project"], article_id, world.ids[username], status)
        db.commit()


def row(body, article_id):
    return next(item for item in body["results"] if item["id"] == article_id)


def test_library_shows_each_coders_status_and_counts(world):
    code = make_code(world, "A")
    add_segment(world.coder, world, code["id"], 0, 3)
    add_segment(world.coder, world, code["id"], 4, 8)
    add_segment(world.coder2, world, code["id"], 0, 3)
    set_progress(world, "coder", "fx_de_1", "done")
    set_progress(world, "coder2", "fx_de_1", "in_progress")

    body = world.coder.get(f"{world.url}/library").json()
    assert body["project_total"] == 5 and body["total"] == 5
    article = row(body, "fx_de_1")
    assert article["my_status"] == "done"
    assert [(c["user"]["username"], c["status"], c["segments"]) for c in article["coders"]] == [
        ("coder", "done", 2),
        ("coder2", "in_progress", 1),
    ]
    assert article["language_label"] == "German (de)" and article["source_label"] == "Salto.bz"
    assert row(body, "fx_it_1")["my_status"] == "not_started" and row(body, "fx_it_1")["coders"] == []


def test_library_filters_and_reports_how_many_are_hidden(world):
    set_progress(world, "coder", "fx_it_1", "done")
    url = f"{world.url}/library"
    assert {a["id"] for a in world.coder.get(url, params={"language": "it"}).json()["results"]} == {"fx_it_1"}
    assert {a["id"] for a in world.coder.get(url, params={"source": "trail"}).json()["results"]} == {"fx_lld_crlf"}
    done = world.coder.get(url, params={"status": "done"}).json()
    assert [a["id"] for a in done["results"]] == ["fx_it_1"] and done["total"] == 1 and done["project_total"] == 5
    # Another coder's progress doesn't count as mine.
    assert world.coder2.get(url, params={"status": "done"}).json()["total"] == 0
    assert world.coder2.get(url, params={"status": "not_started"}).json()["total"] == 5


def test_library_paginates_newest_first_with_project_wide_facets(world):
    first = world.coder.get(f"{world.url}/library", params={"page_size": 2}).json()
    second = world.coder.get(f"{world.url}/library", params={"page_size": 2, "page": 2}).json()
    assert [a["id"] for a in first["results"]] == ["fx_de_1", "fx_it_1"]
    assert [a["id"] for a in second["results"]] == ["fx_lld_nfd", "fx_lld_crlf"]
    assert {f["id"]: f["count"] for f in first["languages"]} == {"de": 2, "it": 1, "lld_gherd": 1, "lld_badia": 1}


def test_library_is_closed_to_other_projects(world):
    assert world.outsider.get(f"{world.url}/library").status_code == 404
    assert world.anonymous.get(f"{world.url}/library").status_code == 401


def test_article_that_left_the_corpus_stays_visible(world):
    code = make_code(world, "A")
    add_segment(world.coder, world, code["id"], 0, 3, article="fx_it_1")
    import shutil
    import sqlite3

    from backend.app.settings import get_settings

    copy = get_settings().corpus_path.parent / "library_copy.db"
    shutil.copy(get_settings().corpus_path, copy)
    connection = sqlite3.connect(copy)
    connection.execute("DELETE FROM articles WHERE id = 'fx_it_1'")
    connection.commit()
    connection.close()
    import os

    os.environ["DIDI_CORPUS_PATH"] = str(copy)
    get_settings.cache_clear()
    try:
        body = world.coder.get(f"{world.url}/library").json()
    finally:
        os.environ.pop("DIDI_CORPUS_PATH", None)
        get_settings.cache_clear()
        copy.unlink()
    assert body["project_total"] == 5
    article = row(body, "fx_it_1")
    assert article["in_corpus"] is False and article["coders"][0]["segments"] == 1
    assert body["results"][-1]["id"] == "fx_it_1"


def test_project_article_route_requires_the_article_in_the_project(world):
    other = f"/api/projects/{world.ids['other_project']}"
    assert world.coder.get(f"{world.url}/articles/fx_de_1").json()["id"] == "fx_de_1"
    assert world.coder.get(f"{other}/articles/fx_de_1").status_code == 404
    assert world.outsider.get(f"{world.url}/articles/fx_de_1").status_code == 404


def test_search_marks_articles_already_in_the_project(world):
    other = f"/api/projects/{world.ids['other_project']}"
    world.outsider.post(f"{other}/articles", json={"article_ids": ["fx_de_1"]})
    body = world.outsider.get(f"{other}/article-search", params={"language": "de"}).json()
    assert body["total"] == 2 and body["in_project_total"] == 1
    assert {a["id"]: a["in_project"] for a in body["results"]} == {"fx_de_1": True, "fx_markup": False}
    assert world.lead.get(f"{other}/article-search").status_code == 404


def test_adding_all_matches_of_a_search(world):
    other = f"/api/projects/{world.ids['other_project']}"
    world.outsider.post(f"{other}/articles", json={"article_ids": ["fx_de_1"]})
    response = world.outsider.post(f"{other}/articles/from-search", json={"language": ["de"]})
    assert response.json() == {"added": 1, "already_present": 1}
    again = world.outsider.post(f"{other}/articles/from-search", json={"language": ["de"]})
    assert again.json() == {"added": 0, "already_present": 2}
    assert world.outsider.get(f"{other}/library").json()["project_total"] == 2
    # A search adds the same articles it shows, including the thesaurus match for Ladin "scola".
    shown = world.outsider.get(f"{other}/article-search", params={"q": "scuola"}).json()["total"]
    by_query = world.outsider.post(f"{other}/articles/from-search", json={"q": "scuola"}).json()
    assert by_query["added"] + by_query["already_present"] == shown == 2


def test_adding_from_search_needs_a_lead_and_valid_syntax(world):
    assert world.coder.post(f"{world.url}/articles/from-search", json={"language": ["de"]}).status_code == 403
    assert world.outsider.post(f"{world.url}/articles/from-search", json={}).status_code == 404
    bad = world.lead.post(f"{world.url}/articles/from-search", json={"q": '"unbalanced'})
    assert bad.status_code == 400
    assert world.lead.get(f"{world.url}/article-search", params={"q": '"unbalanced'}).status_code == 400


def test_adding_thousands_of_articles_is_safe(world, monkeypatch):
    from backend.app.services import library

    ids = [f"bulk_{index}" for index in range(5000)]
    with Session(get_engine()) as db:
        assert library.add_articles(db, world.ids["project"], world.ids["lead"], ids) == 5000
        assert library.add_articles(db, world.ids["project"], world.ids["lead"], ids) == 0
        db.rollback()


def annotate(client, world, code_id, article="fx_de_1"):
    return client.post(f"{world.url}/articles/{article}/annotations", json={"start": 0, "end": 3, "code_id": code_id})


def test_first_segment_marks_the_article_in_progress_for_that_coder_only(world):
    code = make_code(world, "A")
    url = f"{world.url}/articles/fx_de_1/progress"
    assert world.coder.get(url).json()["status"] == "not_started"
    annotate(world.coder, world, code["id"])
    assert world.coder.get(url).json()["status"] == "in_progress"
    assert world.coder2.get(url).json()["status"] == "not_started"


def test_mark_done_and_reopen_and_coding_does_not_undo_done(world):
    code = make_code(world, "A")
    url = f"{world.url}/articles/fx_de_1/progress"
    assert world.coder.put(url, json={"status": "done"}).json()["status"] == "done"
    annotate(world.coder, world, code["id"])
    assert world.coder.get(url).json()["status"] == "done"
    assert world.coder.put(url, json={"status": "in_progress"}).json()["status"] == "in_progress"
    assert world.coder.get(f"{world.url}/library", params={"status": "in_progress"}).json()["total"] == 1


def test_progress_rules(world):
    url = f"{world.url}/articles/fx_de_1/progress"
    assert world.coder.put(url, json={"status": "not_started"}).status_code == 422
    assert world.admin.put(url, json={"status": "done"}).status_code == 403
    assert world.outsider.put(url, json={"status": "done"}).status_code == 404
    assert world.coder.put(f"{world.url}/articles/not_in_project/progress", json={"status": "done"}).status_code == 404
    assert world.anonymous.get(url).status_code == 401


def test_presence_shows_others_and_never_yourself(world):
    url = f"{world.url}/articles/fx_de_1/presence"
    assert world.coder.post(url).json()["others"] == []
    assert [person["username"] for person in world.coder2.post(url).json()["others"]] == ["coder"]
    assert [person["username"] for person in world.coder.post(url).json()["others"]] == ["coder2"]
    # A different article doesn't count.
    assert world.lead.post(f"{world.url}/articles/fx_it_1/presence").json()["others"] == []


def test_leaving_clears_presence(world):
    url = f"{world.url}/articles/fx_de_1/presence"
    world.coder.post(url)
    assert world.coder.delete(url).status_code == 204
    assert world.coder2.post(url).json()["others"] == []


def test_presence_expires_when_a_tab_just_disappears(world):
    from datetime import timedelta

    from backend.app.models import Presence, utcnow
    from backend.app.services.library import PRESENCE_TIMEOUT_SECONDS

    url = f"{world.url}/articles/fx_de_1/presence"
    world.coder.post(url)
    with Session(get_engine()) as db:
        presence = db.get(Presence, (world.ids["project"], "fx_de_1", world.ids["coder"]))
        presence.last_seen = utcnow() - timedelta(seconds=PRESENCE_TIMEOUT_SECONDS - 5)
        db.commit()
    assert len(world.coder2.post(url).json()["others"]) == 1
    with Session(get_engine()) as db:
        presence = db.get(Presence, (world.ids["project"], "fx_de_1", world.ids["coder"]))
        presence.last_seen = utcnow() - timedelta(seconds=PRESENCE_TIMEOUT_SECONDS + 5)
        db.commit()
    assert world.coder2.post(url).json()["others"] == []


def test_presence_is_limited_to_the_project(world):
    url = f"{world.url}/articles/fx_de_1/presence"
    assert world.outsider.post(url).status_code == 404
    assert world.anonymous.post(url).status_code == 401
    # An admin who isn't a member can look without appearing as someone working on it.
    world.coder.post(url)
    assert len(world.admin.post(url).json()["others"]) == 1
    assert [person["username"] for person in world.coder.post(url).json()["others"]] == []


def test_streamlit_no_longer_uses_the_old_annotation_table():
    from pathlib import Path

    from src.ui.data_service import DataService

    for name in ("add_annotation", "export_all_annotations", "_init_annotations_table"):
        assert not hasattr(DataService, name)
    source = Path("src/ui/app.py").read_text(encoding="utf-8") + Path("src/ui/data_service.py").read_text(encoding="utf-8")
    assert "article_annotations" not in source


def test_removing_an_article_needs_a_lead_and_no_segments(world):
    url = f"{world.url}/articles"
    assert world.coder.delete(f"{url}/fx_it_1").status_code == 403
    assert world.outsider.delete(f"{url}/fx_it_1").status_code == 404
    assert world.anonymous.delete(f"{url}/fx_it_1").status_code == 401
    assert world.lead.delete(f"{url}/not_in_project").status_code == 404

    code = make_code(world, "A")
    add_segment(world.coder, world, code["id"], 0, 3)
    add_segment(world.coder2, world, code["id"], 0, 3)
    refused = world.lead.delete(f"{url}/fx_de_1")
    assert refused.status_code == 409 and "2 coded passages from 2 coders" in refused.json()["detail"]
    assert world.coder.get(f"{world.url}/passages").json()["total"] == 2

    set_progress(world, "coder", "fx_it_1", "done")
    assert world.lead.delete(f"{url}/fx_it_1").status_code == 204
    library_ids = {item["id"] for item in world.lead.get(f"{world.url}/library").json()["results"]}
    assert "fx_it_1" not in library_ids and "fx_de_1" in library_ids
    # Adding it back starts clean, and the removal is on record.
    assert world.lead.post(url, json={"article_ids": ["fx_it_1"]}).json()["added"] == 1
    assert row(world.coder.get(f"{world.url}/library").json(), "fx_it_1")["my_status"] == "not_started"
    assert "articles.removed" in {entry["action"] for entry in world.lead.get(f"{world.url}/activity").json()}


def test_removing_everything_nobody_has_started(world):
    code = make_code(world, "A")
    add_segment(world.coder, world, code["id"], 0, 3)
    set_progress(world, "coder2", "fx_it_1", "done")
    assert world.lead.get(f"{world.url}/library").json()["unstarted_total"] == 3

    url = f"{world.url}/articles/remove-unstarted"
    assert world.coder.post(url).status_code == 403
    assert world.lead.post(url).json() == {"removed": 3}
    library_ids = {item["id"] for item in world.lead.get(f"{world.url}/library").json()["results"]}
    assert library_ids == {"fx_de_1", "fx_it_1"}
    assert world.lead.post(url).json() == {"removed": 0}


def test_a_removal_waits_for_a_segment_save_in_progress_and_then_refuses(world):
    import pytest
    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from backend.app.models import Annotation
    from backend.app.services.annotations import require_article_in_project

    code = make_code(world, "A")
    project, article = world.ids["project"], "fx_it_1"
    fixed = world.coder.get(f"/api/articles/{article}").json()["full_text"]
    with Session(get_engine()) as saving, Session(get_engine()) as removing:
        require_article_in_project(saving, project, article, lock=True)
        saving.add(Annotation(
            project_id=project, article_id=article, user_id=world.ids["coder"], code_id=code["id"],
            start_pos=0, end_pos=3, quote=fixed[:3], text_sha256="x",
        ))
        saving.flush()

        # While the save is open, the removal has to wait.
        removing.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(OperationalError):
            library.remove_article(removing, project, world.ids["lead"], article)
        removing.rollback()

        saving.commit()
        with pytest.raises(HTTPException) as refused:
            library.remove_article(removing, project, world.ids["lead"], article)
        assert refused.value.status_code == 409
