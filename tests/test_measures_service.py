import pytest

from backend.app.services.measures import (
    _is_ingroup_pronoun,
    _is_konjunktiv_i,
    dunning_g2_keyness,
    score_tokens,
)


def test_ingroup_pronouns():
    # German wir/uns
    assert _is_ingroup_pronoun("wir", "wir", "PRON", "Case=Nom|Number=Plur|Person=1", "de")
    assert _is_ingroup_pronoun("uns", "wir", "PRON", "Case=Acc|Number=Plur|Person=1", "de")
    assert not _is_ingroup_pronoun("sie", "sie", "PRON", "Case=Nom|Number=Plur|Person=3", "de")

    # Italian noi/nostro
    assert _is_ingroup_pronoun("noi", "noi", "PRON", "Number=Plur|Person=1", "it")
    assert _is_ingroup_pronoun("nostro", "nostro", "DET", "Gender=Masc|Number=Sing|Person=1|Poss=Yes", "it")
    assert not _is_ingroup_pronoun("loro", "loro", "PRON", "Number=Plur|Person=3", "it")


def test_konjunktiv_i():
    # German Konjunktiv I: Mood=Sub, Tense=Pres
    assert _is_konjunktiv_i("VERB", "VVFIN", "Mood=Sub|Number=Sing|Person=3|Tense=Pres", "de")
    assert _is_konjunktiv_i("AUX", "VAFIN", "Mood=Sub|Number=Sing|Person=3|Tense=Pres", "de")
    # Not Konjunktiv I if past or indicative
    assert not _is_konjunktiv_i("VERB", "VVFIN", "Mood=Ind|Number=Sing|Person=3|Tense=Pres", "de")
    assert not _is_konjunktiv_i("VERB", "VVFIN", "Mood=Sub|Number=Sing|Person=3|Tense=Past", "de")
    # Not available in Italian
    assert not _is_konjunktiv_i("VERB", "V", "Mood=Sub|Tense=Pres", "it")


def test_dunning_g2_keyness():
    target = ["autonomie", "autonomie", "autonomie", "schutz", "gesetz", "recht"]
    reference = ["schule", "kinder", "bildung", "lehrer", "schule", "recht"]
    keyness = dunning_g2_keyness(target, reference, min_count=2, top_n=5, language="de")
    assert len(keyness) > 0
    top_word = keyness[0]
    assert top_word["lemma"] == "autonomie"
    assert top_word["g2"] > 0


def test_score_tokens_empty():
    res = score_tokens([], language="de")
    assert res["word_count"] == 0
    assert res["small_sample"] is True
    assert res["readability"] is None


def test_score_tokens_german():
    tokens = [
        {"form": "Die", "lemma": "der", "upos": "DET", "feats": "", "xpos": ""},
        {"form": "Regierung", "lemma": "Regierung", "upos": "NOUN", "feats": "", "xpos": ""},
        {"form": "betont", "lemma": "betonen", "upos": "VERB", "feats": "", "xpos": ""},
        {"form": "unsere", "lemma": "unser", "upos": "DET", "feats": "Number=Plur|Person=1", "xpos": ""},
        {"form": "Verantwortung", "lemma": "Verantwortung", "upos": "NOUN", "feats": "", "xpos": ""},
        {"form": "für", "lemma": "für", "upos": "ADP", "feats": "", "xpos": ""},
        {"form": "die", "lemma": "der", "upos": "DET", "feats": "", "xpos": ""},
        {"form": "Gerechtigkeit", "lemma": "Gerechtigkeit", "upos": "NOUN", "feats": "", "xpos": ""},
        {"form": ".", "lemma": ".", "upos": "PUNCT", "feats": "", "xpos": ""},
    ]
    res = score_tokens(tokens, language="de")
    assert res["word_count"] == len(tokens)
    assert res["ingroup_pronouns"]["count"] == 1
    assert res["ingroup_pronouns"]["rate_per_1k"] > 0
    assert res["readability"] is not None
    assert res["concreteness"] is not None
    assert res["complexity"] is not None


def test_project_analysis_endpoint(world):
    from tests.test_codebook import add_segment, make_code
    code = make_code(world, "Autonomie")
    add_segment(world.coder, world, code["id"], 0, 10)

    resp = world.coder.get(f"{world.url}/analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "codes" in data
    assert len(data["codes"]) >= 1
    found = next(c for c in data["codes"] if c["code_id"] == str(code["id"]))
    assert found["code_name"] == "Autonomie"
    assert found["passage_count"] == 1
    assert "readability" in found
    assert "concreteness" in found
    assert "complexity" in found


def test_project_corpus_comparison_endpoint(world):
    resp = world.coder.get(f"{world.url}/corpus-comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert "project_id" in data
    assert "article_count" in data
    assert "total_words" in data
    assert "project_profile" in data
    assert "articles" in data


def test_project_comparison_grid_endpoint(world):
    from tests.test_codebook import add_segment, make_code
    code = make_code(world, "GridCode")
    add_segment(world.coder, world, code["id"], 0, 15)

    resp = world.coder.get(f"{world.url}/comparison-grid?row_by=language&measure=count")
    assert resp.status_code == 200
    data = resp.json()
    assert data["row_by"] == "language"
    assert data["measure"] == "count"
    assert "rows" in data
    assert "columns" in data
    assert "cells" in data
    assert len(data["columns"]) >= 1

    # Test CSV export
    csv_resp = world.coder.get(f"{world.url}/exports/comparison-grid.csv?row_by=language&measure=count")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["Content-Type"]
    assert "Comparison Grid" in csv_resp.text


