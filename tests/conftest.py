import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict

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

    try:
        get_engine().dispose()
    except Exception:
        pass
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


@pytest.fixture(scope="session")
def test_database():
    """Create and migrate an empty test database in the local PostgreSQL. Start it with `make db-up`."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    engine = create_engine(TEST_DATABASE_URL.replace("/didi_test", "/didi"), isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP DATABASE IF EXISTS didi_test WITH (FORCE)"))
        connection.execute(text("CREATE DATABASE didi_test"))
    engine.dispose()

    previous = os.environ.get("DIDI_DATABASE_URL")
    os.environ["DIDI_DATABASE_URL"] = TEST_DATABASE_URL
    _reset_settings()
    command.upgrade(Config(str(ROOT / "backend" / "alembic.ini")), "head")
    if previous is None:
        del os.environ["DIDI_DATABASE_URL"]
    else:
        os.environ["DIDI_DATABASE_URL"] = previous
    _reset_settings()
    return TEST_DATABASE_URL


@pytest.fixture
def clean_database(test_database, configure, fixture_corpus):
    from sqlalchemy import text

    from backend.app.database import get_engine

    configure(fixture_corpus)
    with get_engine().begin() as connection:
        tables = connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
        ).scalars().all()
        connection.execute(text("TRUNCATE " + ", ".join(tables) + " CASCADE"))
    return test_database


PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session")
def password_hash():
    from backend.app.security import hash_password

    return hash_password(PASSWORD)


@dataclass
class World:
    """Two projects and one person in each role. Each client is logged in as that person."""

    make_client: Callable
    ids: Dict[str, uuid.UUID] = field(default_factory=dict)
    clients: Dict[str, object] = field(default_factory=dict)

    def __getattr__(self, name):
        try:
            return self.clients[name]
        except KeyError:
            raise AttributeError(name)


@pytest.fixture
def world(clean_database, password_hash):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    from backend.app.database import get_engine
    from backend.app.main import app
    from backend.app.models import Project, ProjectArticle, ProjectMember, User

    def make_client(username=None):
        client = TestClient(app)
        if username:
            response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
            assert response.status_code == 200, response.text
        return client

    state = World(make_client=make_client)
    with Session(get_engine()) as db:
        for name, is_admin in [("admin", True), ("member_admin", True), ("lead", False), ("coder", False), ("coder2", False), ("outsider", False)]:
            user = User(username=name, display_name=name.title(), password_hash=password_hash, is_admin=is_admin)
            db.add(user)
            db.flush()
            state.ids[name] = user.id
        for key, name in [("project", "Autonomy"), ("other_project", "Language rights")]:
            project = Project(name=name, created_by=state.ids["admin"])
            db.add(project)
            db.flush()
            state.ids[key] = project.id
        for user_key, role in [("lead", "lead"), ("coder", "coder"), ("coder2", "coder"), ("member_admin", "coder")]:
            db.add(ProjectMember(project_id=state.ids["project"], user_id=state.ids[user_key], role=role))
        db.add(ProjectMember(project_id=state.ids["other_project"], user_id=state.ids["outsider"], role="lead"))
        db.add(ProjectMember(project_id=state.ids["other_project"], user_id=state.ids["coder"], role="lead"))
        for article_id in ("fx_de_1", "fx_it_1", "fx_de_nfd", "fx_it_crlf", "fx_markup"):
            db.add(ProjectArticle(project_id=state.ids["project"], article_id=article_id, added_by=state.ids["admin"]))
        db.commit()
    for name in ("admin", "member_admin", "lead", "coder", "coder2", "outsider"):
        state.clients[name] = make_client(name)
    state.clients["anonymous"] = make_client()
    state.url = f"/api/projects/{state.ids['project']}"
    return state


@pytest.fixture
def client(world):
    """A logged-in client for reading the corpus."""
    return world.coder
