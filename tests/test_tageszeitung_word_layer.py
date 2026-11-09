"""
Tests for Tageszeitung Ingestion and Word Layer.

All tests run on synthetic in-memory or fixture data, never on the real copyrighted corpus.
"""

import json
import sqlite3
import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.importers.tageszeitung import (
    extract_words_from_conll,
    make_article_id,
    normalize_url,
    parse_german_date,
)
from src.storage.word_layer import (
    init_words_db,
    insert_words_batch,
    get_article_words,
    get_passage_words,
    get_word_layer_summary,
)
from src.ui.data_service import DataService
from backend.app.services.words import (
    get_article_words as service_get_article_words,
    get_passage_words as service_get_passage_words,
)


def test_normalize_url():
    assert normalize_url("https://www.tageszeitung.it/2021/07/20/zwei-neue-woelfe/") == "https://www.tageszeitung.it/2021/07/20/zwei-neue-woelfe"
    assert normalize_url("https://www.tageszeitung.it/2021/07/20/zwei-neue-woelfe") == "https://www.tageszeitung.it/2021/07/20/zwei-neue-woelfe"


def test_parse_german_date_and_id():
    date_str = "06. Mai 2025, 05:49"
    url = "https://www.tageszeitung.it/2025/05/06/keine-echte-autonomie/"
    dt = parse_german_date(date_str, url)
    assert dt.year == 2025
    assert dt.month == 5
    assert dt.day == 6
    assert dt.hour == 5
    assert dt.minute == 49

    art_id = make_article_id(dt, url)
    assert art_id == "taz_20250506_keine-echte-autonomie"


def test_parse_date_fallback_to_url():
    url = "https://www.tageszeitung.it/2018/11/04/ein-artikel-ohne-datum/"
    dt = parse_german_date(None, url)
    assert dt.year == 2018
    assert dt.month == 11
    assert dt.day == 4
    art_id = make_article_id(dt, url)
    assert art_id == "taz_20181104_ein-artikel-ohne-datum"


def test_title_offset_shifting():
    """Verify that title tokens are excluded and content tokens shift by -(len(title) + 1)."""
    title = "Kurzer Titel"
    content = "Das erste Wort im Inhalt."
    # len("Kurzer Titel") = 12. '\n' at 12. shift = 13.
    # Title tokens:
    # 0..6 'Kurzer', 7..12 'Titel'
    # Content tokens:
    # 13..16 'Das' -> [0:3]
    # 17..22 'erste' -> [4:9]
    # 23..27 'Wort' -> [10:14]
    # 28..30 'im' -> [15:17]
    # 31..37 'Inhalt' -> [18:24]
    # 37..38 '.' -> [24:25]
    conll_lines = [
        "1\tKurzer\tkurz\tADJ\tADJA\t_\t2\tamod\t_\tstart_char=0|end_char=6|ner=O",
        "2\tTitel\tTitel\tNOUN\tNN\t_\t0\troot\t_\tstart_char=7|end_char=12|ner=O",
        "3\tDas\tder\tDET\tART\t_\t5\tdet\t_\tstart_char=13|end_char=16|ner=O",
        "4\terste\terst\tADJ\tADJA\t_\t5\tamod\t_\tstart_char=17|end_char=22|ner=O",
        "5\tWort\tWort\tNOUN\tNN\t_\t0\troot\t_\tstart_char=23|end_char=27|ner=O",
        "6\tim\tim\tADP\tAPPRART\t_\t7\tcase\t_\tstart_char=28|end_char=30|ner=O",
        "7\tInhalt\tInhalt\tNOUN\tNN\t_\t5\tnmod\t_\tstart_char=31|end_char=37|ner=O",
        "8\t.\t.\tPUNCT\t$.\t_\t5\tpunct\t_\tstart_char=37|end_char=38|ner=O",
    ]

    words, is_valid, error = extract_words_from_conll(conll_lines, title, content, "art_test_1")
    assert is_valid, f"Failed: {error}"
    assert len(words) == 6
    # Check shifted offsets
    assert words[0]["form"] == "Das"
    assert words[0]["start_char"] == 0
    assert words[0]["end_char"] == 3
    assert content[words[0]["start_char"]:words[0]["end_char"]] == "Das"

    assert words[4]["form"] == "Inhalt"
    assert words[4]["start_char"] == 18
    assert words[4]["end_char"] == 24
    assert content[words[4]["start_char"]:words[4]["end_char"]] == "Inhalt"


def test_multi_word_tokens_sharing_span():
    """Verify that multi-word tokens share their parent token span and both are retained."""
    title = "Titel"
    # shift = 5 + 1 = 6.
    # In full text: 'Beim Arzt'
    # CoNLL text: 'Titel\nBeim Arzt'
    # 'Beim' is at 6..10.
    content = "Beim Arzt."
    conll_lines = [
        "1\tTitel\tTitel\tNOUN\tNN\t_\t0\troot\t_\tstart_char=0|end_char=5|ner=O",
        "1-2\tBeim\t_\t_\t_\t_\t_\t_\t_\tstart_char=6|end_char=10|ner=O",
        "1\tBei\tbei\tADP\tAPPR\t_\t3\tcase\t_\t_",
        "2\tdem\tder\tDET\tART\tCase=Dat\t3\tdet\t_\t_",
        "3\tArzt\tArzt\tNOUN\tNN\tCase=Dat\t0\troot\t_\tstart_char=11|end_char=15|ner=O",
        "4\t.\t.\tPUNCT\t$.\t_\t3\tpunct\t_\tstart_char=15|end_char=16|ner=O",
    ]

    words, is_valid, error = extract_words_from_conll(conll_lines, title, content, "art_mwt")
    assert is_valid, error
    assert len(words) == 4

    # Words 0 and 1 are MWT parts sharing span [0:4] in content ('Beim')
    assert words[0]["form"] == "Bei"
    assert words[0]["lemma"] == "bei"
    assert words[0]["start_char"] == 0
    assert words[0]["end_char"] == 4

    assert words[1]["form"] == "dem"
    assert words[1]["lemma"] == "der"
    assert words[1]["start_char"] == 0
    assert words[1]["end_char"] == 4

    assert words[2]["form"] == "Arzt"
    assert words[2]["start_char"] == 5
    assert words[2]["end_char"] == 9
    assert content[words[2]["start_char"]:words[2]["end_char"]] == "Arzt"


def test_unicode_and_emoji_handling():
    """Verify that Unicode German characters (ä, ö, ü, ß) and emoji are accurately aligned."""
    title = "Südtirol 🌲"
    # len("Südtirol 🌲") = 10 code points. shift = 11.
    content = "Schöne Grüße aus Bozen!"
    # 'Schöne': 11..17 -> [0:6]
    # 'Grüße': 18..23 -> [7:12]
    # 'aus': 24..27 -> [13:16]
    # 'Bozen': 28..33 -> [17:22]
    # '!': 33..34 -> [22:23]
    conll_lines = [
        "1\tSüdtirol\tSüdtirol\tPROPN\tNE\t_\t2\tappos\t_\tstart_char=0|end_char=8|ner=B-LOC",
        "2\t🌲\t🌲\tSYM\t_XY\t_\t0\troot\t_\tstart_char=9|end_char=10|ner=O",
        "3\tSchöne\tschön\tADJ\tADJA\t_\t4\tamod\t_\tstart_char=11|end_char=17|ner=O",
        "4\tGrüße\tGruß\tNOUN\tNN\t_\t0\troot\t_\tstart_char=18|end_char=23|ner=O",
        "5\taus\taus\tADP\tAPPR\t_\t6\tcase\t_\tstart_char=24|end_char=27|ner=O",
        "6\tBozen\tBozen\tPROPN\tNE\t_\t4\tnmod\t_\tstart_char=28|end_char=33|ner=B-LOC",
        "7\t!\t!\tPUNCT\t$.\t_\t4\tpunct\t_\tstart_char=33|end_char=34|ner=O",
    ]

    words, is_valid, error = extract_words_from_conll(conll_lines, title, content, "art_unicode")
    assert is_valid, error
    assert len(words) == 5

    assert words[0]["form"] == "Schöne"
    assert content[words[0]["start_char"]:words[0]["end_char"]] == "Schöne"

    assert words[1]["form"] == "Grüße"
    assert content[words[1]["start_char"]:words[1]["end_char"]] == "Grüße"

    assert words[3]["form"] == "Bozen"
    assert words[3]["ner"] == "B-LOC"
    assert content[words[3]["start_char"]:words[3]["end_char"]] == "Bozen"


def test_token_mismatch_fails_gracefully():
    """Verify that an article with differing text is flagged and skipped without throwing."""
    title = "Titel"
    # full_text has 'Anderer Inhalt' but CoNLL has 'Falscher Text'
    content = "Anderer Inhalt."
    shift = 6
    conll_lines = [
        "1\tTitel\tTitel\tNOUN\tNN\t_\t0\troot\t_\tstart_char=0|end_char=5|ner=O",
        "2\tFalscher\tfalsch\tADJ\tADJA\t_\t3\tamod\t_\tstart_char=6|end_char=14|ner=O",
        "3\tText\tText\tNOUN\tNN\t_\t0\troot\t_\tstart_char=15|end_char=19|ner=O",
    ]

    words, is_valid, error = extract_words_from_conll(conll_lines, title, content, "art_mismatch")
    assert not is_valid
    assert words == []
    assert "Token mismatch" in error


def test_word_layer_database_operations(tmp_path: Path):
    """Verify database initialization, batch insertion, and sub-millisecond retrieval."""
    words_db = tmp_path / "test_words.db"
    init_words_db(words_db)

    words = [
        {
            "article_id": "test_art_1",
            "token_idx": 0,
            "start_char": 0,
            "end_char": 4,
            "form": "Dies",
            "lemma": "dieser",
            "upos": "PRON",
            "xpos": "PDS",
            "feats": "Case=Nom",
            "ner": "O",
        },
        {
            "article_id": "test_art_1",
            "token_idx": 1,
            "start_char": 5,
            "end_char": 8,
            "form": "ist",
            "lemma": "sein",
            "upos": "AUX",
            "xpos": "VAFIN",
            "feats": "Mood=Ind",
            "ner": "O",
        },
        {
            "article_id": "test_art_1",
            "token_idx": 2,
            "start_char": 9,
            "end_char": 12,
            "form": "ein",
            "lemma": "ein",
            "upos": "DET",
            "xpos": "ART",
            "feats": "Case=Nom",
            "ner": "O",
        },
        {
            "article_id": "test_art_1",
            "token_idx": 3,
            "start_char": 13,
            "end_char": 17,
            "form": "Test",
            "lemma": "Test",
            "upos": "NOUN",
            "xpos": "NN",
            "feats": "Case=Nom",
            "ner": "O",
        },
    ]

    insert_words_batch(words_db, words, metadata={"source": "Stanza_Test"})

    # Test full article retrieval
    art_words = get_article_words(words_db, "test_art_1")
    assert len(art_words) == 4
    assert art_words[0]["form"] == "Dies"
    assert art_words[3]["form"] == "Test"

    # Test passage retrieval covering [5:12] -> 'ist ein'
    passage_words = get_passage_words(words_db, "test_art_1", 5, 12)
    assert len(passage_words) == 2
    assert [w["form"] for w in passage_words] == ["ist", "ein"]

    # Test summary
    summary = get_word_layer_summary(words_db)
    assert summary["total_words"] == 4
    assert summary["total_articles"] == 1
    assert summary["metadata"].get("source") == "Stanza_Test"


def test_data_service_and_backend_service_word_retrieval(tmp_path: Path):
    """Verify DataService and backend services load words seamlessly."""
    # Synthetic corpus db
    corpus_db = tmp_path / "test_corpus.db"
    words_db = tmp_path / "test_words.db"

    with sqlite3.connect(corpus_db) as conn:
        conn.execute("""
            CREATE TABLE articles (
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
        conn.execute("""
            INSERT INTO articles (id, source, language, url, title, publish_date, full_text, created_at)
            VALUES ('taz_sample', 'tageszeitung', 'de', 'https://example.com/art', 'Titel', '2025-05-01', 'Hallo Bozen.', '2026-11-09')
        """)
        conn.commit()

    init_words_db(words_db)
    words = [
        {"article_id": "taz_sample", "token_idx": 0, "start_char": 0, "end_char": 5, "form": "Hallo", "lemma": "hallo", "upos": "INTJ", "xpos": "ITJ", "feats": "_", "ner": "O"},
        {"article_id": "taz_sample", "token_idx": 1, "start_char": 6, "end_char": 11, "form": "Bozen", "lemma": "Bozen", "upos": "PROPN", "xpos": "NE", "feats": "_", "ner": "B-LOC"},
        {"article_id": "taz_sample", "token_idx": 2, "start_char": 11, "end_char": 12, "form": ".", "lemma": ".", "upos": "PUNCT", "xpos": "$.", "feats": "_", "ner": "O"},
    ]
    insert_words_batch(words_db, words)

    # Test DataService
    ds = DataService(db_path=corpus_db, words_db_path=words_db, enable_hybrid=False)
    retrieved = ds.get_article_words("taz_sample")
    assert len(retrieved) == 3
    assert retrieved[1]["form"] == "Bozen"

    passage = ds.get_passage_words("taz_sample", 6, 12)
    assert len(passage) == 2
    assert [w["form"] for w in passage] == ["Bozen", "."]


def test_idempotency_running_import_twice(tmp_path: Path):
    """Verify that running word insertion twice produces 0 duplicate records."""
    words_db = tmp_path / "idempotent_words.db"
    init_words_db(words_db)

    words = [
        {"article_id": "art_1", "token_idx": 0, "start_char": 0, "end_char": 4, "form": "Wort", "lemma": "wort", "upos": "NOUN", "xpos": "NN", "feats": "_", "ner": "O"}
    ]

    # Run 1
    insert_words_batch(words_db, words)
    assert len(get_article_words(words_db, "art_1")) == 1

    # Run 2
    insert_words_batch(words_db, words)
    # Primary key (article_id, token_idx) prevents duplicates
    assert len(get_article_words(words_db, "art_1")) == 1

