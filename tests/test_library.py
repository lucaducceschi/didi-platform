from sqlalchemy.orm import Session

from backend.app.database import get_engine
from backend.app.models import ArticleProgress
from tests.test_codebook import add_segment, make_code


def set_progress(world, username, article_id, status):
    with Session(get_engine()) as db:
        db.add(ArticleProgress(project_id=world.ids["project"], article_id=article_id, user_id=world.ids[username], status=status))
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
