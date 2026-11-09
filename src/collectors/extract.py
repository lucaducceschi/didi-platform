"""
Article extraction with layered fallbacks for DIDI collectors.
Uses JSON-LD, OpenGraph/Meta tags, and Trafilatura (required).
Detects wire bylines and records extractor provenance.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

import trafilatura
from bs4 import BeautifulSoup, Tag

from . import COLLECTOR_VERSION
from .discovery import parse_date

ARTICLE_TYPES = {
    "NewsArticle", "Article", "ReportageNewsArticle", "AnalysisNewsArticle",
    "OpinionNewsArticle", "BlogPosting", "LiveBlogPosting", "PressRelease"
}
BOILERPLATE = re.compile(
    r"(cookie|newsletter|abbonati|abonnieren|iscriviti|anmelden|condividi|teilen|"
    r"riproduzione riservata|alle rechte vorbehalten|pubblicità|werbung)",
    re.I,
)

WIRE_AGENCIES = ["ANSA", "Adnkronos", "APA", "dpa", "Italpress", "Reuters"]
WIRE_REGEX = re.compile(r"\b(ANSA|Adnkronos|APA|dpa|Italpress|Reuters)\b", re.IGNORECASE)


@dataclass
class Article:
    url: str
    canonical_url: Optional[str] = None
    final_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    published: Optional[datetime] = None
    modified: Optional[datetime] = None
    section: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    language: Optional[str] = None
    text: str = ""
    is_accessible_for_free: Optional[bool] = None
    extraction_method: str = ""
    trafilatura_version: str = field(default_factory=lambda: getattr(trafilatura, "__version__", "unknown"))
    collector_version: str = field(default=COLLECTOR_VERSION)
    wire_byline: bool = False
    wire_agency: Optional[str] = None

    @property
    def word_count(self) -> int:
        return len(self.text.split())


def detect_wire_agency(authors: List[str], text: str) -> Tuple[bool, Optional[str]]:
    """Flag articles whose author/byline or dateline mentions a wire agency."""
    for a in authors:
        m = WIRE_REGEX.search(a)
        if m:
            return True, m.group(1).upper()
    # Check first 250 characters (typical dateline area)
    m = WIRE_REGEX.search(text[:250])
    if m:
        return True, m.group(1).upper()
    return False, None


# ------------------------------------------------------------------ JSON-LD
def _iter_jsonld(soup: BeautifulSoup):
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = json.loads(re.sub(r"[\x00-\x1f]", " ", raw))
            except json.JSONDecodeError:
                continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop(0)
            if isinstance(node, dict):
                if "@graph" in node:
                    stack.extend(node["@graph"] if isinstance(node["@graph"], list) else [node["@graph"]])
                yield node
            elif isinstance(node, list):
                stack.extend(node)


def _types(node: dict) -> set[str]:
    t = node.get("@type", [])
    return set(t if isinstance(t, list) else [t])


def _names(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [v["name"]] if v.get("name") else []
    if isinstance(v, list):
        return [n for x in v for n in _names(x)]
    return []


def _from_jsonld(soup: BeautifulSoup, art: Article) -> None:
    for node in _iter_jsonld(soup):
        if not (_types(node) & ARTICLE_TYPES):
            continue
        art.title = art.title or node.get("headline") or node.get("name")
        art.description = art.description or node.get("description")
        art.authors = art.authors or _names(node.get("author"))
        art.published = art.published or parse_date(node.get("datePublished"))
        art.modified = art.modified or parse_date(node.get("dateModified"))
        sec = node.get("articleSection")
        art.section = art.section or (sec[0] if isinstance(sec, list) and sec else sec)
        kw = node.get("keywords")
        if kw and not art.keywords:
            art.keywords = [k.strip() for k in (kw.split(",") if isinstance(kw, str) else kw) if k]
        art.language = art.language or node.get("inLanguage")
        free = node.get("isAccessibleForFree")
        if free is not None and art.is_accessible_for_free is None:
            art.is_accessible_for_free = str(free).lower() not in ("false", "0")
        body = node.get("articleBody")
        if body and len(body.split()) > 40 and not art.text:
            art.text, art.extraction_method = _clean(body), "jsonld"


# ------------------------------------------------------------------ meta
def _meta(soup: BeautifulSoup, *keys: str) -> Optional[str]:
    for k in keys:
        el = soup.find("meta", attrs={"property": k}) or soup.find("meta", attrs={"name": k})
        if el and el.get("content"):
            return el["content"].strip()
    return None


def _from_meta(soup: BeautifulSoup, art: Article) -> None:
    art.title = art.title or _meta(soup, "og:title", "twitter:title") or (
        soup.title.get_text(strip=True) if soup.title else None
    )
    art.description = art.description or _meta(soup, "og:description", "description")
    art.published = art.published or parse_date(
        _meta(soup, "article:published_time", "pubdate", "date", "DC.date.issued")
    )
    if art.published is None:
        t = soup.find("time", attrs={"datetime": True})
        art.published = parse_date(t["datetime"]) if t else None
    art.modified = art.modified or parse_date(_meta(soup, "article:modified_time", "og:updated_time"))
    art.section = art.section or _meta(soup, "article:section")
    if not art.authors:
        a = _meta(soup, "author", "article:author")
        art.authors = [a] if a and not a.startswith("http") else []
    can = soup.find("link", rel="canonical")
    art.canonical_url = can["href"] if can and can.get("href") else _meta(soup, "og:url")
    if not art.language and soup.html and soup.html.get("lang"):
        art.language = soup.html["lang"][:2].lower()


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _paragraphs(container: Tag) -> str:
    paras = []
    for p in container.find_all(["p", "h2", "h3", "blockquote", "li"]):
        t = p.get_text(" ", strip=True)
        if len(t) < 25 or BOILERPLATE.search(t) and len(t) < 160:
            continue
        paras.append(t)
    out = [p for i, p in enumerate(paras) if i == 0 or p != paras[i - 1]]
    return _clean("\n\n".join(out))


def _density_heuristic(soup: BeautifulSoup) -> str:
    for bad in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "figure"]):
        bad.decompose()
    best, best_len = None, 0
    for cand in soup.find_all(["article", "main", "div", "section"]):
        n = sum(len(p.get_text(strip=True)) for p in cand.find_all("p", recursive=False))
        if n > best_len:
            best, best_len = cand, n
    if best is None:
        art = soup.find("article")
        best = art or soup.body
    return _paragraphs(best) if best else ""


def extract(
    html: str,
    url: str,
    body_selector: Optional[str] = None,
    final_url: Optional[str] = None,
) -> Article:
    soup = BeautifulSoup(html, "lxml")
    art = Article(url=url, final_url=final_url or url)
    _from_jsonld(soup, art)
    _from_meta(soup, art)

    # 1. Primary: Trafilatura
    if not art.text:
        txt = trafilatura.extract(
            html,
            url=final_url or url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if txt and len(txt.split()) > 30:
            art.text, art.extraction_method = _clean(txt), "trafilatura"

    # 2. Fallback: CSS selector
    if not art.text and body_selector:
        el = soup.select_one(body_selector)
        if el:
            art.text, art.extraction_method = _paragraphs(el), "selector"

    # 3. Fallback: Density heuristic
    if not art.text:
        art.text, art.extraction_method = _density_heuristic(soup), "heuristic"

    if art.title:
        art.title = _clean(art.title)

    # Check wire bylines
    wire_detected, agency = detect_wire_agency(art.authors, art.text)
    art.wire_byline = wire_detected
    art.wire_agency = agency

    return art

