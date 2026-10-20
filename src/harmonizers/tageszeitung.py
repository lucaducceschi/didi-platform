"""
Harmonizer for Neue Südtiroler Tageszeitung (tageszeitung.it).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict
from .base import BaseHarmonizer
from ..models.schema import DIDIArticle

GERMAN_MONTHS: Dict[str, int] = {
    "januar": 1, "jänner": 1, "jan": 1,
    "februar": 2, "feb": 2,
    "märz": 3, "mar": 3, "mrz": 3,
    "april": 4, "apr": 4,
    "mai": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "dez": 12
}


class TageszeitungHarmonizer(BaseHarmonizer):
    """Parses Tageszeitung JSON scraped files into canonical DIDIArticle records."""

    def _parse_german_date(self, date_str: str, file_name: str) -> datetime:
        """Parse date string like 'erstellt:  06. Mai 2025, 05:49' or fallback to filename."""
        # 1. Try regex on date_str: DD. Month YYYY[, HH:MM]
        match = re.search(r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s*(\d{4})(?:,\s*(\d{1,2}):(\d{2}))?", date_str)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else 12
            minute = int(match.group(5)) if match.group(5) else 0

            month = GERMAN_MONTHS.get(month_name)
            if month:
                return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)

        # 2. Fallback to filename pattern: e.g. 2025_05_06
        fn_match = re.search(r"(\d{4})_(\d{2})_(\d{2})", file_name)
        if fn_match:
            year, month, day = int(fn_match.group(1)), int(fn_match.group(2)), int(fn_match.group(3))
            return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)

        # 3. Default fallback
        return datetime.now(timezone.utc)

    def parse_file(self, file_path: Path) -> Optional[DIDIArticle]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            title = data.get("title", "").strip()
            content = data.get("content", "").strip()
            crumbs_str = data.get("crumbs", "")
            date_str = data.get("date", "")

            # Reconstruct URL and slug from filename
            # Filename format: https:__www.tageszeitung.it_2025_05_06_keine-echte-autonomie_.json
            fn = file_path.name
            clean_url = fn.replace("https:__", "https://").replace("http:__", "http://").replace("_.json", "").replace(".json", "")
            clean_url = clean_url.replace("_", "/")

            slug_match = re.search(r"\d{4}_\d{2}_\d{2}_(.*?)_\.json$", fn)
            slug = slug_match.group(1) if slug_match else re.sub(r"[^a-zA-Z0-9-]", "", title[:40].lower().replace(" ", "-"))

            pub_date = self._parse_german_date(date_str, fn)
            article_id = f"taz_{pub_date.strftime('%Y%m%d')}_{slug}"

            # Parse breadcrumbs: "Du befindest dich hier: Home » Südtirol » „Keine echte Autonomie“"
            breadcrumbs = []
            category = "Südtirol"
            if crumbs_str:
                parts = [p.strip() for p in crumbs_str.replace("Du befindest dich hier:", "").split("»")]
                breadcrumbs = [p for p in parts if p and p != title]
                if len(breadcrumbs) > 1:
                    category = breadcrumbs[1]
                elif len(breadcrumbs) == 1:
                    category = breadcrumbs[0]

            return DIDIArticle(
                id=article_id,
                source="tageszeitung",
                language="de",
                url=clean_url,
                title=title,
                publish_date=pub_date,
                category=category,
                breadcrumbs=breadcrumbs,
                full_text=content,
                metadata={"raw_date_string": date_str, "crumbs_string": crumbs_str}
            )
        except Exception as e:
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
