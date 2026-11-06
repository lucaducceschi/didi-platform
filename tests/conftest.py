import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).parent / "fixtures"
REAL_CORPUS = ROOT / "data" / "processed" / "didi_corpus.db"
TEST_DATABASE_URL = "postgresql+psycopg://didi:didi_dev@localhost:5433/didi_test"


def _fixture_records():
    return json.loads((FIXTURES / "corpus_articles.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def fixture_records():
    return _fixture_records()


@pytest.fixture(scope="session")
def fixture_corpus(tmp_path_factory):
    from src.models.schema import DIDIArticle
    from src.storage import DIDICorpusDB

    path = tmp_path_factory.mktemp("corpus") / "corpus.db"
    articles = [
        DIDIArticle(**{**record, "publish_date": datetime.fromisoformat(record["publish_date"])})
        for record in _fixture_records()
    ]
    assert DIDICorpusDB(path).insert_batch(articles) == len(articles)
    return path


def _reset_settings():
    from backend.app.database import get_engine
    from backend.app.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def configure(monkeypatch):
    def apply(corpus_path, database_url=TEST_DATABASE_URL):
        monkeypatch.setenv("DIDI_CORPUS_PATH", str(corpus_path))
        monkeypatch.setenv("DIDI_DATABASE_URL", database_url)
        _reset_settings()

    yield apply
    monkeypatch.undo()
    _reset_settings()


@pytest.fixture
def client(configure, fixture_corpus):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    configure(fixture_corpus)
    return TestClient(app)


@pytest.fixture(scope="session")
def test_database():
    """Create an empty test database in the local PostgreSQL. Start it with `make db-up`."""
    from sqlalchemy import create_engine, text

    engine = create_engine(TEST_DATABASE_URL.replace("/didi_test", "/didi"), isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP DATABASE IF EXISTS didi_test WITH (FORCE)"))
        connection.execute(text("CREATE DATABASE didi_test"))
    engine.dispose()
    return TEST_DATABASE_URL
