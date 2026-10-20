"""
SQLite Storage Engine with Full-Text Search (FTS5) & NLP Metrics for the DIDI Platform.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..models.schema import DIDIArticle
from ..nlp.lexical import LexicalAnalyzer
from ..nlp.emotions import NRCEmotionAnalyzer

logger = logging.getLogger("DIDICorpusDB")


class DIDICorpusDB:
    """Manages the local SQLite corpus with FTS5 full-text search index and quantitative NLP metrics."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            # Main articles table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    language TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    publish_date TEXT NOT NULL,
                    author TEXT DEFAULT 'Redaktion',
                    category TEXT,
                    breadcrumbs_json TEXT,
                    full_text TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Migration: Ensure author column exists
            cur.execute("PRAGMA table_info(articles)")
            columns = [row["name"] for row in cur.fetchall()]
            if "author" not in columns:
                cur.execute("ALTER TABLE articles ADD COLUMN author TEXT DEFAULT 'Redaktion'")

            # Quantitative NLP metrics table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS article_nlp_metrics (
                    article_id TEXT PRIMARY KEY,
                    word_count INTEGER,
                    vocab_size INTEGER,
                    sentence_count INTEGER,
                    mean_sentence_length REAL,
                    ttr REAL,
                    root_ttr REAL,
                    log_ttr REAL,
                    hapax_count INTEGER,
                    hapax_ratio REAL,
                    net_sentiment REAL,
                    positive_density REAL,
                    negative_density REAL,
                    anger_density REAL,
                    anticipation_density REAL,
                    disgust_density REAL,
                    fear_density REAL,
                    joy_density REAL,
                    sadness_density REAL,
                    surprise_density REAL,
                    trust_density REAL,
                    emotional_density REAL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
                )
            """)

            # Indices on core filtering dimensions
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_language ON articles(language)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(publish_date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_nlp_sentiment ON article_nlp_metrics(net_sentiment)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_nlp_ttr ON article_nlp_metrics(ttr)")

            # Full-Text Search (FTS5) Virtual Table
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    id UNINDEXED,
                    title,
                    full_text,
                    content='articles',
                    content_rowid='rowid'
                )
            """)

            # Triggers to keep FTS5 synchronized with main table
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
                    INSERT INTO articles_fts(rowid, id, title, full_text)
                    VALUES (new.rowid, new.id, new.title, new.full_text);
                END;
            """)
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
                    INSERT INTO articles_fts(articles_fts, rowid, id, title, full_text)
                    VALUES ('delete', old.rowid, old.id, old.title, old.full_text);
                END;
            """)
            conn.commit()

    def insert_article(self, article: DIDIArticle) -> bool:
        """Insert or replace an article in the database."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO articles (
                    id, source, language, url, title, publish_date, author, category,
                    breadcrumbs_json, full_text, word_count, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.id,
                article.source,
                article.language,
                article.url,
                article.title,
                article.publish_date.isoformat(),
                getattr(article, "author", "Redaktion"),
                article.category,
                json.dumps(article.breadcrumbs),
                article.full_text,
                article.word_count,
                json.dumps(article.metadata),
                now
            ))
            cur.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
            conn.commit()
            return True

    def insert_batch(self, articles: List[DIDIArticle]) -> int:
        """Insert a batch of articles inside a single transaction."""
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        with self._get_connection() as conn:
            cur = conn.cursor()
            for art in articles:
                try:
                    cur.execute("""
                        INSERT OR REPLACE INTO articles (
                            id, source, language, url, title, publish_date, author, category,
                            breadcrumbs_json, full_text, word_count, metadata_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        art.id,
                        art.source,
                        art.language,
                        art.url,
                        art.title,
                        art.publish_date.isoformat(),
                        getattr(art, "author", "Redaktion"),
                        art.category,
                        json.dumps(art.breadcrumbs),
                        art.full_text,
                        art.word_count,
                        json.dumps(art.metadata),
                        now
                    ))
                    inserted += 1
                except Exception as e:
                    logger.error(f"Error inserting article {getattr(art, 'id', 'unknown')}: {e}")
            cur.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
            conn.commit()
        return inserted

    def enrich_nlp_metrics(self, limit: Optional[int] = None) -> int:
        """Compute and store quantitative lexical and emotional metrics for unindexed articles."""
        lex_analyzer = LexicalAnalyzer()
        emo_analyzer = NRCEmotionAnalyzer()

        with self._get_connection() as conn:
            cur = conn.cursor()
            query = """
                SELECT a.id, a.language, a.full_text
                FROM articles a
                LEFT JOIN article_nlp_metrics m ON a.id = m.article_id
                WHERE m.article_id IS NULL
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            cur.execute(query)
            pending = cur.fetchall()

            if not pending:
                return 0

            now = datetime.now(timezone.utc).isoformat()
            processed = 0
            for row in pending:
                art_id, lang, text = row["id"], row["language"], row["full_text"]
                lex = lex_analyzer.analyze(text)
                emo = emo_analyzer.analyze(text, lang)

                cur.execute("""
                    INSERT OR REPLACE INTO article_nlp_metrics (
                        article_id, word_count, vocab_size, sentence_count, mean_sentence_length,
                        ttr, root_ttr, log_ttr, hapax_count, hapax_ratio,
                        net_sentiment, positive_density, negative_density,
                        anger_density, anticipation_density, disgust_density,
                        fear_density, joy_density, sadness_density, surprise_density,
                        trust_density, emotional_density, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    art_id,
                    lex["word_count"],
                    lex["vocab_size"],
                    lex["sentence_count"],
                    lex["mean_sentence_length"],
                    lex["ttr"],
                    lex["root_ttr"],
                    lex["log_ttr"],
                    lex["hapax_count"],
                    lex["hapax_ratio"],
                    emo["net_sentiment"],
                    emo["positive_density"],
                    emo["negative_density"],
                    emo["anger_density"],
                    emo["anticipation_density"],
                    emo["disgust_density"],
                    emo["fear_density"],
                    emo["joy_density"],
                    emo["sadness_density"],
                    emo["surprise_density"],
                    emo["trust_density"],
                    emo["emotional_density"],
                    now
                ))
                processed += 1
            conn.commit()
            return processed

    def search_articles(self, query: str, limit: int = 20, source: Optional[str] = None, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run full-text search with optional filters."""
        sql = """
            SELECT a.id, a.source, a.language, a.url, a.title, a.publish_date, a.author, a.category, a.word_count,
                   m.net_sentiment, m.ttr, m.mean_sentence_length,
                   snippet(articles_fts, 1, '<b>', '</b>', '...', 25) as snippet
            FROM articles_fts f
            JOIN articles a ON a.id = f.id
            LEFT JOIN article_nlp_metrics m ON m.article_id = a.id
            WHERE articles_fts MATCH ?
        """
        params = [query]
        if source:
            sql += " AND a.source = ?"
            params.append(source)
        if language:
            sql += " AND a.language = ?"
            params.append(language)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def export_to_jsonl(self, output_path: Path) -> int:
        """Export full database to JSONL format."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with self._get_connection() as conn, open(output_path, "w", encoding="utf-8") as f:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.*, m.net_sentiment, m.ttr, m.root_ttr, m.anger_density, m.joy_density, m.trust_density
                FROM articles a
                LEFT JOIN article_nlp_metrics m ON a.id = m.article_id
            """)
            for row in cur.fetchall():
                d = dict(row)
                if d.get("breadcrumbs_json"):
                    d["breadcrumbs"] = json.loads(d.pop("breadcrumbs_json"))
                if d.get("metadata_json"):
                    d["metadata"] = json.loads(d.pop("metadata_json"))
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                count += 1
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Return corpus statistics grouped by source and language."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) as total_articles, sum(word_count) as total_words FROM articles")
            totals = cur.fetchone()

            cur.execute("SELECT source, count(*) as count, sum(word_count) as words FROM articles GROUP BY source")
            sources = {row["source"]: {"articles": row["count"], "words": row["words"]} for row in cur.fetchall()}

            cur.execute("SELECT language, count(*) as count FROM articles GROUP BY language")
            languages = {row["language"]: row["count"] for row in cur.fetchall()}

            cur.execute("SELECT min(publish_date) as earliest, max(publish_date) as latest FROM articles")
            date_range = cur.fetchone()

            cur.execute("SELECT count(*) as count FROM article_nlp_metrics")
            nlp_count = cur.fetchone()["count"]

            return {
                "total_articles": totals["total_articles"],
                "total_words": totals["total_words"] or 0,
                "sources": sources,
                "languages": languages,
                "nlp_profiled_articles": nlp_count,
                "earliest_date": date_range["earliest"] if date_range else "",
                "latest_date": date_range["latest"] if date_range else "",
            }
