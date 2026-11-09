"""
Collector for Autonomous Province of Bolzano (Landespresseamt / Ufficio Stampa).
Fetches official press releases via Kontent.ai Delivery API in Italian and German.
Links bilingual twins (DE <-> IT) via system.codename / system.id.
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
from .dedup import content_hash, simhash
from .store import State, JsonlWriter

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
    raw_html = (
        elems.get("normal_text", {}).get("value")
        or elems.get("text", {}).get("value")
        or elems.get("long_text", {}).get("value")
        or ""
    )
    body_text = clean_rich_text(raw_html)
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


def harvest_provinz_press(
    languages: List[str] = ["it", "de"],
    data_dir: Path = Path("data"),
    delay_seconds: float = 0.5,
    user_agent: str = "DIDI-research-crawler/0.1 (Eurac Research)",
    batch_size: int = 100,
) -> Dict[str, Any]:
    state = State(data_dir)
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    now_dt = datetime.now(timezone.utc)
    writer = JsonlWriter(data_dir, "provinz_press", run_id, now_dt)
    known = state.known_urls("provinz_press")

    total_written = 0
    total_skipped = 0
    by_lang: Dict[str, int] = {}

    with writer.open() as write:
        for lang in languages:
            skip = 0
            lang_count = 0
            print(f"Starting harvest for [{lang.upper()}] from Kontent.ai...")

            while True:
                url = f"{API_BASE}?system.type=news&language={lang}&limit={batch_size}&skip={skip}&includeTotalCount=true"
                req = urllib.request.Request(url, headers={"User-Agent": user_agent})
                try:
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                except Exception as e:
                    print(f"Error fetching [{lang}] skip={skip}: {e}")
                    break

                items = data.get("items", [])
                if not items:
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
                        "raw_sha256": None,
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
                        raw_sha256="",
                        wire_byline=False,
                        wire_agency=None,
                    )
                    known.add(url_norm)
                    lang_count += 1
                    total_written += 1

                skip += len(items)
                if skip % 1000 == 0 or skip >= total_available:
                    print(f"[{lang.upper()}] Harvested {skip}/{total_available} items...")
                if skip >= total_available:
                    break
                time.sleep(delay_seconds)

            by_lang[lang] = lang_count
            state.commit()

    state.commit()
    return {
        "total_written": total_written,
        "total_skipped": total_skipped,
        "by_lang": by_lang,
        "run_id": run_id,
        "output_path": str(writer.path),
    }
