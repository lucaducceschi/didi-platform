import sqlite3
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from tests.conftest import REAL_CORPUS

real_corpus = pytest.mark.real_corpus
skip_without_corpus = pytest.mark.skipif(not REAL_CORPUS.exists(), reason="private corpus not available")


def test_health_reports_both_databases(client, test_database):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "corpus": "ok"}
    assert response.json()["build"]["version"]


def test_health_fails_when_postgres_is_unreachable(configure, fixture_corpus):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    configure(fixture_corpus, "postgresql+psycopg://didi:x@localhost:1/none?connect_timeout=1")
    response = TestClient(app).get("/api/health")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unavailable"


def test_health_fails_when_corpus_is_missing(configure, test_database, tmp_path):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    configure(tmp_path / "missing.db")
    response = TestClient(app).get("/api/health")
    assert response.status_code == 503
    assert response.json()["checks"]["corpus"] == "unavailable"


def test_migrations_run_on_empty_database(configure, fixture_corpus, test_database):
    configure(fixture_corpus)
    config = Config(str(Path(__file__).parent.parent / "backend" / "alembic.ini"))
    command.upgrade(config, "head")


def test_search_finds_and_marks_matches(client):
    body = client.get("/api/articles/search", params={"q": "Museumsbericht"}).json()
    assert body["total"] == 1
    assert body["results"][0]["id"] == "fx_markup"
    assert any(part["match"] for part in body["results"][0]["snippet"])
    assert "full_text" not in body["results"][0]


def test_search_never_returns_highlight_html(client):
    body = client.get("/api/articles/search", params={"q": "Autonomie"}).json()
    assert body["total"] >= 1
    assert all("<mark" not in part["text"] for result in body["results"] for part in result["snippet"])


def test_search_filters_by_language_and_source(client):
    body = client.get("/api/articles/search", params={"language": ["lld_gherd", "lld_badia"]}).json()
    assert {result["id"] for result in body["results"]} == {"fx_lld_nfd", "fx_lld_crlf"}
    body = client.get("/api/articles/search", params={"source": "trail"}).json()
    assert [result["id"] for result in body["results"]] == ["fx_lld_crlf"]


def test_search_paginates(client):
    first = client.get("/api/articles/search", params={"page_size": 2, "page": 1}).json()
    second = client.get("/api/articles/search", params={"page_size": 2, "page": 2}).json()
    assert first["total"] == 5
    assert not {result["id"] for result in first["results"]} & {result["id"] for result in second["results"]}


@pytest.mark.parametrize("query", ['"unbalanced', "AND", "foo AND", "NOT NOT"])
def test_bad_search_syntax_gets_a_clear_error(client, query):
    response = client.get("/api/articles/search", params={"q": query})
    assert response.status_code == 400
    assert "search" in response.json()["detail"].lower()


def test_page_size_is_limited(client):
    assert client.get("/api/articles/search", params={"page_size": 1000}).status_code == 422


@pytest.mark.parametrize("article_id", ["fx_de_1", "fx_lld_nfd", "fx_lld_crlf", "fx_markup"])
def test_article_text_is_exact(client, fixture_records, article_id):
    expected = next(record for record in fixture_records if record["id"] == article_id)["full_text"]
    assert client.get(f"/api/articles/{article_id}").json()["full_text"] == expected


def test_missing_article_is_404(client):
    assert client.get("/api/articles/nope").status_code == 404


def test_summary_has_labelled_facets(client):
    body = client.get("/api/corpus/summary").json()
    assert body["total_articles"] == 5
    assert {"id": "de", "label": "German (de)", "count": 2} in body["languages"]


def test_corpus_connection_is_read_only(fixture_corpus):
    from src.ui.data_service import DataService

    service = DataService(fixture_corpus, read_only=True, enable_hybrid=False)
    with pytest.raises(sqlite3.OperationalError):
        with service._get_connection() as connection:
            connection.execute("DELETE FROM articles")


@real_corpus
@skip_without_corpus
def test_real_articles_are_exact(configure):
    import unicodedata

    from fastapi.testclient import TestClient

    from backend.app.main import app

    configure(REAL_CORPUS)
    client = TestClient(app)
    connection = sqlite3.connect(f"{REAL_CORPUS.as_uri()}?mode=ro", uri=True)
    rows = connection.execute("SELECT id, full_text FROM articles").fetchall()
    connection.close()
    nfd = [row for row in rows if unicodedata.normalize("NFC", row[1]) != row[1]][:10]
    carriage_returns = [row for row in rows if "\r" in row[1]]
    emoji = [row for row in rows if any(ord(ch) > 0xFFFF for ch in row[1])]
    assert nfd and emoji
    for article_id, text in nfd + carriage_returns + emoji:
        assert client.get(f"/api/articles/{article_id}").json()["full_text"] == text


@real_corpus
@skip_without_corpus
@pytest.mark.parametrize("query", ["autonomia", "scuola", "kompatscher", "Autonomie Statut", ""])
def test_real_search_is_fast(configure, query):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    configure(REAL_CORPUS)
    client = TestClient(app)
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        assert client.get("/api/articles/search", params={"q": query}).status_code == 200
        timings.append(time.perf_counter() - start)
    assert sorted(timings)[2] < 0.2, f"median {sorted(timings)[2]:.3f}s"
