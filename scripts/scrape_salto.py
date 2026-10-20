#!/usr/bin/env python3
"""
Salto.bz Scraper & Raw Storage
Downloads German and Italian articles from salto.bz sitemap URLs
and stores raw JSON snapshots locally.
"""

import argparse
import json
import logging
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SaltoScraper")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
WGET_LOG = Path(os.environ.get("SALTO_WGET_LOG", str(Path.home() / "Data" / "KST" / "salto" / "sitemap-wget.log")))
OUTPUT_DIR = Path(os.environ.get("SALTO_OUTPUT_DIR", str(Path(__file__).resolve().parent.parent / "data" / "raw" / "salto")))


def extract_urls(log_path: Path) -> Dict[str, List[str]]:
    """Extract German and Italian article URLs from log."""
    urls = set()
    if not log_path.exists():
        logger.warning(f"Log path {log_path} not found.")
        return {"de": [], "it": []}

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            matches = re.findall(r"https://salto\.bz/(de|it)/article/\d{8}/[a-zA-Z0-9_\-]+", line)
            if matches:
                # Re-extract full URL
                for m in re.finditer(r"https://salto\.bz/(de|it)/article/\d{8}/[a-zA-Z0-9_\-]+", line):
                    urls.add(m.group(0))

    de_urls = sorted([u for u in urls if "/de/" in u])
    it_urls = sorted([u for u in urls if "/it/" in u])
    return {"de": de_urls, "it": it_urls}


def parse_html(html: str, url: str) -> Optional[Dict]:
    """Extract structured article data from HTML."""
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Title
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "").replace(" | SALTO", "").strip()

        # Lead / Subhead
        lead_div = soup.find("div", class_="lead")
        lead = lead_div.get_text(strip=True) if lead_div else ""

        # Body paragraphs
        paragraphs = []
        # 1. Paragraph entities
        for p_div in soup.find_all("div", class_="field--name-field-text-body"):
            for elem in p_div.find_all(["p", "h2", "h3"]):
                txt = elem.get_text(strip=True)
                if txt and len(txt) > 15:
                    paragraphs.append(txt)

        # 2. Classic body entity fallback
        if not paragraphs:
            for b_div in soup.find_all("div", class_="field--name-body"):
                for elem in b_div.find_all(["p", "h2", "h3"]):
                    txt = elem.get_text(strip=True)
                    if txt and len(txt) > 15:
                        paragraphs.append(txt)

        # Filter boilerplate / ads
        clean_paras = []
        for p in paragraphs:
            if any(b in p for b in ["Cookiebot", "SALTO abonnieren", "Jetzt S+ abonnieren", "Abonnement"]):
                continue
            clean_paras.append(p)

        full_body = "\n\n".join(clean_paras)
        full_text = f"{lead}\n\n{full_body}".strip() if lead else full_body

        if len(full_text.split()) < 10:
            return None

        # Author
        byline = soup.find("div", class_="byline")
        author = byline.get_text(" ", strip=True) if byline else "Redaktion"
        author = re.sub(r"^(von|di)\s*", "", author).strip()

        # Category
        cat_span = soup.find("span", class_="salto-header__context-label")
        category = cat_span.get_text(strip=True) if cat_span else "News"

        # Date from URL
        date_match = re.search(r"/article/(\d{2})(\d{2})(\d{4})/", url)
        iso_date = ""
        if date_match:
            d, m, y = date_match.group(1), date_match.group(2), date_match.group(3)
            iso_date = f"{y}-{m}-{d}T12:00:00Z"

        lang = "it" if "/it/" in url else "de"

        return {
            "url": url,
            "title": title,
            "lead": lead,
            "author": author,
            "category": category,
            "publish_date": iso_date,
            "language": lang,
            "full_text": full_text,
            "paragraphs": clean_paras,
            "word_count": len(full_text.split()),
        }
    except Exception as e:
        logger.error(f"Error parsing HTML for {url}: {e}")
        return None


def fetch_and_save(url: str, output_dir: Path) -> Optional[Dict]:
    """Fetch article and save to raw JSON."""
    match = re.search(r"/article/\d{8}/([a-zA-Z0-9_\-]+)", url)
    slug = match.group(1) if match else "article"
    lang = "it" if "/it/" in url else "de"
    out_file = output_dir / lang / f"{slug}.json"

    if out_file.exists():
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            data = parse_html(html, url)
            if data:
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return data
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {e}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Scrape Salto.bz articles")
    parser.add_argument("--limit-per-lang", type=int, default=50, help="Max articles to download per language")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent worker threads")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "de").mkdir(exist_ok=True)
    (OUTPUT_DIR / "it").mkdir(exist_ok=True)

    url_dict = extract_urls(WGET_LOG)
    logger.info(f"Loaded {len(url_dict['de'])} German URLs and {len(url_dict['it'])} Italian URLs.")

    for lang in ["de", "it"]:
        targets = url_dict[lang][:args.limit_per_lang]
        logger.info(f"Downloading {len(targets)} {lang.upper()} articles with {args.workers} workers...")
        success = 0
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_url = {executor.submit(fetch_and_save, u, OUTPUT_DIR): u for u in targets}
            for future in as_completed(future_to_url):
                res = future.result()
                if res:
                    success += 1
        logger.info(f"Finished {lang.upper()}: {success}/{len(targets)} articles saved.")


if __name__ == "__main__":
    main()
