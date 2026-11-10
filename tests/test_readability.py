import pytest

from src.nlp.readability import (
    ReadabilityAnalyzer,
    analyze_readability,
    count_syllables_de,
    count_syllables_it,
)


def test_syllable_counter_german():
    assert count_syllables_de("Haus") == 1
    assert count_syllables_de("Häuser") == 2
    assert count_syllables_de("Autonomie") == 4  # Au - to - no - mie
    assert count_syllables_de("Sonderautonomiestatut") >= 7
    assert count_syllables_de("") == 0


def test_syllable_counter_italian():
    assert count_syllables_it("pane") == 2
    assert count_syllables_it("casa") == 2
    assert count_syllables_it("straordinario") >= 4
    assert count_syllables_it("autonomia") >= 4
    assert count_syllables_it("") == 0


def test_italian_readability_gulpease():
    # Simple Italian text
    simple_text = (
        "Il gatto mangia il pesce. La casa è bella e grande. "
        "Oggi c'è il sole in città e i bambini giocano nel parco."
    )
    res = analyze_readability(simple_text, language="it")
    assert res.primary_metric == "Gulpease"
    # Simple text should have high Gulpease score (>= 60)
    assert res.score >= 60.0
    assert "school" in res.grade_level.lower()
    assert res.lix > 0
    assert res.reading_ease > 0
    assert res.word_count > 10
    assert "gulpease" in res.components
    assert "flesch_vacca" in res.components

    # Complex Italian administrative legal text
    complex_text = (
        "In conformità con le disposizioni legislative concernenti l'amministrazione "
        "delle competenze regionali e l'attuazione delle prescrizioni giurisprudenziali, "
        "si dispone l'immediata sospensione dei provvedimenti amministrativi precedentemente adottati."
    )
    res_complex = analyze_readability(complex_text, language="it")
    assert res_complex.score < res.score  # Complex text has lower Gulpease score


def test_german_readability_wstf():
    # Standard German journalistic text
    german_text = (
        "Der Südtiroler Landtag hat heute über den neuen Haushalt debattiert. "
        "Die Abgeordneten sprachen über Bildung, Gesundheit und den Ausbau der Infrastruktur. "
        "Der Landeshauptmann betonte die Bedeutung stabiler Finanzen für das Land."
    )
    res = analyze_readability(german_text, language="de")
    assert res.primary_metric == "Wiener Sachtextformel"
    # WSTF should be within realistic grade levels 4-15
    assert 4.0 <= res.score <= 15.0
    assert res.lix > 0
    assert res.reading_ease > 0
    assert res.word_count > 10
    assert "wstf" in res.components
    assert "flesch_amstad" in res.components


def test_short_and_empty_text():
    empty_res = analyze_readability("", language="de")
    assert empty_res.score == 0.0
    assert empty_res.grade_level == "Insufficient text"

    short_res = analyze_readability("Hallo.", language="it")
    assert short_res.score == 0.0
    assert short_res.grade_level == "Insufficient text"

