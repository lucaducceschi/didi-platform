"""
Tests for CollectedHarmonizer and bilingual twin linking.
All tests run offline on synthetic fixtures with no network access.
"""
from datetime import datetime, timezone
from src.harmonizers.collected import CollectedHarmonizer, link_bilingual_twins
from src.sources import SOURCE_LABELS, SOURCE_REGISTRY


def test_harmonize_provinz_press_record():
    harmonizer = CollectedHarmonizer()
    rec = {
        "url": "https://news.provincia.bz.it/it/news/politica-di-coesione-ue",
        "title": "Politica di coesione UE",
        "text": "A Bruxelles vertice importante sulle regioni europee e fondi strutturali.",
        "published": "2026-03-04T16:49:00Z",
        "source_id": "provinz_press",
        "source_language": "it",
        "authors": ["USP"],
        "section": "Politica",
        "keywords": ["Europa", "Fondi"],
        "codename": "brussel_bruxelles_usp",
        "raw_kontent_id": "item_12345",
    }
    art = harmonizer.harmonize_record(rec)
    assert art is not None
    assert art.source == "provinz_news"
    assert art.source_type == "official_press"
    assert art.language == "it"
    assert art.author == "USP"
    assert art.id.startswith("provinz_it_20260304_")
    assert art.metadata["codename"] == "brussel_bruxelles_usp"
    assert art.word_count == 10


def test_existing_article_url_is_preserved_and_skipped():
    # Simulate an article already present in DIDI
    existing_url = "salto.bz/article/24042025/acchiappa-la-talpa"
    harmonizer = CollectedHarmonizer(existing_urls={existing_url})

    rec = {
        "url": "https://salto.bz/it/article/24042025/acchiappa-la-talpa",
        "title": "Acchiappa la talpa modificata",
        "text": "Nuovo testo differente che non deve sovrascrivere l'articolo esistente.",
        "published": "2025-04-24T12:00:00Z",
        "source_id": "salto_it",
    }
    art = harmonizer.harmonize_record(rec)
    assert art is None, "Existing article must not be overwritten or re-ingested"


def test_link_bilingual_twins():
    harmonizer = CollectedHarmonizer()
    rec_it = {
        "url": "https://news.provincia.bz.it/it/news/vertice-bruxelles",
        "title": "Vertice a Bruxelles",
        "text": "La delegazione altoatesina è giunta a Bruxelles per incontrare i commissari europei.",
        "published": "2026-03-04T12:00:00Z",
        "source_id": "provinz_press",
        "source_language": "it",
        "codename": "bruxelles_summit_2026",
    }
    rec_de = {
        "url": "https://news.provinz.bz.it/de/news/eu-gipfel-in-brussel",
        "title": "EU-Gipfel in Brüssel",
        "text": "Die Südtiroler Delegation traf sich in Brüssel mit den Vertretern der Regionen.",
        "published": "2026-03-04T12:00:00Z",
        "source_id": "provinz_press",
        "source_language": "de",
        "codename": "bruxelles_summit_2026",
    }
    art_it = harmonizer.harmonize_record(rec_it)
    art_de = harmonizer.harmonize_record(rec_de)
    assert art_it and art_de

    link_bilingual_twins([art_it, art_de])

    assert art_it.metadata.get("twin_article_id") == art_de.id
    assert art_it.metadata.get("twin_url") == art_de.url
    assert art_de.metadata.get("twin_article_id") == art_it.id
    assert art_de.metadata.get("twin_url") == art_it.url


def test_sources_registry_has_all_sources():
    expected_sources = {"tageszeitung", "salto", "provinz_news", "rai_bolzano", "la_usc", "trail"}
    assert expected_sources.issubset(set(SOURCE_REGISTRY.keys()))
    for s_id in expected_sources:
        assert s_id in SOURCE_LABELS
        assert len(SOURCE_LABELS[s_id]) > 0

