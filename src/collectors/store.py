"""
Storage for DIDI collectors:
- Raw HTML pages saved gzipped with SHA-256 and fetch time
- Gzipped JSONL records with extraction metadata
- SQLite state tracking seen URLs, runs, failures, and SimHash index
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set

from .dedup import bands, hamming, to_signed, to_unsigned

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT, source_id TEXT, started TEXT, finished TEXT,
  since TEXT, until TEXT, status TEXT, n_candidates INT, n_written INT, n_failed INT,
  PRIMARY KEY (run_id, source_id));

CREATE TABLE IF NOT EXISTS docs (
  url TEXT PRIMARY KEY, doc_id TEXT, source_id TEXT, run_id TEXT,
  published TEXT, content_hash TEXT, simhash INT, raw_sha256 TEXT,
  wire_byline INT, wire_agency TEXT, fetched_at TEXT);

CREATE TABLE IF NOT EXISTS raw_pages (
  sha256 TEXT PRIMARY KEY, url TEXT, fetched_at TEXT, byte_size INT, path TEXT);

CREATE TABLE IF NOT EXISTS failures (
  url TEXT PRIMARY KEY, source_id TEXT, reason TEXT, retryable INT, attempts INT, last_try TEXT);

CREATE TABLE IF NOT EXISTS sim_bands (band INT, value INT, doc_id TEXT);
CREATE INDEX IF NOT EXISTS ix_bands ON sim_bands(band, value);
CREATE INDEX IF NOT EXISTS ix_docs_hash ON docs(content_hash);
"""


def quarter_of(d: datetime) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


class State:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.state_dir = self.data_dir / "raw" / "collected"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.state_dir / "state.sqlite")
        self.db.executescript(SCHEMA)

    def last_success(self, source_id: str) -> Optional[datetime]:
        row = self.db.execute(
            "SELECT MAX(until) FROM runs WHERE source_id=? AND status='ok'", (source_id,)
        ).fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def log_run(self, **kw) -> None:
        cols = ",".join(kw)
        self.db.execute(
            f"INSERT OR REPLACE INTO runs ({cols}) VALUES ({','.join('?' * len(kw))})",
            tuple(kw.values()),
        )
        self.db.commit()

    def known_urls(self, source_id: str) -> Set[str]:
        return {r[0] for r in self.db.execute("SELECT url FROM docs WHERE source_id=?", (source_id,))}

    def exact_dup(self, chash: str) -> Optional[str]:
        r = self.db.execute("SELECT doc_id FROM docs WHERE content_hash=? LIMIT 1", (chash,)).fetchone()
        return r[0] if r else None

    def near_dup(self, sh: int, max_dist: int = 3) -> Optional[str]:
        cands: Set[str] = set()
        for i, v in enumerate(bands(sh)):
            cands |= {r[0] for r in self.db.execute(
                "SELECT doc_id FROM sim_bands WHERE band=? AND value=?", (i, v)
            )}
        best, best_d = None, max_dist + 1
        for doc_id in cands:
            r = self.db.execute("SELECT simhash FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
            if r is None:
                continue
            d = hamming(sh, to_unsigned(r[0]))
            if d < best_d:
                best, best_d = doc_id, d
        return best

    def save_raw_page(self, source_id: str, url: str, content: bytes) -> str:
        """Save raw downloaded page unchanged (gzipped) with SHA-256 and fetch time."""
        sha256 = hashlib.sha256(content).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        pages_dir = self.state_dir / source_id / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        page_path = pages_dir / f"{sha256}.html.gz"

        if not page_path.exists():
            with gzip.open(page_path, "wb") as f:
                f.write(content)

        self.db.execute(
            "INSERT OR REPLACE INTO raw_pages VALUES (?,?,?,?,?)",
            (sha256, url, now, len(content), str(page_path)),
        )
        return sha256

    def add_doc(
        self,
        *,
        url: str,
        doc_id: str,
        source_id: str,
        run_id: str,
        published: str,
        chash: str,
        sh: int,
        raw_sha256: str,
        wire_byline: bool = False,
        wire_agency: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT OR REPLACE INTO docs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                url,
                doc_id,
                source_id,
                run_id,
                published,
                chash,
                to_signed(sh),
                raw_sha256,
                1 if wire_byline else 0,
                wire_agency,
                now,
            ),
        )
        self.db.executemany(
            "INSERT INTO sim_bands VALUES (?,?,?)",
            [(i, v, doc_id) for i, v in enumerate(bands(sh))],
        )
        self.db.execute("DELETE FROM failures WHERE url=?", (url,))

    def add_failure(self, url: str, source_id: str, reason: str) -> None:
        """Add failure. Non-transient errors (short, no_date, out_of_window, 4xx) are marked non-retryable."""
        now = datetime.now(timezone.utc).isoformat()
        retryable = 1 if reason.startswith(("fetch_error", "timeout", "http_5")) else 0
        self.db.execute(
            """INSERT INTO failures VALUES (?,?,?,?,1,?)
               ON CONFLICT(url) DO UPDATE SET reason=excluded.reason,
               retryable=excluded.retryable, attempts=attempts+1, last_try=excluded.last_try""",
            (url, source_id, reason, retryable, now),
        )

    def failures(self, source_id: Optional[str] = None) -> List[dict]:
        """Return all failure records."""
        if source_id:
            cur = self.db.execute(
                "SELECT url, source_id, reason, retryable, attempts, last_try FROM failures WHERE source_id=?",
                (source_id,),
            )
        else:
            cur = self.db.execute(
                "SELECT url, source_id, reason, retryable, attempts, last_try FROM failures"
            )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def retryable_failures(self, source_id: str, max_attempts: int = 3) -> List[str]:
        """Return only failures with retryable network/server errors."""
        return [
            r[0] for r in self.db.execute(
                "SELECT url FROM failures WHERE source_id=? AND retryable=1 AND attempts < ?",
                (source_id, max_attempts),
            )
        ]

    def commit(self) -> None:
        self.db.commit()


class JsonlWriter:
    def __init__(self, data_dir: Path, source_id: str, run_id: str, until: datetime):
        d = Path(data_dir) / "raw" / "collected" / source_id / quarter_of(until)
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / f"{run_id}.jsonl.gz"
        self.n = 0

    @contextmanager
    def open(self):
        with gzip.open(self.path, "at", encoding="utf-8") as fh:
            def write(rec: dict) -> None:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                self.n += 1
            yield write

