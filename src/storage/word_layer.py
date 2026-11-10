"""
Word Layer Storage Engine for the DIDI Platform.

Manages SQLite storage for token-level annotations:
character offsets [start_char:end_char] in full_text, lemmas,
UPOS, XPOS, morphological features, and NER tags.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_WORDS_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "processed"
    / "didi_words.db"
)


def init_words_db(db_path: Optional[Path] = None) -> Path:
    """Initialize the word layer SQLite database schema with indexes."""
    path = Path(db_path) if db_path else DEFAULT_WORDS_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_words (
                article_id TEXT NOT NULL,
                token_idx INTEGER NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                form TEXT NOT NULL,
                lemma TEXT NOT NULL,
                upos TEXT NOT NULL,
                xpos TEXT,
                feats TEXT,
                ner TEXT,
                PRIMARY KEY (article_id, token_idx)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_words_start 
            ON article_words (article_id, start_char)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_quotes (
                article_id TEXT NOT NULL,
                quote_idx INTEGER NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                quote_text TEXT NOT NULL,
                quote_type TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                PRIMARY KEY (article_id, quote_idx)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_quotes_start 
            ON article_quotes (article_id, start_char)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS word_layer_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()
    return path


def insert_words_batch(
    db_path: Path,
    words: List[Dict[str, Any]],
    metadata: Optional[Dict[str, str]] = None
) -> int:
    """
    Insert a batch of word records into the word layer database.
    Each word dict must have:
    article_id, token_idx, start_char, end_char, form, lemma, upos, xpos, feats, ner
    """
    if not words and not metadata:
        return 0

    tuples = [
        (
            w["article_id"],
            w["token_idx"],
            w["start_char"],
            w["end_char"],
            w["form"],
            w["lemma"],
            w["upos"],
            w.get("xpos"),
            w.get("feats"),
            w.get("ner", "O"),
        )
        for w in words
    ]

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        if tuples:
            conn.executemany(
                """
                INSERT OR REPLACE INTO article_words 
                (article_id, token_idx, start_char, end_char, form, lemma, upos, xpos, feats, ner)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuples,
            )
        if metadata:
            meta_tuples = [(k, str(v)) for k, v in metadata.items()]
            conn.executemany(
                "INSERT OR REPLACE INTO word_layer_metadata (key, value) VALUES (?, ?)",
                meta_tuples,
            )
        conn.commit()

    return len(tuples)


def _get_read_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.execute("PRAGMA mmap_size = 268435456")
    conn.row_factory = sqlite3.Row
    return conn


def get_article_words(
    db_path: Path, article_id: str
) -> List[Dict[str, Any]]:
    """Retrieve all word tokens for an article, ordered by token index."""
    if not db_path.exists():
        return []

    with _get_read_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT article_id, token_idx, start_char, end_char, form, lemma, upos, xpos, feats, ner
            FROM article_words
            WHERE article_id = ?
            ORDER BY token_idx ASC
            """,
            (article_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_passage_words(
    db_path: Path, article_id: str, start_char: int, end_char: int
) -> List[Dict[str, Any]]:
    """
    Retrieve word tokens covering or intersecting a text span [start_char:end_char].
    Orders by token_idx ASC.
    """
    if not db_path.exists():
        return []

    with _get_read_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT article_id, token_idx, start_char, end_char, form, lemma, upos, xpos, feats, ner
            FROM article_words
            WHERE article_id = ? 
              AND end_char > ? 
              AND start_char < ?
            ORDER BY token_idx ASC
            """,
            (article_id, start_char, end_char),
        )
        return [dict(row) for row in cur.fetchall()]


def get_word_layer_summary(db_path: Path) -> Dict[str, Any]:
    """Retrieve statistics and metadata from the word layer database."""
    if not db_path.exists():
        return {"total_words": 0, "total_articles": 0, "metadata": {}}

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT count(*), count(distinct article_id) FROM article_words")
        total_words, total_articles = cur.fetchone()

        cur.execute("SELECT key, value FROM word_layer_metadata")
        meta = {row["key"]: row["value"] for row in cur.fetchall()}

        return {
            "total_words": total_words,
            "total_articles": total_articles,
            "metadata": meta,
        }


def insert_quotes_batch(
    db_path: Path,
    quotes: List[Dict[str, Any]],
) -> int:
    """
    Insert a batch of detected quote spans into article_quotes table.
    Each quote dict must have:
    article_id, quote_idx, start_char, end_char, quote_text, quote_type, rule_version
    """
    if not quotes:
        return 0

    tuples = [
        (
            q["article_id"],
            q["quote_idx"],
            q["start_char"],
            q["end_char"],
            q["quote_text"],
            q.get("quote_type", "direct_speech"),
            q.get("rule_version", "quote_rules_v1"),
        )
        for q in quotes
    ]

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executemany(
            """
            INSERT OR REPLACE INTO article_quotes 
            (article_id, quote_idx, start_char, end_char, quote_text, quote_type, rule_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            tuples,
        )
        conn.commit()

    return len(tuples)


def _has_quotes_table(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'article_quotes'"
    ).fetchone() is not None


def get_article_quotes(
    db_path: Path, article_id: str
) -> List[Dict[str, Any]]:
    """Retrieve all detected quotes for an article, ordered by start_char."""
    if not db_path.exists():
        return []

    with _get_read_connection(db_path) as conn:
        if not _has_quotes_table(conn):
            return []  # quotes not stored yet: callers detect them on the fly
        cur = conn.cursor()
        cur.execute(
            """
            SELECT article_id, quote_idx, start_char, end_char, quote_text, quote_type, rule_version
            FROM article_quotes
            WHERE article_id = ?
            ORDER BY start_char ASC
            """,
            (article_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_passage_quotes(
    db_path: Path, article_id: str, start_char: int, end_char: int
) -> List[Dict[str, Any]]:
    """Retrieve detected quote spans intersecting a character span [start_char:end_char]."""
    if not db_path.exists():
        return []

    with _get_read_connection(db_path) as conn:
        if not _has_quotes_table(conn):
            return []  # quotes not stored yet: callers detect them on the fly
        cur = conn.cursor()
        cur.execute(
            """
            SELECT article_id, quote_idx, start_char, end_char, quote_text, quote_type, rule_version
            FROM article_quotes
            WHERE article_id = ? 
              AND end_char > ? 
              AND start_char < ?
            ORDER BY start_char ASC
            """,
            (article_id, start_char, end_char),
        )
        return [dict(row) for row in cur.fetchall()]


