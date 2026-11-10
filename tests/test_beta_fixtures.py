import json
from datetime import datetime
from pathlib import Path
import pytest
from src.models.schema import DIDIArticle
from src.storage import DIDICorpusDB

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "beta_search_articles.json"


def test_beta_fixture_format():
    assert FIXTURE_PATH.exists()
    records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(records) >= 6

    # Verify presence of German, Italian, and Ladin items
    langs = {r["language"] for r in records}
    assert "de" in langs
    assert "it" in langs
    assert "lld_gherd" in langs

    # Verify presence of both journalism and official press
    sources = {r["source"] for r in records}
    assert "tageszeitung" in sources
    assert "salto" in sources
    assert "provinz_news" in sources


def test_beta_fixture_insertion_and_fts(tmp_path):
    db_path = tmp_path / "test_beta.db"
    db = DIDICorpusDB(db_path)

    records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    articles = [
        DIDIArticle(**{**r, "publish_date": datetime.fromisoformat(r["publish_date"])})
        for r in records
    ]
    inserted = db.insert_batch(articles)
    assert inserted == len(articles)

    # Verify FTS query on compound
    with db._get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM articles_fts WHERE articles_fts MATCH 'Autonomiestatut*'")
        assert c.fetchone()[0] >= 1

