import pytest

from src.nlp.complexity import analyze_complexity
from src.nlp.concreteness import analyze_concreteness


def test_concreteness_german():
    # Concrete German text: bread, apples, house, mountain
    concrete_text = "Die Bauern backen frisches Brot im Haus am Berg und bringen Äpfel zur Schule."
    res_c = analyze_concreteness(concrete_text, language="de")
    assert res_c.score >= 3.0
    assert res_c.concrete_words_count > 0

    # Abstract German administrative text: Autonomie, Zuständigkeit, Verantwortung
    abstract_text = (
        "Die Autonomieentwicklung erfordert politische Verantwortungsbereitschaft, "
        "Rechtssicherheit und institutionelle Nachhaltigkeit im Minderheitenschutz."
    )
    res_a = analyze_concreteness(abstract_text, language="de")
    assert res_a.score < res_c.score
    assert res_a.abstract_words_count >= 3
    assert res_a.abstract_density > 0


def test_concreteness_italian():
    # Concrete Italian text: pane, mele, casa, treno
    concrete_text = "I contadini preparano il pane e portano le mele in treno vicino alla scuola."
    res_c = analyze_concreteness(concrete_text, language="it")
    assert res_c.score >= 3.0

    # Abstract Italian administrative text: attuazione, disposizione, giurisprudenza
    abstract_text = (
        "L'amministrazione provinciale garantisce la tutela e la valorizzazione "
        "delle competenze istituzionali attraverso la modernizzazione dei servizi."
    )
    res_a = analyze_concreteness(abstract_text, language="it")
    assert res_a.score < res_c.score
    assert res_a.abstract_words_count >= 2


def test_complexity_tokens():
    # High nominal ratio (typical administrative style: Noun + ADP dominant)
    admin_tokens = [
        {"form": "Zur", "lemma": "zu", "upos": "ADP"},
        {"form": "Durchführung", "lemma": "Durchführung", "upos": "NOUN"},
        {"form": "der", "lemma": "der", "upos": "DET"},
        {"form": "Verordnung", "lemma": "Verordnung", "upos": "NOUN"},
        {"form": "über", "lemma": "über", "upos": "ADP"},
        {"form": "Minderheitenrechte", "lemma": "Minderheitenrecht", "upos": "NOUN"},
        {"form": "erfolgt", "lemma": "erfolgen", "upos": "VERB"},
        {"form": "die", "lemma": "der", "upos": "DET"},
        {"form": "Mitteilung", "lemma": "Mitteilung", "upos": "NOUN"},
    ]
    res_admin = analyze_complexity(admin_tokens)
    assert res_admin.nominal_ratio >= 2.0
    assert "Administrative" in res_admin.style_label

    # Dynamic verbal style
    verbal_tokens = [
        {"form": "Wir", "lemma": "wir", "upos": "PRON"},
        {"form": "laufen", "lemma": "laufen", "upos": "VERB"},
        {"form": "schnell", "lemma": "schnell", "upos": "ADV"},
        {"form": "und", "lemma": "und", "upos": "CCONJ"},
        {"form": "sehen", "lemma": "sehen", "upos": "VERB"},
        {"form": "das", "lemma": "das", "upos": "DET"},
        {"form": "Haus", "lemma": "Haus", "upos": "NOUN"},
    ]
    res_verbal = analyze_complexity(verbal_tokens)
    assert res_verbal.nominal_ratio < res_admin.nominal_ratio

