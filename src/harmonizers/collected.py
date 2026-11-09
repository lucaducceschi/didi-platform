"""
Harmonizer for collected open media & institutional records.
Transforms raw JSONL records from collectors (provinz_press, rai_tgr_bolzano, salto_it)
into canonical DIDIArticle records, linking bilingual twins and preserving exact text.
"""
from __future__ import annotations

import gzip
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from ..models.schema import DIDIArticle
from ..sources import SOURCE_REGISTRY

log = logging.getLogger(__name__)

PREFIX_MAP = {
    "salto_it": "salto_it",
    "salto": "salto",
    "provinz_press": "provinz",
    "provinz_news": "provinz",
    "rai_tgr_bolzano": "rai_it",
    "rai_bolzano": "rai_it",
}


def slugify(text: str, max_len: int = 40) -> str:
    """Normalize text into an alphanumeric slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len].strip("-") or "item"


def parse_date(date_val: Any) -> datetime:
    """Parse various ISO formats into UTC datetime."""
    if isinstance(date_val, datetime):
        return date_val if date_val.tzinfo else date_val.replace(tzinfo=timezone.utc)
    if isinstance(date_val, str) and date_val.strip():
        s = date_val.strip().replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(s)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class CollectedHarmonizer:
    """Harmonizes raw collector JSONL records into canonical DIDIArticle instances."""

    def __init__(self, existing_urls: Optional[Set[str]] = None):
        # Normalized URLs of articles already in the DIDI database
        self.existing_urls: Set[str] = existing_urls or set()

    def normalize_url_for_dedup(self, url: str) -> str:
        """Strip http/https, trailing slash, and language prefix for matching existing articles."""
        u = re.sub(r"^https?://", "", url.lower().strip()).rstrip("/")
        # For Salto, /it/article/ and /de/article/ point to the same content
        u = re.sub(r"^salto\.bz/(it|de)/article/", "salto.bz/article/", u)
        return u

    def generate_id(self, source_id: str, lang: str, pub_date: datetime, slug_hint: str) -> str:
        prefix = PREFIX_MAP.get(source_id, source_id)
        date_str = pub_date.strftime("%Y%m%d")
        clean_slug = slugify(slug_hint)
        if prefix == "provinz":
            return f"provinz_{lang}_{date_str}_{clean_slug}"
        return f"{prefix}_{date_str}_{clean_slug}"

    def harmonize_record(self, record: Dict[str, Any]) -> Optional[DIDIArticle]:
        """Harmonize a single collector dictionary into a DIDIArticle."""
        url = (record.get("canonical_url") or record.get("url") or "").strip()
        if not url:
            return None

        # Check if already present in database
        norm_url = self.normalize_url_for_dedup(url)
        if norm_url in self.existing_urls:
            return None

        title = (record.get("title") or "").strip()
        full_text = (record.get("text") or record.get("full_text") or "").strip()
        if not title or not full_text:
            return None

        pub_date = parse_date(record.get("published") or record.get("publish_date"))
        raw_source = record.get("source_id") or record.get("source") or "unknown"

        # Determine target source key
        if "provinz" in raw_source:
            source = "provinz_news"
            source_type = "official_press"
            category = record.get("section") or record.get("category") or "Landesverwaltung"
            lang = record.get("language") or record.get("source_language") or "it"
        elif "rai" in raw_source:
            source = "rai_bolzano"
            source_type = "journalism"
            category = record.get("section") or record.get("category") or "Cronaca"
            lang = "it"
        else:
            source = "salto"
            source_type = "journalism"
            category = record.get("section") or record.get("category") or "News"
            lang = record.get("language") or "it"

        # Derive slug hint from URL or codename or title
        slug_hint = ""
        url_match = re.search(r"/(?:article|news)/\d{8}/([a-zA-Z0-9_\-]+)", url)
        if url_match:
            slug_hint = url_match.group(1)
        elif "/news/" in url:
            slug_hint = url.split("/news/")[-1].split("?")[0]
        elif record.get("codename"):
            slug_hint = record["codename"]
        else:
            slug_hint = title

        article_id = self.generate_id(raw_source, lang, pub_date, slug_hint)

        # Author
        authors = record.get("authors") or []
        author = authors[0] if (isinstance(authors, list) and authors) else record.get("author") or "Redaktion"
        if source == "provinz_news" and (not author or author == "Redaktion"):
            author = "USP"

        # Metadata
        meta: Dict[str, Any] = {
            "wire_byline": bool(record.get("wire_byline")),
            "wire_agency": record.get("wire_agency"),
            "content_hash": record.get("content_hash"),
            "simhash": record.get("simhash"),
            "near_dup_of": record.get("near_dup_of"),
            "raw_sha256": record.get("raw_sha256"),
            "extraction_method": record.get("extraction_method"),
            "collector_version": record.get("collector_version"),
        }
        if record.get("codename"):
            meta["codename"] = record["codename"]
        if record.get("raw_kontent_id"):
            meta["raw_kontent_id"] = record["raw_kontent_id"]

        breadcrumbs = record.get("keywords") or record.get("breadcrumbs") or []
        if isinstance(breadcrumbs, str):
            breadcrumbs = [breadcrumbs]

        return DIDIArticle(
            id=article_id,
            source=source,
            language=lang,
            url=url,
            title=title,
            publish_date=pub_date,
            author=author,
            source_type=source_type,
            category=category,
            breadcrumbs=breadcrumbs,
            full_text=full_text,
            word_count=len(full_text.split()),
            local_provenance_score=1.0,
            geographic_scope="Südtirol/Alto Adige",
            wire_agency_detected=record.get("wire_agency"),
            metadata=meta,
        )


def link_bilingual_twins(articles: List[DIDIArticle]) -> None:
    """Link Italian and German twin press releases via their shared codename."""
    codename_map: Dict[str, Dict[str, DIDIArticle]] = {}
    for art in articles:
        codename = art.metadata.get("codename")
        if codename:
            codename_map.setdefault(codename, {})[art.language] = art

    linked = 0
    for codename, twins in codename_map.items():
        if "it" in twins and "de" in twins:
            twins["it"].metadata["twin_article_id"] = twins["de"].id
            twins["it"].metadata["twin_url"] = twins["de"].url
            twins["de"].metadata["twin_article_id"] = twins["it"].id
            twins["de"].metadata["twin_url"] = twins["it"].url
            linked += 1

    log.info("Linked %d bilingual twin release pairs.", linked)

