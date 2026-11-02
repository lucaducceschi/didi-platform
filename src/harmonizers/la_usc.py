"""
Harmonizer for La Usc di Ladins (lausc.it) and RaiNews TGR TRAIL (rainews.it/tgr/trail).
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple
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

REGION_TO_LANG: Dict[str, str] = {
    "gherdeina": "lld_gherd",
    "val-badia": "lld_badia",
    "badia": "lld_badia",
    "fascia": "lld_fascia",
}


class LaUscHarmonizer(BaseHarmonizer):
    """Parses La Usc di Ladins JSON archives and the Ladin master SQLite database (La Usc + RaiNews TRAIL)."""

    def _parse_ladin_date(self, date_str: str, scraped_at: str) -> datetime:
        """Parse Ladin date string like '08 de fauré 2025', ISO timestamp, or fallback to scraped_at."""
        if date_str:
            match = re.search(r"(\d{1,2})(?:\s+de)?\s+([A-Za-zëéè]+)\s+(\d{4})", date_str, re.I)
            if match:
                day = int(match.group(1))
                m_name = match.group(2).lower()
                year = int(match.group(3))
                month = LADIN_MONTHS.get(m_name)
                if month:
                    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)
            try:
                iso_clean = re.sub(r"\+0000$", "+00:00", date_str.replace("Z", "+00:00"))
                return datetime.fromisoformat(iso_clean)
            except Exception:
                pass

        if scraped_at:
            try:
                return datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
            except Exception:
                pass

        return datetime.now(timezone.utc)

    def _detect_subvariety(self, url: str, region: str = "") -> str:
        """Detect Ladin dialect variety (Gherdëina, Badia, Fascia, or generic Ladin)."""
        reg_clean = (region or "").strip().lower()
        if reg_clean in REGION_TO_LANG:
            return REGION_TO_LANG[reg_clean]
        url_lower = (url or "").lower()
        if "gherdeina" in url_lower or "gardena" in url_lower:
            return "lld_gherd"
        elif "badia" in url_lower or "val-badia" in url_lower:
            return "lld_badia"
        elif "fascia" in url_lower:
            return "lld_fascia"
        return "lld"

    @staticmethod
    def _clean_text_and_extract_author(text: str, raw_author: str = "") -> Tuple[str, str, str]:
        """Strip trailing FOTO captions and extract inline trailing author initials on La Usc texts."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        photo_credits = []
        while lines and re.match(r"^(?:FOTO|Foto|foto)\s*:", lines[-1]):
            photo_credits.append(lines.pop())

        author = (raw_author or "").strip()
        if lines and not author:
            last = lines[-1]
            m_paren = re.search(r"\(([A-Za-z\.]{2,15})\)\s*$", last)
            if m_paren and len(last) < 25:
                author = m_paren.group(1).strip()
                lines.pop()
            elif m_paren:
                author = m_paren.group(1).strip()
            elif re.match(r"^[A-Z]{2,4}$", last):
                author = last
                lines.pop()

        cleaned = "\n\n".join(lines).strip()
        return cleaned, (author or "Redaktion"), "; ".join(reversed(photo_credits))

    def parse_file(self, file_path: Path) -> Optional[DIDIArticle]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            title = data.get("title", "").strip()
            intro_text = data.get("intro_text", "").strip()
            full_text = data.get("full_text", "").strip()
            url = data.get("url", "").strip()
            raw_id = str(data.get("id", "")).strip() or file_path.stem
            date_str = data.get("publish_date", "").strip()
            scraped_at = data.get("scraped_at", "").strip()

            combined_text = full_text
            if intro_text and not full_text.startswith(intro_text):
                combined_text = f"{intro_text}\n\n{full_text}".strip()

            cleaned_text, author, photo_credit = self._clean_text_and_extract_author(
                combined_text, data.get("author", "")
            )
            if not title or len(cleaned_text.split()) < 5:
                return None

            pub_date = self._parse_ladin_date(date_str, scraped_at)
            language = self._detect_subvariety(url, data.get("region", ""))

            breadcrumbs = []
            category = "Valedes Ladines"
            if url:
                parts = [p for p in url.replace("https://www.lausc.it/", "").split("/") if p and not p.endswith(raw_id)]
                if parts:
                    breadcrumbs = parts
                    category = parts[-1].capitalize()

            return DIDIArticle(
                id=f"lausc_{raw_id}",
                source="la_usc",
                language=language,
                url=url,
                title=title,
                publish_date=pub_date,
                author=author,
                category=category,
                breadcrumbs=breadcrumbs,
                full_text=cleaned_text,
                metadata={
                    "raw_id": raw_id,
                    "credits": data.get("credits", "") or photo_credit,
                    "data_type": data.get("data_type", "articolo"),
                    "tags": data.get("tags", ""),
                    "scraped_at": scraped_at,
                },
            )
        except Exception:
            return None

    def parse_directory(self, dir_path: Path, limit: Optional[int] = None) -> List[DIDIArticle]:
        articles = []
        json_files = sorted(dir_path.glob("*.json"))
        if limit:
            json_files = json_files[:limit]
        for f in json_files:
            art = self.parse_file(f)
            if art:
                articles.append(art)
        return articles

    def parse_master_db(self, db_path: Path, limit: Optional[int] = None) -> List[DIDIArticle]:
        """Ingest all Ladin articles (La Usc + RaiNews TGR TRAIL) from scraping_ladino/corpus_master.db."""
        articles: List[DIDIArticle] = []
        if not db_path.exists():
            return articles

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        sql = "SELECT * FROM articles WHERE length(trim(full_text)) > 0 ORDER BY id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur.execute(sql)

        for row in cur.fetchall():
            try:
                raw_source = (row["source"] or "lausc").strip().lower()
                source_label = "trail" if raw_source == "trail" else "la_usc"
                title = (row["title"] or "").strip()
                intro_text = (row["intro_text"] or "").strip()
                full_text = (row["full_text"] or "").strip()
                url = (row["url"] or "").strip()
                raw_id = str(row["source_id"] or row["id"]).strip().replace(".json", "")
                date_str = (row["publish_date"] or "").strip()
                scraped_at = (row["scraped_at"] or "").strip()
                region = (row["region"] or "").strip()
                tags = (row["tags"] or "").strip()
                themes = (row["themes"] or "").strip()

                combined_text = full_text
                if intro_text and not full_text.startswith(intro_text):
                    combined_text = f"{intro_text}\n\n{full_text}".strip()

                cleaned_text, author, photo_credit = self._clean_text_and_extract_author(
                    combined_text, row["author"] or ""
                )
                if not title or len(cleaned_text.split()) < 5:
                    continue

                pub_date = self._parse_ladin_date(date_str, scraped_at)
                language = self._detect_subvariety(url, region)

                breadcrumbs = [b.strip() for b in themes.split(",") if b.strip()] if themes else []
                category = breadcrumbs[0] if breadcrumbs else (region.capitalize() if region else "Valedes Ladines")
                if not breadcrumbs and url and source_label == "la_usc":
                    parts = [p for p in url.replace("https://www.lausc.it/", "").split("/") if p]
                    if len(parts) > 1:
                        breadcrumbs = parts[:-1]
                        category = breadcrumbs[-1].capitalize()

                prefix = "trail" if source_label == "trail" else "lausc"
                article_id = f"{prefix}_{row['id']}"

                articles.append(
                    DIDIArticle(
                        id=article_id,
                        source=source_label,
                        language=language,
                        url=url,
                        title=title,
                        publish_date=pub_date,
                        author=author,
                        category=category,
                        breadcrumbs=breadcrumbs,
                        full_text=cleaned_text,
                        metadata={
                            "raw_id": raw_id,
                            "region": region,
                            "credits": photo_credit,
                            "data_type": row["data_type"] or "articolo",
                            "tags": tags,
                            "themes": themes,
                            "scraped_at": scraped_at,
                        },
                    )
                )
            except Exception:
                continue

        conn.close()
        return articles
