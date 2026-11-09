"""
Neue Südtiroler Tageszeitung Ingestion & Word Layer Pipeline.

Streams Stanza-annotated CoNLL-U files and JSON archives, aligns character
offsets to full_text, preserves existing DIDI articles, and writes
word-level tokens to the dedicated word layer database.
"""

import io
import json
import logging
import re
import sqlite3
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Set, Tuple

from ..harmonizers.tageszeitung import GERMAN_MONTHS
from ..storage.word_layer import init_words_db, insert_words_batch

logger = logging.getLogger("TageszeitungImporter")


def normalize_url(url: str) -> str:
    """Normalize article URL by stripping trailing slash."""
    return url.strip().rstrip("/")


def parse_german_date(date_str: Optional[str], url: str) -> datetime:
    """
    Parse date from German date string (e.g. '14. Mai 2015, 12:12'),
    or fallback to URL path components /YYYY/MM/DD/.
    """
    if date_str:
        m = re.search(
            r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s*(\d{4})(?:,\s*(\d{1,2}):(\d{2}))?",
            date_str,
        )
        if m:
            day = int(m.group(1))
            month_name = m.group(2).lower()
            year = int(m.group(3))
            hour = int(m.group(4)) if m.group(4) else 12
            minute = int(m.group(5)) if m.group(5) else 0
            month = GERMAN_MONTHS.get(month_name)
            if month:
                return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)

    # Fallback to URL: https://www.tageszeitung.it/YYYY/MM/DD/...
    url_m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if url_m:
        year, month, day = int(url_m.group(1)), int(url_m.group(2)), int(url_m.group(3))
        return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)

    return datetime.now(timezone.utc)


def make_article_id(pub_date: datetime, url: str) -> str:
    """Generate canonical DIDI article ID: taz_YYYYMMDD_<slug>."""
    norm_url = normalize_url(url)
    slug = norm_url.split("/")[-1]
    # Clean slug of invalid characters
    slug = re.sub(r"[^a-zA-Z0-9_-]", "", slug)
    date_prefix = pub_date.strftime("%Y%m%d")
    return f"taz_{date_prefix}_{slug}"


def extract_words_from_conll(
    conll_lines: Iterable[str],
    title: str,
    full_text: str,
    article_id: str,
) -> Tuple[List[Dict[str, Any]], bool, str]:
    """
    Extract token-level word layer from CoNLL lines.
    
    Offsets in CoNLL are indexed from `title + '\\n' + content`.
    Shifts offsets by `-(len(title) + 1)` so they map strictly to full_text.
    Multi-word tokens: the individual words share the MWT's character span.
    Validates that `full_text[start:end] == form` for non-MWT tokens.
    Returns (words, is_valid, error_reason).
    """
    shift = len(title) + 1
    words: List[Dict[str, Any]] = []
    token_idx = 0

    last_mwt_span: Optional[Tuple[int, int]] = None
    last_mwt_range: Optional[Set[int]] = None

    for raw_line in conll_lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 10:
            continue

        t_id_str, form, lemma, upos, xpos, feats, head, deprel, deps, misc = parts

        # Check for multi-word token range header, e.g. '1-2 Beim'
        if "-" in t_id_str:
            m = re.search(r"start_char=(\d+)\|end_char=(\d+)", misc)
            if m:
                last_mwt_span = (int(m.group(1)), int(m.group(2)))
                try:
                    rng = [int(x) for x in t_id_str.split("-")]
                    last_mwt_range = set(range(rng[0], rng[1] + 1))
                except ValueError:
                    last_mwt_range = None
            continue

        # Extract character positions
        sc_match = re.search(r"start_char=(\d+)\|end_char=(\d+)", misc)
        is_mwt_part = False

        if not sc_match and last_mwt_span and last_mwt_range:
            try:
                t_id = int(t_id_str)
                if t_id in last_mwt_range:
                    sc, ec = last_mwt_span
                    is_mwt_part = True
                else:
                    continue
            except ValueError:
                continue
        elif sc_match:
            sc, ec = int(sc_match.group(1)), int(sc_match.group(2))
        else:
            continue

        # Skip tokens belonging to the title
        if sc < shift:
            continue

        c_sc = sc - shift
        c_ec = ec - shift

        # Validation bounds check
        if c_sc < 0 or c_ec > len(full_text):
            return (
                [],
                False,
                f"Offset out of bounds: [{c_sc}:{c_ec}] for full_text len {len(full_text)}",
            )

        # Token form alignment check
        if not is_mwt_part:
            extracted = full_text[c_sc:c_ec]
            if extracted != form:
                return (
                    [],
                    False,
                    f"Token mismatch at [{c_sc}:{c_ec}]: full_text='{extracted}' != form='{form}'",
                )

        ner_match = re.search(r"ner=([^|]+)", misc)
        ner = ner_match.group(1) if ner_match else "O"

        words.append(
            {
                "article_id": article_id,
                "token_idx": token_idx,
                "start_char": c_sc,
                "end_char": c_ec,
                "form": form,
                "lemma": lemma,
                "upos": upos,
                "xpos": xpos if xpos != "_" else None,
                "feats": feats if feats != "_" else None,
                "ner": ner,
            }
        )
        token_idx += 1

    return words, True, ""


def stream_conll_articles(
    file_obj: io.BufferedReader,
) -> Generator[Tuple[str, List[str]], None, None]:
    """
    Stream a CoNLL-U file line-by-line, yielding (url, lines) per article.
    Memory footprint is bounded to a single article's annotations.
    """
    current_url: Optional[str] = None
    current_lines: List[str] = []

    for raw_bytes in file_obj:
        line = raw_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
        if line.startswith("<url = \""):
            if current_url:
                yield current_url, current_lines
            current_url = line[8:-2]
            current_lines = []
        elif current_url:
            current_lines.append(line)

    if current_url:
        yield current_url, current_lines

