"""
Harmonizer for Salto.bz (Bilingual German / Italian).
Processes scraped JSON snapshots into canonical DIDIArticle records.
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
        full_text = record.get("full_text", "").strip()
        if not title or not full_text:
            return None

        lang = record.get("language")
        if not lang:
            lang = "it" if "/it/" in url else "de"

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

        article_id = f"salto_{lang}_{pub_date.strftime('%Y%m%d')}_{slug}"
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
            }
        )

    def parse_directory(self, dir_path: Path, limit: Optional[int] = None) -> List[DIDIArticle]:
        """Parse all JSON files in dir_path recursively."""
        articles = []
        files = list(dir_path.rglob("*.json"))
        if limit:
            files = files[:limit]

        for p in files:
            art = self.parse_file(p)
            if art:
                articles.append(art)
        return articles
