"""
Core pipeline orchestration for DIDI collectors.
Performs discover -> fetch -> raw page save -> extract -> filter -> dedup -> store.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import Registry, Source
from .dedup import content_hash, simhash
from .discovery import Candidate, discover, normalize_url
from .extract import extract
from .http import PoliteSession
from .store import JsonlWriter, State

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2
OVERLAP = timedelta(days=7)
FIRST_RUN_LOOKBACK = timedelta(days=100)
MIN_WORDS = 30


def resolve_window(
    state: State,
    src: Source,
    since: Optional[datetime],
    until: Optional[datetime],
) -> Tuple[datetime, datetime]:
    until = until or datetime.now(timezone.utc)
    if since is None:
        last = state.last_success(src.id)
        since = (last - OVERLAP) if last else (until - FIRST_RUN_LOOKBACK)
    return since, until


def run_source(
    src: Source,
    reg: Registry,
    data_dir: Path,
    run_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: Optional[int] = None,
    max_pages: int = 2000,
    dry_run: bool = False,
) -> Dict[str, Any]:
    state = State(data_dir)
    since, until = resolve_window(state, src, since, until)
    started = datetime.now(timezone.utc)
    log.info("[%s] window: %s to %s", src.id, since.date(), until.date())

    http = PoliteSession(reg.user_agent, src.delay_seconds, src.respect_robots)

    known = state.known_urls(src.id)
    cands = [c for c in discover(src, http, since, known) if c.url not in known]
    cands += [
        Candidate(u, None, "retry")
        for u in state.retryable_failures(src.id)
        if u not in {c.url for c in cands}
    ]

    # Cap by max_pages (default 2,000) or user limit
    cap = min(limit or max_pages, max_pages)
    cands = cands[:cap]

    if dry_run:
        for c in cands:
            d_str = c.date.isoformat() if c.date else "unknown-date"
            print(f"{d_str:25} {c.url}")
        return {
            "source": src.id,
            "candidates": len(cands),
            "written": 0,
            "failed": 0,
            "dry_run": True,
        }

    writer = JsonlWriter(data_dir, src.id, run_id, until)
    n_fail = n_window = 0

    with writer.open() as write:
        for i, c in enumerate(cands, 1):
            r = http.get(c.url)
            if r is None:
                state.add_failure(c.url, src.id, "fetch_error")
                n_fail += 1
                continue

            # Save raw gzipped page and compute sha256
            raw_sha256 = state.save_raw_page(src.id, c.url, r.content)

            final_url = normalize_url(r.url)
            art = extract(r.text, c.url, src.body_selector, final_url=final_url)
            pub = art.published or c.date
            if pub is None:
                state.add_failure(c.url, src.id, "no_date")
                n_fail += 1
                continue

            if not (since <= pub <= until):
                state.add_failure(c.url, src.id, f"out_of_window:{pub.date()}")
                n_window += 1
                continue

            if art.word_count < MIN_WORDS:
                state.add_failure(c.url, src.id, f"short:{art.word_count}")
                n_fail += 1
                continue

            doc_id = f"{src.id}:{hashlib.sha1(c.url.encode()).hexdigest()[:16]}"
            chash, sh = content_hash(art.text), simhash(art.text)
            dup_of = state.exact_dup(chash) or state.near_dup(sh)

            rec = {
                "schema_version": SCHEMA_VERSION,
                "doc_id": doc_id,
                "source_id": src.id,
                "source_name": src.name,
                "source_language": src.language,
                "source_kind": src.kind,
                "source_owner": src.owner,
                "url": c.url,
                "canonical_url": art.canonical_url or c.url,
                "final_url": final_url,
                "title": art.title,
                "description": art.description,
                "authors": art.authors,
                "published": pub.isoformat(),
                "modified": art.modified.isoformat() if art.modified else None,
                "section": art.section,
                "keywords": art.keywords,
                "language": art.language or src.language,
                "text": art.text,
                "word_count": art.word_count,
                "is_accessible_for_free": art.is_accessible_for_free,
                "raw_sha256": raw_sha256,
                "extraction_method": art.extraction_method,
                "trafilatura_version": art.trafilatura_version,
                "collector_version": art.collector_version,
                "wire_byline": art.wire_byline,
                "wire_agency": art.wire_agency,
                "content_hash": chash,
                "simhash": format(sh, "016x"),
                "near_dup_of": dup_of,
                "discovered_via": c.via,
                "run_id": run_id,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            write(rec)
            state.add_doc(
                url=c.url,
                doc_id=doc_id,
                source_id=src.id,
                run_id=run_id,
                published=rec["published"],
                chash=chash,
                sh=sh,
                raw_sha256=raw_sha256,
                wire_byline=art.wire_byline,
                wire_agency=art.wire_agency,
            )

            if i % 25 == 0 or i == len(cands):
                state.commit()
                log.info("[%s] %d/%d processed, %d saved", src.id, i, len(cands), writer.n)

    state.log_run(
        run_id=run_id,
        source_id=src.id,
        started=started.isoformat(),
        finished=datetime.now(timezone.utc).isoformat(),
        since=since.isoformat(),
        until=until.isoformat(),
        status="ok" if writer.n else "empty",
        n_candidates=len(cands),
        n_written=writer.n,
        n_failed=n_fail,
    )
    state.commit()

    if writer.n == 0 and writer.path.exists():
        writer.path.unlink()

    return {
        "source": src.id,
        "candidates": len(cands),
        "written": writer.n,
        "failed": n_fail,
        "out_of_window": n_window,
        "output": str(writer.path) if writer.n else None,
    }


def probe(src: Source, reg: Registry) -> Dict[str, Any]:
    """Health check for a source config: robots permissions, sitemaps, feeds, test extraction."""
    http = PoliteSession(reg.user_agent, src.delay_seconds, src.respect_robots)
    since = datetime.now(timezone.utc) - timedelta(days=14)

    report: Dict[str, Any] = {
        "source": src.id,
        "base_url": src.base_url,
        "robots_sitemaps": http.robots_sitemaps(src.base_url),
        "homepage_allowed": http.allowed(src.base_url),
    }

    cands = discover(src, http, since, set())
    report["candidates_recent"] = len(cands)
    report["by_channel"] = {}
    for c in cands:
        ch = c.via.split(":")[0]
        report["by_channel"][ch] = report["by_channel"].get(ch, 0) + 1

    if cands:
        sample_c = cands[0]
        r = http.get(sample_c.url)
        if r is not None:
            a = extract(r.text, sample_c.url, src.body_selector, final_url=r.url)
            report["sample"] = {
                "url": sample_c.url,
                "title": a.title,
                "published": str(a.published),
                "authors": a.authors,
                "words": a.word_count,
                "method": a.extraction_method,
                "trafilatura_version": a.trafilatura_version,
                "wire_byline": a.wire_byline,
                "wire_agency": a.wire_agency,
                "head": a.text[:300],
            }
    return report

