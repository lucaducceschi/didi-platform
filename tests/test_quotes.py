"""
Tests for Stage 5: Direct Quotes Detection and Measures Partition.

Covers:
- All quotation mark styles per language (German: „…“, »…«, "…", ‚…‘; Italian: «…», "…")
- Nested quotes (outer speech with inner quotation)
- Quotes running across paragraph boundaries
- Unbalanced quotation marks (unclosed openers, stray closers)
- Quotes in headlines (e.g. SVP: „Keine Koalition ohne Autonomiegarantie“)
- Scare quotes and short titles filtering (<= 2 words without verb)
- Additive measure split (inside_quotes + outside_quotes == total)
- Database persistence (article_quotes table in didi_words.db)
"""

import sqlite3
from pathlib import Path

import pytest
from src.nlp.quotes import (
    RULE_VERSION,
    QuoteSpan,
    detect_direct_quotes,
    split_tokens_by_quotes,
)
from src.storage.word_layer import (
    get_article_quotes,
    get_passage_quotes,
    init_words_db,
    insert_quotes_batch,
)
from backend.app.services.measures import score_tokens


def test_german_quotation_mark_styles():
    """Verify detection across all German quotation mark styles: „…“, »…«, \"…\", ‚…‘."""
    # 1. German low-high double „…“
    text_de_standard = 'Landeshauptmann Arno Kompatscher erklärte: „Wir werden die Autonomie mit allen Mitteln verteidigen.“'
    quotes = detect_direct_quotes(text_de_standard, language="de")
    assert len(quotes) == 1
    assert "Wir werden die Autonomie mit allen Mitteln verteidigen." in quotes[0].text
    assert quotes[0].start_char == text_de_standard.index("„")
    assert quotes[0].end_char == text_de_standard.index("“") + 1

    # 2. German inward chevrons »…«
    text_de_chevrons = 'Die Opposition kritisierte: »Dieser Haushaltsplan ist ein Schlag ins Gesicht aller Bürger.«'
    quotes = detect_direct_quotes(text_de_chevrons, language="de")
    assert len(quotes) == 1
    assert "Dieser Haushaltsplan ist ein Schlag" in quotes[0].text

    # 3. Straight double quotes "…"
    text_de_straight = 'Der Sprecher sagte: "Die Verhandlungen sind auf einem guten Weg."'
    quotes = detect_direct_quotes(text_de_straight, language="de")
    assert len(quotes) == 1
    assert "Die Verhandlungen sind auf einem guten Weg." in quotes[0].text

    # 4. German low-high single ‚…‘
    text_de_single = 'Er fügte hinzu: ‚Wir sind zu weiteren Gesprächen bereit.‘'
    quotes = detect_direct_quotes(text_de_single, language="de")
    assert len(quotes) == 1
    assert "Wir sind zu weiteren Gesprächen bereit." in quotes[0].text


def test_italian_quotation_mark_styles():
    """Verify detection across Italian quotation mark styles: «…» and \"…\"."""
    # 1. Italian caporali «…»
    text_it_caporali = 'Il presidente ha confermato: «La tutela della minoranza resta la priorità assoluta per il governo provinciale.»'
    quotes = detect_direct_quotes(text_it_caporali, language="it")
    assert len(quotes) == 1
    assert "La tutela della minoranza resta" in quotes[0].text

    # 2. Italian straight double quotes "…"
    text_it_straight = 'Il consigliere ha replicato: "Non permetteremo tagli alla sanità pubblica nelle valli."'
    quotes = detect_direct_quotes(text_it_straight, language="it")
    assert len(quotes) == 1
    assert "Non permetteremo tagli alla sanità" in quotes[0].text

    # 3. Curly “…” and low „…“, as used by Salto's Italian articles
    for text_it in (
        'L’assessore Alfreider: “L’inizio lavori? Con il completamento della circonvallazione di Bolzano”.',
        'Le maestre dovevano dire: „Ragazzi, dobbiamo andare via subito dal cinema adesso“ E poi basta.',
    ):
        quotes = detect_direct_quotes(text_it, language="it")
        assert len(quotes) == 1, text_it
        assert text_it[quotes[0].start_char] in "“„"


def test_nested_quotes():
    """Verify outer and inner quotes handling."""
    text_nested = 'Er betonte: „Die sogenannte ‚Reform‘ ist in Wahrheit ein Rückschritt für uns.“'
    quotes = detect_direct_quotes(text_nested, language="de")
    # Outer quote has verb 'ist' and multiple words
    speech_quotes = [q for q in quotes if q.quote_type == "direct_speech"]
    assert any("Die sogenannte" in q.text for q in speech_quotes)


def test_cross_paragraph_quotes():
    """Verify quotes that span across paragraph breaks (\\n\\n)."""
    text_multiline = (
        'Der Minister stellte klar:\n'
        '„Wir haben die Vereinbarung gemeinsam unterzeichnet.\n\n'
        'Nun müssen alle Beteiligten ihren Verpflichtungen nachkommen.“'
    )
    quotes = detect_direct_quotes(text_multiline, language="de")
    assert len(quotes) == 1
    assert "Nun müssen alle Beteiligten" in quotes[0].text
    assert "\n\n" in quotes[0].text


def test_unbalanced_quotation_marks():
    """Verify that unclosed or stray quotation marks are safely handled without swallowing text."""
    # Unclosed opening quote
    text_unclosed = 'Er begann mit: „Dieser Satz hat kein Ende.\nUnd hier geht der normale Artikel weiter.'
    quotes = detect_direct_quotes(text_unclosed, language="de")
    assert len(quotes) == 0  # Unclosed quote discarded

    # Stray closer without opener
    text_stray_closer = 'Hier ist ein normaler Satz ohne Opener.“ Danach geht es weiter.'
    quotes = detect_direct_quotes(text_stray_closer, language="de")
    assert len(quotes) == 0


def test_quotes_in_headlines():
    """Verify quotes in journalistic headlines without standard speech verbs."""
    headline_de = 'SVP: „Keine Koalition ohne Autonomiegarantie“'
    quotes = detect_direct_quotes(headline_de, language="de")
    assert len(quotes) == 1
    assert "Keine Koalition ohne Autonomiegarantie" in quotes[0].text

    headline_it = 'Kompatscher: «Maggiori risorse per la sanità locale»'
    quotes = detect_direct_quotes(headline_it, language="it")
    assert len(quotes) == 1
    assert "Maggiori risorse per la sanità locale" in quotes[0].text


def test_scare_quotes_filtered_out():
    """Verify scare quotes and single terms (<= 2 words without verb) are filtered out."""
    # Single word scare quote
    tokens_single = [
        {"form": "Er", "lemma": "er", "upos": "PRON", "start_char": 0, "end_char": 2},
        {"form": "sprach", "lemma": "sprechen", "upos": "VERB", "start_char": 3, "end_char": 9},
        {"form": "von", "lemma": "von", "upos": "ADP", "start_char": 10, "end_char": 13},
        {"form": "einer", "lemma": "ein", "upos": "DET", "start_char": 14, "end_char": 19},
        {"form": "„", "lemma": '"', "upos": "PUNCT", "start_char": 20, "end_char": 21},
        {"form": "Krise", "lemma": "Krise", "upos": "NOUN", "start_char": 21, "end_char": 26},
        {"form": "“", "lemma": '"', "upos": "PUNCT", "start_char": 26, "end_char": 27},
    ]
    text_scare = "Er sprach von einer „Krise“."
    quotes = detect_direct_quotes(text_scare, language="de", tokens=tokens_single)
    assert len(quotes) == 0

    # Two words without verb: "großer Skandal"
    tokens_two = [
        {"form": "„", "lemma": '"', "upos": "PUNCT", "start_char": 0, "end_char": 1},
        {"form": "großer", "lemma": "groß", "upos": "ADJ", "start_char": 1, "end_char": 7},
        {"form": "Skandal", "lemma": "Skandal", "upos": "NOUN", "start_char": 8, "end_char": 15},
        {"form": "“", "lemma": '"', "upos": "PUNCT", "start_char": 15, "end_char": 16},
    ]
    text_two = "„großer Skandal“"
    quotes_two = detect_direct_quotes(text_two, language="de", tokens=tokens_two)
    assert len(quotes_two) == 0

    # Short quote WITH a verb: "Wir siegen" (2 words, has verb) -> kept
    tokens_verb = [
        {"form": "„", "lemma": '"', "upos": "PUNCT", "start_char": 0, "end_char": 1},
        {"form": "Wir", "lemma": "wir", "upos": "PRON", "feats": "Person=1|Number=Plur", "start_char": 1, "end_char": 4},
        {"form": "siegen", "lemma": "siegen", "upos": "VERB", "feats": "Mood=Ind|Tense=Pres", "start_char": 5, "end_char": 11},
        {"form": "“", "lemma": '"', "upos": "PUNCT", "start_char": 11, "end_char": 12},
    ]
    text_verb = "„Wir siegen“"
    quotes_verb = detect_direct_quotes(text_verb, language="de", tokens=tokens_verb)
    assert len(quotes_verb) == 1


def test_measure_split_sums_back_to_total():
    """Verify that inside_quotes + outside_quotes measures strictly sum to total."""
    # Construct a synthetic document with 1 speech quote and outside narration
    # Outside text: "Der Sprecher sagte gestern in Bozen: " (start 0..37)
    # Inside quote: "„Wir schützen unser Land und unsere Rechte.“" (start 37..81)
    tokens = [
        # Outside tokens
        {"form": "Der", "lemma": "der", "upos": "DET", "start_char": 0, "end_char": 3},
        {"form": "Sprecher", "lemma": "Sprecher", "upos": "NOUN", "start_char": 4, "end_char": 12},
        {"form": "sagte", "lemma": "sagen", "upos": "VERB", "start_char": 13, "end_char": 18},
        {"form": "gestern", "lemma": "gestern", "upos": "ADV", "start_char": 19, "end_char": 26},
        {"form": "in", "lemma": "in", "upos": "ADP", "start_char": 27, "end_char": 29},
        {"form": "Bozen", "lemma": "Bozen", "upos": "PROPN", "start_char": 30, "end_char": 35},
        {"form": ":", "lemma": ":", "upos": "PUNCT", "start_char": 35, "end_char": 36},
        # Inside quote tokens
        {"form": "„", "lemma": '"', "upos": "PUNCT", "start_char": 37, "end_char": 38},
        {"form": "Wir", "lemma": "wir", "upos": "PRON", "feats": "Person=1|Number=Plur", "start_char": 38, "end_char": 41},
        {"form": "schützen", "lemma": "schützen", "upos": "VERB", "start_char": 42, "end_char": 50},
        {"form": "unser", "lemma": "unser", "upos": "DET", "feats": "Person=1|Number=Plur", "start_char": 51, "end_char": 56},
        {"form": "Land", "lemma": "Land", "upos": "NOUN", "start_char": 57, "end_char": 61},
        {"form": "und", "lemma": "und", "upos": "CCONJ", "start_char": 62, "end_char": 65},
        {"form": "unsere", "lemma": "unser", "upos": "DET", "feats": "Person=1|Number=Plur", "start_char": 66, "end_char": 72},
        {"form": "Rechte", "lemma": "Recht", "upos": "NOUN", "start_char": 73, "end_char": 79},
        {"form": ".", "lemma": ".", "upos": "PUNCT", "start_char": 79, "end_char": 80},
        {"form": "“", "lemma": '"', "upos": "PUNCT", "start_char": 80, "end_char": 81},
    ]

    quote_spans = [(37, 81)]

    scored = score_tokens(tokens, language="de", quote_spans=quote_spans)

    assert "inside_quotes" in scored
    assert "outside_quotes" in scored
    assert scored["quote_count"] == 1
    assert scored["quote_split_unvalidated"] is True

    inside = scored["inside_quotes"]
    outside = scored["outside_quotes"]

    # 1. Total word count sum
    assert inside["word_count"] + outside["word_count"] == scored["word_count"]
    assert scored["word_count"] == len(tokens)

    # 2. Ingroup pronouns: 'Wir', 'unser', 'unsere' are all INSIDE the quote
    assert inside["ingroup_pronouns"]["count"] == 3
    assert outside["ingroup_pronouns"]["count"] == 0
    assert inside["ingroup_pronouns"]["count"] + outside["ingroup_pronouns"]["count"] == scored["ingroup_pronouns"]["count"]

    # 3. Konjunktiv I counts
    assert inside["konjunktiv_i"]["count"] + outside["konjunktiv_i"]["count"] == scored["konjunktiv_i"]["count"]

    # 4. MFD breakdown sums
    for pole, count in scored["mfd_breakdown"].items():
        assert count == inside["mfd_breakdown"].get(pole, 0) + outside["mfd_breakdown"].get(pole, 0)


def test_quote_storage_sqlite(tmp_path: Path):
    """Verify database persistence in article_quotes table."""
    db_file = tmp_path / "test_words.db"
    init_words_db(db_file)

    sample_quotes = [
        {
            "article_id": "art_101",
            "quote_idx": 0,
            "start_char": 50,
            "end_char": 120,
            "quote_text": "„Wir werden nicht weichen.“",
            "quote_type": "direct_speech",
            "rule_version": RULE_VERSION,
        },
        {
            "article_id": "art_101",
            "quote_idx": 1,
            "start_char": 200,
            "end_char": 280,
            "quote_text": "„Die Gespräche waren konstruktiv.“",
            "quote_type": "direct_speech",
            "rule_version": RULE_VERSION,
        },
    ]

    inserted = insert_quotes_batch(db_file, sample_quotes)
    assert inserted == 2

    # Query article quotes
    fetched = get_article_quotes(db_file, "art_101")
    assert len(fetched) == 2
    assert fetched[0]["quote_text"] == "„Wir werden nicht weichen.“"
    assert fetched[0]["rule_version"] == RULE_VERSION

    # Query passage intersection: [40, 100] should match quote 0, but not quote 1
    passage_q = get_passage_quotes(db_file, "art_101", 40, 100)
    assert len(passage_q) == 1
    assert passage_q[0]["quote_idx"] == 0

    # Query passage outside both quotes
    empty_q = get_passage_quotes(db_file, "art_101", 130, 190)
    assert len(empty_q) == 0

