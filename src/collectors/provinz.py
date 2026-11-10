"""
Collector for Autonomous Province of Bolzano (Landespresseamt / Ufficio Stampa).
Fetches official press releases via Kontent.ai Delivery API in Italian and German.
Links bilingual twins (DE <-> IT) via system.codename / system.id.
Saves raw API responses with SHA-256 checksums, retries on failure with exponential backoff,
and checkpoints progress so interrupted runs resume where they stopped.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from bs4 import BeautifulSoup
from .config import load_registry
from .dedup import content_hash, simhash
from .store import JsonlWriter, State

log = logging.getLogger(__name__)

PROJECT_ID = "c1c45d5a-c794-01a3-3c24-89f77bf8cab4"
API_BASE = f"https://deliver.kontent.ai/{PROJECT_ID}/items"
COLLECTOR_VERSION = "0.1.0"
SCHEMA_VERSION = 1


def clean_rich_text(html_str: str) -> str:
    """Clean rich text paragraphs from Kontent HTML."""
    if not html_str:
        return ""
    soup = BeautifulSoup(html_str, "html.parser")
    for s in soup(["script", "style"]):
        s.extract()
    paragraphs = []
    for p in soup.find_all(["p", "h2", "h3", "li"]):
        txt = p.get_text(" ", strip=True)
        if txt and len(txt) > 10:
            paragraphs.append(txt)
    if not paragraphs:
        return soup.get_text("\n\n", strip=True)
    return "\n\n".join(paragraphs).strip()


def parse_item(item: Dict[str, Any], lang: str) -> Optional[Dict[str, Any]]:
    """Convert Kontent item to unified raw record."""
    sys_info = item.get("system", {})
    elems = item.get("elements", {})

    art_id = sys_info.get("id")
    codename = sys_info.get("codename")
    if not art_id:
        return None

    title = (elems.get("title", {}).get("value") or "").strip()
    subtitle = (elems.get("subtitle", {}).get("value") or "").strip()
    body_text = (
        clean_rich_text(elems.get("normal_text", {}).get("value"))
        or clean_rich_text(elems.get("long_text", {}).get("value"))
        or clean_rich_text(elems.get("text", {}).get("value"))
        or clean_rich_text(elems.get("short_text", {}).get("value"))
        or ""
    )
    full_text = f"{subtitle}\n\n{body_text}".strip() if subtitle else body_text
    if not title or len(full_text.split()) < 10:
        return None

    raw_date = elems.get("date", {}).get("value") or sys_info.get("last_modified")
    author = (elems.get("author", {}).get("value") or "USP").strip()
    cats = [c.get("name") for c in elems.get("news_categories", {}).get("value", []) if c.get("name")]
    category = cats[0].split("|")[0].strip() if cats else "Landesverwaltung"
    tags = [t.get("name") for t in elems.get("news_tag", {}).get("value", []) if t.get("name")]

    slug = elems.get("url", {}).get("value") or codename
    base_domain = "news.provinz.bz.it" if lang == "de" else "news.provincia.bz.it"
    canonical_url = f"https://{base_domain}/{lang}/news/{slug}"

    return {
        "raw_id": art_id,
        "codename": codename,
        "language": lang,
        "url": canonical_url,
        "title": title,
        "subtitle": subtitle,
        "author": author,
        "category": category,
        "tags": tags,
        "publish_date": raw_date,
        "full_text": full_text,
        "word_count": len(full_text.split()),
        "source": "provinz_news",
        "source_type": "official_press",
        "local_provenance_score": 1.0,
    }


def get_checkpoint(state: State, lang: str) -> int:
    """Get last saved offset for language harvest."""
    state.db.execute(
        "CREATE TABLE IF NOT EXISTS provinz_checkpoints (lang TEXT PRIMARY KEY, skip INT, updated_at TEXT)"
    )
    row = state.db.execute("SELECT skip FROM provinz_checkpoints WHERE lang=?", (lang,)).fetchone()
    return row[0] if row else 0


def set_checkpoint(state: State, lang: str, skip: int) -> None:
    """Save offset for language harvest."""
    state.db.execute(
        "CREATE TABLE IF NOT EXISTS provinz_checkpoints (lang TEXT PRIMARY KEY, skip INT, updated_at TEXT)"
    )
    now = datetime.now(timezone.utc).isoformat()
    state.db.execute(
        "INSERT OR REPLACE INTO provinz_checkpoints VALUES (?, ?, ?)",
        (lang, skip, now),
    )
    state.commit()


def is_retryable_error(exc: Exception) -> bool:
    """Retry only network errors and 5xx / 429 HTTP status codes."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError, OSError)):
        return True
    msg = str(exc).lower()
    if any(k in msg for k in ("timeout", "connection", "network", "reset", "refused")):
        return True
    return False


def fetch_batch_with_retry(
    url: str,
    user_agent: str,
    lang: str,
    skip: int,
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
) -> bytes:
    """Fetch URL with exponential backoff on network/server errors (5xx, 429)."""
    last_err: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            if not is_retryable_error(e):
                log.error("Fatal non-retryable error fetching [%s] at offset skip=%d: %s", lang, skip, e)
                raise RuntimeError(
                    f"Provinz press harvest failed with non-retryable error for language '{lang}' at offset skip={skip}: {e}"
                ) from e

            log.warning("Attempt %d/%d failed for [%s] offset skip=%d: %s", attempt, max_attempts, lang, skip, e)
            if attempt < max_attempts:
                time.sleep(backoff_factor * (2 ** (attempt - 1)))
    log.error("Fatal: failed fetching [%s] at offset skip=%d after %d attempts: %s", lang, skip, max_attempts, last_err)
    raise RuntimeError(
        f"Provinz press harvest failed for language '{lang}' at offset skip={skip} after {max_attempts} attempts: {last_err}"
    )


def harvest_provinz_press(
    languages: List[str] = ["it", "de"],
    data_dir: Path = Path("data"),
    delay_seconds: float = 0.5,
    user_agent: Optional[str] = None,
    batch_size: int = 100,
    resume: bool = True,
    max_retries: int = 3,
) -> Dict[str, Any]:
    state = State(data_dir)
    ua = user_agent or load_registry().user_agent
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    started_iso = datetime.now(timezone.utc).isoformat()
    now_dt = datetime.now(timezone.utc)
    writer = JsonlWriter(data_dir, "provinz_press", run_id, now_dt)
    known = state.known_urls("provinz_press")

    total_written = 0
    total_skipped = 0
    by_lang: Dict[str, int] = {}

    with writer.open() as write:
        for lang in languages:
            skip = get_checkpoint(state, lang) if resume else 0
            lang_count = 0
            print(f"Starting harvest for [{lang.upper()}] from Kontent.ai (starting skip={skip})...")

            while True:
                url = f"{API_BASE}?system.type=news&language={lang}&order=system.last_modified[asc]&limit={batch_size}&skip={skip}&includeTotalCount=true"
                raw_bytes = fetch_batch_with_retry(
                    url=url,
                    user_agent=ua,
                    lang=lang,
                    skip=skip,
                    max_attempts=max_retries,
                    backoff_factor=delay_seconds,
                )

                # Save raw response unchanged (gzipped) with SHA-256 and fetch time
                raw_sha256 = state.save_raw_page("provinz_press", url, raw_bytes)
                data = json.loads(raw_bytes.decode("utf-8"))

                items = data.get("items", [])
                if not items:
                    set_checkpoint(state, lang, 0)
                    break

                total_available = data.get("pagination", {}).get("total_count", 0)

                for item in items:
                    parsed = parse_item(item, lang)
                    if not parsed:
                        total_skipped += 1
                        continue

                    url_norm = parsed["url"]
                    if url_norm in known:
                        total_skipped += 1
                        continue

                    chash = content_hash(parsed["full_text"])
                    sh = simhash(parsed["full_text"])
                    doc_id = f"provinz_{lang}_{hashlib.sha1(url_norm.encode()).hexdigest()[:16]}"
                    dup_of = state.exact_dup(chash) or state.near_dup(sh)

                    record = {
                        "schema_version": SCHEMA_VERSION,
                        "doc_id": doc_id,
                        "source_id": "provinz_press",
                        "source_name": "Provincia Autonoma di Bolzano / Landespresseamt",
                        "source_language": lang,
                        "source_kind": "institution",
                        "source_owner": "Provincia Autonoma di Bolzano",
                        "url": url_norm,
                        "canonical_url": url_norm,
                        "final_url": url_norm,
                        "title": parsed["title"],
                        "subtitle": parsed["subtitle"],
                        "description": parsed["subtitle"],
                        "authors": [parsed["author"]],
                        "published": parsed["publish_date"],
                        "modified": None,
                        "section": parsed["category"],
                        "keywords": parsed["tags"],
                        "language": lang,
                        "text": parsed["full_text"],
                        "word_count": parsed["word_count"],
                        "is_accessible_for_free": True,
                        "raw_sha256": raw_sha256,
                        "extraction_method": "kontent_api",
                        "trafilatura_version": None,
                        "collector_version": COLLECTOR_VERSION,
                        "wire_byline": False,
                        "wire_agency": None,
                        "content_hash": chash,
                        "simhash": format(sh, "016x"),
                        "near_dup_of": dup_of,
                        "discovered_via": "kontent_api",
                        "run_id": run_id,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "codename": parsed["codename"],
                        "raw_kontent_id": parsed["raw_id"],
                    }

                    write(record)
                    state.add_doc(
                        url=url_norm,
                        doc_id=doc_id,
                        source_id="provinz_press",
                        run_id=run_id,
                        published=parsed["publish_date"],
                        chash=chash,
                        sh=sh,
                        raw_sha256=raw_sha256,
                        wire_byline=False,
                        wire_agency=None,
                    )
                    known.add(url_norm)
                    lang_count += 1
                    total_written += 1

                skip += len(items)
                set_checkpoint(state, lang, skip)
                if skip % 1000 == 0 or skip >= total_available:
                    print(f"[{lang.upper()}] Harvested {skip}/{total_available} items...")
                if skip >= total_available:
                    set_checkpoint(state, lang, 0)
                    break
                time.sleep(delay_seconds)

            by_lang[lang] = lang_count
            state.commit()

    finished_iso = datetime.now(timezone.utc).isoformat()
    state.log_run(
        run_id=run_id,
        source_id="provinz_press",
        started=started_iso,
        finished=finished_iso,
        since=None,
        until=finished_iso,
        status="ok",
        n_candidates=total_written + total_skipped,
        n_written=total_written,
        n_failed=0,
    )
    state.commit()
    return {
        "total_written": total_written,
        "total_skipped": total_skipped,
        "by_lang": by_lang,
        "run_id": run_id,
        "output_path": str(writer.path),
    }
