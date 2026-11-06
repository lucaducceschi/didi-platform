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

# Marker words shared with digi-rlf's sample_gold.py. The source's `region` is the region an
# article is about, not the variety it is written in, so variety is read from the text.
BADIOT_MARKERS = frozenset("le ince sön plü dles tles él gnü porsones".split())
GHERDEINA_MARKERS = frozenset("l ie plu nce sun iel unì à àn".split())
FASCIAN_HINT_RE = re.compile(r"\b(?:ence|dut|duc|sia|de la|te la|l['’][eèé]|i é|tel)\b", re.IGNORECASE)
VARIETY_THRESHOLD = 0.6
VARIETY_MIN_TOKENS = 30
FASCIAN_HINT_RATE = 0.02


def detect_badiot_or_gherdeina(text: str) -> Optional[str]:
    """Return lld_badia or lld_gherd when the marker words clearly favour one, else None."""
    tokens = re.findall(r"\w+['’]?", text)
    if len(tokens) < VARIETY_MIN_TOKENS:
        return None
    badiot = gherdeina = 0
    for token in tokens:
        low = token.lower()
        # ö/ü only in lowercase words: capitalised ones are often German names (Südtirol)
        if low in BADIOT_MARKERS or (token.islower() and ("ö" in token or "ü" in token)):
            badiot += 1
        elif low in GHERDEINA_MARKERS:
            gherdeina += 1
    score = (badiot - gherdeina) / max(1, badiot + gherdeina)
    if score > VARIETY_THRESHOLD:
        return "lld_badia"
    if score < -VARIETY_THRESHOLD:
        return "lld_gherd"
    return None


def resolve_variety(text: str, region_language: str) -> Tuple[str, Dict[str, object]]:
    """Correct a Badiot/Gherdëina region label from the text. Fascia and generic labels stay as they are."""
    if region_language not in ("lld_badia", "lld_gherd"):
        return region_language, {}
    detected = detect_badiot_or_gherdeina(text)
    if detected == region_language:
        return region_language, {}
    # The markers can't recognise Fascian, and would read it as Gherdëina, so don't relabel it.
    looks_fascian = len(FASCIAN_HINT_RE.findall(text)) / max(1, len(text.split())) > FASCIAN_HINT_RATE
    if detected is None or looks_fascian:
        return region_language, {"variety_uncertain": True}
    return detected, {"region_variety": region_language}


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
            language, variety_flags = resolve_variety(
                cleaned_text, self._detect_subvariety(url, data.get("region", ""))
            )

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
                language, variety_flags = resolve_variety(cleaned_text, self._detect_subvariety(url, region))

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
                            **variety_flags,
                        },
                    )
                )
            except Exception:
                continue

        conn.close()
        return articles
