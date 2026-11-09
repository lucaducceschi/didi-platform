"""
Offline tests for DIDI media collectors (no network).
Verifies:
- robots.txt compliance (including 401/403 and unreachable blocks)
- URL normalization (stripping utm_*, fbclid, fragments)
- Raw HTML page saving with SHA-256 and fetch time
- Extractor version and method recording
- Wire byline detection (ANSA, Adnkronos, APA, dpa, Italpress, Reuters)
- Window resolution and incremental backfills
- Pipeline execution with fake HTTP
"""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from src.collectors import COLLECTOR_VERSION, pipeline
from src.collectors.config import Registry, Source, load_registry
from src.collectors.dedup import hamming, simhash
from src.collectors.discovery import normalize_url, parse_feed, parse_sitemap
from src.collectors.extract import Article, detect_wire_agency, extract
from src.collectors.http import PoliteSession
from src.collectors.store import State

FX = Path(__file__).parent / "fixtures" / "collectors"
UTC = timezone.utc


def fx(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


# ------------------------------------------------------------------ config
def test_registry_loads_open_sources():
    reg = load_registry()
    ids = [s.id for s in reg.sources]
    assert len(ids) == len(set(ids))
    assert {"salto_it", "rai_tgr_bolzano", "provinz_press"} <= set(ids)
    # Ensure paywalled/agency sources were excluded
    assert "dolomiten_stol" not in set(ids)
    assert "altoadige" not in set(ids)
    assert "corriere_aa" not in set(ids)
    assert "ansa_taa" not in set(ids)


# ------------------------------------------------------------------ URL Normalization
def test_url_normalization_strips_tracking_and_fragment():
    raw = "https://salto.bz/it/article/123?utm_source=facebook&utm_medium=cpc&fbclid=IwAR123&keep=1#comments"
    norm = normalize_url(raw)
    assert norm == "https://salto.bz/it/article/123?keep=1"
    assert "utm_" not in norm
    assert "fbclid" not in norm
    assert "#" not in norm


# ------------------------------------------------------------------ robots.txt
def test_robots_txt_cases(monkeypatch):
    class FakeRobotsResp:
        def __init__(self, status_code: int, text: str = ""):
            self.status_code = status_code
            self.text = text
            self.headers = {"Content-Type": "text/plain"}

    session = PoliteSession(respect_robots=True)

    # 1. 200 OK with Disallow
    monkeypatch.setattr(session, "_raw_get", lambda url, **kw: FakeRobotsResp(200, "User-agent: *\nDisallow: /secret/\n"))
    session.load_robots("https://site1.org/news")
    assert session.allowed("https://site1.org/news") is True
    assert session.allowed("https://site1.org/secret/doc") is False

    # 2. 401 or 403 Forbidden -> blocks everything
    session2 = PoliteSession(respect_robots=True)
    monkeypatch.setattr(session2, "_raw_get", lambda url, **kw: FakeRobotsResp(403))
    session2.load_robots("https://site2.org/news")
    assert session2.allowed("https://site2.org/news") is False

    # 3. Unreachable / network error -> blocks everything
    session3 = PoliteSession(respect_robots=True)
    def fail_get(url, **kw):
        raise requests.ConnectionError("Network down")
    monkeypatch.setattr(session3, "_raw_get", fail_get)
    session3.load_robots("https://site3.org/news")
    assert session3.allowed("https://site3.org/news") is False

    # 4. 404 Not Found -> allows everything
    session4 = PoliteSession(respect_robots=True)
    monkeypatch.setattr(session4, "_raw_get", lambda url, **kw: FakeRobotsResp(404))
    session4.load_robots("https://site4.org/news")
    assert session4.allowed("https://site4.org/news") is True


# ------------------------------------------------------------------ wire bylines
def test_wire_byline_detection():
    # Author byline mention
    flag, agency = detect_wire_agency(["Redazione ANSA"], "Bolzano, inaugurata la mostra.")
    assert flag is True and agency == "ANSA"

    # Dateline mention in text head
    flag, agency = detect_wire_agency(["Mario Rossi"], "BOLZANO (Adnkronos) - Approvata la legge sul bilancio provinciale.")
    assert flag is True and agency == "ADNKRONOS"

    # Normal article
    flag, agency = detect_wire_agency(["Anna Huber"], "Der Landtag debattiert über das Gesetz.")
    assert flag is False and agency is None


# ------------------------------------------------------------------ discovery & extraction
def test_sitemaps_and_feed_parsing():
    children, urls = parse_sitemap(fx("sitemap_index.xml").encode())
    assert [c[0] for c in children][0].endswith("2026-10.xml")
    _, urls = parse_sitemap(fx("news_sitemap.xml").encode())
    assert urls[0][1] == datetime(2026, 10, 14, 6, 30, tzinfo=UTC)

    items = parse_feed(fx("feed.xml").encode())
    assert items[0][0] == "https://example.it/notizie/a"


def test_extraction_provenance_and_metadata():
    art = extract(fx("article_jsonld.html"), "https://example.it/notizie/a?utm_source=x#123", final_url="https://example.it/notizie/a")
    assert art.title.startswith("Toponomastica")
    assert art.published == datetime(2026, 10, 14, 6, 30, tzinfo=UTC)
    assert art.collector_version == COLLECTOR_VERSION
    assert art.trafilatura_version != "unknown"
    assert art.extraction_method in ("jsonld", "trafilatura")


# ------------------------------------------------------------------ storage & raw pages
def test_raw_page_saving_and_checksum(tmp_path):
    state = State(tmp_path)
    content = b"<html><body>Test raw HTML content for checksum verification</body></html>"
    sha = state.save_raw_page("salto_it", "https://example.org/doc", content)

    expected_sha = hashlib.sha256(content).hexdigest()
    assert sha == expected_sha

    # Verify gzipped file on disk
    page_file = tmp_path / "raw" / "collected" / "salto_it" / "pages" / f"{sha}.html.gz"
    assert page_file.exists()
    decompressed = gzip.decompress(page_file.read_bytes())
    assert decompressed == content


# ------------------------------------------------------------------ end-to-end pipeline run
class FakeHTTP:
    pages = {
        "https://example.it/robots.txt": "Sitemap: https://example.it/news_sitemap.xml\n",
        "https://example.it/news_sitemap.xml": fx("news_sitemap.xml"),
        "https://example.it/notizie/a": fx("article_jsonld.html"),
        "https://example.it/notizie/b": fx("article_jsonld.html").replace(
            "2026-10-14T08:30:00+02:00", "2026-06-01T08:00:00Z"
        ),
        "https://example.it/feed": fx("feed.xml"),
        "https://example.it/notizie/old": fx("article_jsonld.html"),
    }

    def __init__(self, *a, **k):
        pass

    def robots_sitemaps(self, url):
        return ["https://example.it/news_sitemap.xml"]

    def allowed(self, url):
        return True

    def get(self, url):
        body = self.pages.get(url)
        if body is None:
            return None
        return SimpleNamespace(text=body, content=body.encode(), url=url, status_code=200, headers={"Content-Type": "text/html"})


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "PoliteSession", FakeHTTP)
    monkeypatch.setattr("src.collectors.discovery.PoliteSession", FakeHTTP, raising=False)
    src = Source(
        id="ex",
        name="Example",
        language="it",
        kind="online",
        base_url="https://example.it/",
        rss=["https://example.it/feed"],
        include=["/notizie/"],
    )
    reg = Registry(user_agent="test", sources=[src])
    return src, reg, tmp_path


def test_pipeline_run_saves_raw_pages_and_records(setup):
    src, reg, data = setup
    since, until = datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 12, 31, tzinfo=UTC)
    s = pipeline.run_source(src, reg, data, "run1", since, until)
    assert s["written"] == 1

    # Check JSONL record
    recs = [json.loads(line) for line in gzip.open(s["output"], "rt", encoding="utf-8")]
    r = recs[0]
    assert r["url"] == "https://example.it/notizie/a"
    assert r["collector_version"] == COLLECTOR_VERSION
    assert "raw_sha256" in r

    # Check raw page file exists
    raw_path = data / "raw" / "collected" / "ex" / "pages" / f"{r['raw_sha256']}.html.gz"
    assert raw_path.exists()

