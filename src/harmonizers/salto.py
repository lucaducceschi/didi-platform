"""
Harmonizer for Salto.bz (Bilingual German / Italian).
Processes scraped JSON snapshots into canonical DIDIArticle records.

The /de/ and /it/ URL prefixes only select the site's interface language: the
same article is served under both, in whatever language it was written. So the
language comes from the text, and each article is kept once.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict
from .base import BaseHarmonizer
from ..models.schema import DIDIArticle

logger = logging.getLogger("SaltoHarmonizer")

_FOOTER_RE = re.compile(r"\s*(?:Kontakt|Contatti)\s*\+39\s*0471.*?ISSN.*\Z", re.DOTALL)
_WORD_RE = re.compile(r"\w+")
_DE_WORDS = frozenset("der die das und ist nicht mit für auf von den dem ein eine auch sich wird im zu des als".split())
_IT_WORDS = frozenset("il la che di per con non una della del sono è le dei nel alla anche un si".split())
_MIN_EVIDENCE = 5  # below this many function words, flag the label as uncertain
_MIXED_RATIO = 1 / 3  # minority/majority share above which a text counts as bilingual


def detect_language(text: str, fallback: str) -> tuple[str, dict]:
    """Return (de|it, flags) by counting German and Italian function words."""
    words = _WORD_RE.findall(text.lower())
    de = sum(w in _DE_WORDS for w in words)
    it = sum(w in _IT_WORDS for w in words)
    if de == it:
        return fallback, {"language_low_evidence": True}
    if max(de, it) < _MIN_EVIDENCE:
        flags = {"language_low_evidence": True}
    else:
        flags = {"language_mixed": True} if min(de, it) / max(de, it) > _MIXED_RATIO else {}
    return ("de" if de > it else "it"), flags


class SaltoHarmonizer(BaseHarmonizer):
    """Parses Salto articles into canonical DIDIArticle records."""

    def _parse_url_date(self, url: str) -> datetime:
        """Parse DDMMYYYY pattern from Salto URL: /article/DDMMYYYY/slug."""
        match = re.search(r"/article/(\d{2})(\d{2})(\d{4})/", url)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)
        return datetime.now(timezone.utc)

    def parse_file(self, file_path: Path) -> Optional[DIDIArticle]:
        """Parse a local Salto JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self.parse_record(data)
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None

    def parse_record(self, record: Dict) -> Optional[DIDIArticle]:
        """Parse structured Salto dictionary into canonical DIDIArticle."""
        url = record.get("url", "")
        title = record.get("title", "").strip()
        full_text = _FOOTER_RE.sub("", record.get("full_text", "")).strip()
        if not title or not full_text:
            return None

        url_lang = "it" if "/it/" in url else "de"
        lang, language_flags = detect_language(f"{title}\n{full_text}", url_lang)

        # ISO date or URL date
        iso_str = record.get("publish_date")
        if iso_str:
            try:
                pub_date = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            except ValueError:
                pub_date = self._parse_url_date(url)
        else:
            pub_date = self._parse_url_date(url)

        slug_match = re.search(r"/article/\d+/([a-zA-Z0-9_\-]+)", url)
        slug = slug_match.group(1) if slug_match else title[:25].lower().replace(" ", "_")

        article_id = f"salto_{url_lang}_{pub_date.strftime('%Y%m%d')}_{slug}"
        category = record.get("category", "News")
        author = record.get("author", "Redaktion")

        return DIDIArticle(
            id=article_id,
            source="salto",
            language=lang,
            url=url,
            title=title,
            publish_date=pub_date,
            author=author,
            category=category,
            breadcrumbs=["Salto", lang.upper(), category],
            full_text=full_text,
            metadata={
                "lead": record.get("lead", ""),
                "author": author,
                "url": url,
                "url_language": url_lang,
                **language_flags,
            }
        )

    def parse_directory(self, dir_path: Path, limit: Optional[int] = None) -> List[DIDIArticle]:
        """Parse all JSON files in dir_path recursively."""
        files = sorted(dir_path.rglob("*.json"))
        if limit:
            files = files[:limit]

        # One record per article; prefer the copy whose URL prefix matches its language.
        articles: Dict[tuple, DIDIArticle] = {}
        for p in files:
            art = self.parse_file(p)
            if not art:
                continue
            key = (art.title.lower(), " ".join(_WORD_RE.findall(art.full_text.lower())))
            kept = articles.get(key)
            if kept is None or (kept.metadata["url_language"] != kept.language and art.metadata["url_language"] == art.language):
                articles[key] = art
        return list(articles.values())
