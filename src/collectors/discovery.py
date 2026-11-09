"""
URL discovery for DIDI collectors: XML sitemaps, RSS feeds, URL normalization.
"""
from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urldefrag, urlencode, urljoin, urlparse, urlunparse

from dateutil import parser as dtparser
from lxml import etree

from .config import Source
from .http import PoliteSession

log = logging.getLogger(__name__)

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "dclid", "_hsenc", "_hsmi", "mc_cid", "mc_eid",
    "igshid", "ref", "ref_src"
}


@dataclass(frozen=True)
class Candidate:
    url: str
    date: Optional[datetime] = None
    via: str = ""


def parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = dtparser.parse(s.strip())
    except (ValueError, OverflowError, TypeError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _localname(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _xml_root(content: bytes):
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=True)
    return etree.fromstring(content, parser=parser)


def normalize_url(url: str) -> str:
    """Strip fragments and tracking parameters (utm_*, fbclid, etc.)."""
    url = url.strip()
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    if not parsed.query:
        return url
    query_tuples = parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [
        (k, v) for k, v in query_tuples
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    new_query = urlencode(filtered)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))


# --------------------------------------------------------------------------- sitemaps
def parse_sitemap(content: bytes) -> Tuple[List[Tuple[str, Optional[datetime]]], List[Tuple[str, Optional[datetime]]]]:
    """Return (child_sitemaps, urls), each as (loc, lastmod/publication_date)."""
    root = _xml_root(content)
    if root is None:
        return [], []
    children, urls = [], []
    kind = _localname(root)
    for entry in root:
        if _localname(entry) not in ("sitemap", "url"):
            continue
        loc, date = None, None
        for el in entry.iter():
            name = _localname(el)
            if name == "loc" and loc is None and el.text:
                loc = el.text.strip()
            elif name == "publication_date" and el.text:  # Google News sitemap
                date = parse_date(el.text)
            elif name == "lastmod" and el.text and date is None:
                date = parse_date(el.text)
        if loc:
            (children if kind == "sitemapindex" else urls).append((loc, date))
    return children, urls


def parse_salto_url_date(url: str) -> Optional[datetime]:
    import re
    m = re.search(r"/article/(\d{2})(\d{2})(\d{4})/", url)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), 12, 0, tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def from_sitemaps(
    src: Source,
    http: PoliteSession,
    since: datetime,
    max_sitemaps: int = 500,
) -> Iterator[Candidate]:
    queue = list(src.sitemaps)
    if src.use_robots_sitemaps:
        queue += [s for s in http.robots_sitemaps(src.base_url) if s not in queue]
    seen: Set[str] = set()

    cache_dir = Path("data/raw/sitemaps_cache/salto")

    while queue and len(seen) < max_sitemaps:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)

        content = None
        # Check local cache first if available
        if "salto.bz/sitemap.xml?page=" in sm and cache_dir.exists():
            try:
                page_num = int(sm.split("page=")[-1])
                cached_p = cache_dir / f"page_{page_num:02d}.xml"
                if cached_p.exists():
                    content = cached_p.read_bytes()
            except ValueError:
                pass

        if content is None:
            r = http.get(sm)
            if r is None:
                continue
            content = r.content

        children, urls = parse_sitemap(content)
        for loc, lastmod in children:
            if lastmod is None or lastmod >= since:
                queue.append(loc)
        for loc, date in urls:
            if date is None and "salto.bz" in loc:
                date = parse_salto_url_date(loc)
            if date is not None and date < since:
                continue
            norm = normalize_url(loc)
            if src.url_allowed(norm):
                yield Candidate(norm, date, via=f"sitemap:{sm}")


# --------------------------------------------------------------------------- RSS
def parse_feed(content: bytes) -> List[Tuple[str, Optional[datetime]]]:
    root = _xml_root(content)
    if root is None:
        return []
    out = []
    for item in root.iter():
        if _localname(item) not in ("item", "entry"):
            continue
        link, date = None, None
        for el in item:
            name = _localname(el)
            if name == "link":
                link = link or (el.get("href") or (el.text or "").strip() or None)
            elif name in ("pubDate", "published", "updated", "date") and date is None:
                date = parse_date(el.text)
        if link:
            out.append((link, date))
    return out


def from_rss(src: Source, http: PoliteSession, since: datetime) -> Iterator[Candidate]:
    for feed in src.rss:
        r = http.get(feed)
        if r is None:
            continue
        for link, date in parse_feed(r.content):
            if date is not None and date < since:
                continue
            norm = normalize_url(link)
            if src.url_allowed(norm):
                yield Candidate(norm, date, via=f"rss:{feed}")


def discover(
    src: Source,
    http: PoliteSession,
    since: datetime,
    known: Set[str],
) -> List[Candidate]:
    found: dict[str, Candidate] = {}
    for c in from_sitemaps(src, http, since):
        if c.url not in known and c.url not in found:
            found[c.url] = c
    for c in from_rss(src, http, since):
        if c.url not in known and c.url not in found:
            found[c.url] = c
    log.info("[%s] discovered %d candidate URLs", src.id, len(found))
    return list(found.values())

