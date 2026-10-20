"""
Harmonizer for La Usc di Ladins (lausc.it).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict
from .base import BaseHarmonizer
from ..models.schema import DIDIArticle

LADIN_MONTHS: Dict[str, int] = {
    "jené": 1, "jëne": 1, "jene": 1, "gennaio": 1,
    "fauré": 2, "faure": 2, "febbraio": 2,
    "merz": 3, "marzo": 3,
    "auril": 4, "avril": 4, "aprile": 4,
    "mei": 5, "maggio": 5,
    "juni": 6, "giugno": 6,
    "messel": 7, "lugio": 7, "luglio": 7,
    "agost": 8, "agosto": 8,
    "setëmber": 9, "setember": 9, "settembre": 9,
    "utober": 10, "ottobre": 10,
    "novëmber": 11, "november": 11, "novembre": 11,
    "dezëmber": 12, "dezember": 12, "dicembre": 12
}


class LaUscHarmonizer(BaseHarmonizer):
    """Parses La Usc di Ladins JSON archives into canonical DIDIArticle records."""

    def _parse_ladin_date(self, date_str: str, scraped_at: str) -> datetime:
        """Parse Ladin date string like '08 de fauré 2025' or fallback to scraped_at."""
        if date_str:
            # Pattern: DD de [month] YYYY or DD [month] YYYY
            match = re.search(r"(\d{1,2})(?:\s+de)?\s+([A-Za-zëéè]+)\s+(\d{4})", date_str, re.I)
            if match:
                day = int(match.group(1))
                m_name = match.group(2).lower()
                year = int(match.group(3))
                month = LADIN_MONTHS.get(m_name)
                if month:
                    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)

        # Fallback to scraped_at ISO timestamp
        if scraped_at:
            try:
                dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
                return dt
            except Exception:
                pass

        return datetime.now(timezone.utc)

    def _detect_subvariety(self, url: str) -> str:
        """Detect Ladin dialect variety (Gherdëina vs Badia vs generic Ladin)."""
        url_lower = url.lower()
        if "gherdeina" in url_lower or "gardena" in url_lower:
            return "lld_gherd"
        elif "badia" in url_lower or "val-badia" in url_lower:
            return "lld_badia"
        elif "fascia" in url_lower:
            return "lld_fascia"
        return "lld"

    def parse_file(self, file_path: Path) -> Optional[DIDIArticle]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            title = data.get("title", "").strip()
            intro_text = data.get("intro_text", "").strip()
            full_text = data.get("full_text", "").strip()
            url = data.get("url", "").strip()
            raw_id = data.get("id", "").strip() or file_path.stem
            date_str = data.get("publish_date", "").strip()
            scraped_at = data.get("scraped_at", "").strip()

            if not title and not full_text:
                return None

            # Combine intro and full text cleanly
            combined_text = full_text
            if intro_text and not full_text.startswith(intro_text):
                combined_text = f"{intro_text}\n\n{full_text}"

            pub_date = self._parse_ladin_date(date_str, scraped_at)
            language = self._detect_subvariety(url)

            # Extract category breadcrumbs from URL structure
            # e.g., https://www.lausc.it/valedes-ladines/gherdeina/28801-slug
            breadcrumbs = []
            category = "Valedes Ladines"
            if url:
                parts = [p for p in url.replace("https://www.lausc.it/", "").split("/") if p and not p.endswith(raw_id)]
                if parts:
                    breadcrumbs = parts
                    category = parts[-1].capitalize()

            article_id = f"lausc_{raw_id}"

            return DIDIArticle(
                id=article_id,
                source="la_usc",
                language=language,
                url=url,
                title=title,
                publish_date=pub_date,
                category=category,
                breadcrumbs=breadcrumbs,
                full_text=combined_text,
                metadata={
                    "raw_id": raw_id,
                    "credits": data.get("credits", ""),
                    "data_type": data.get("data_type", "articolo"),
                    "tags": data.get("tags", ""),
                    "scraped_at": scraped_at
                }
            )
        except Exception:
            return None

    def parse_directory(self, dir_path: Path, limit: Optional[int] = None) -> List[DIDIArticle]:
        articles = []
        json_files = list(dir_path.glob("*.json"))
        if limit:
            json_files = json_files[:limit]
        for f in json_files:
            art = self.parse_file(f)
            if art:
                articles.append(art)
        return articles
