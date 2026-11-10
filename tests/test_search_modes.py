import pytest
from src.ui.data_service import DataService


@pytest.fixture
def data_service(fixture_corpus):
    return DataService(db_path=fixture_corpus)


def test_apostrophe_and_curly_quote_handling_does_not_crash(client):
    # Test unquoted Italian apostrophes (straight and curly)
    for q in ["dell'autonomia", "dell’autonomia", "l'autonomia", "l’autonomia", "un'autonomia", "un’altra"]:
        res = client.get("/api/articles/search", params={"q": q})
        assert res.status_code == 200, f"Search failed for {q}: {res.text}"
        data = res.json()
        assert "query_interpretation" in data
        assert data["query_interpretation"]["normalized_query"] is not None


def test_hyphenated_compound_does_not_crash(client):
    for q in ["SVP-Parteitag", "Tirol-Südtirol-Trentino", "non-profit"]:
        res = client.get("/api/articles/search", params={"q": q})
        assert res.status_code == 200, f"Search failed for {q}: {res.text}"


def test_search_modes_differentiation(data_service):
    # 1. Exact Mode
    eff_exact, note_exact = data_service.build_fts_query("Autonomie", search_mode="exact")
    assert eff_exact == '"Autonomie"'
    assert "Exact" in note_exact

    # 2. Word Family Mode
    eff_wf, note_wf = data_service.build_fts_query("Autonomie", search_mode="word_family")
    assert eff_wf == "Autonomie*"
    assert "Word family" in note_wf

    # 3. Concept Mode
    eff_concept, note_concept = data_service.build_fts_query("Autonomie", search_mode="concept")
    assert "OR" in eff_concept
    assert "Concept Expansion" in note_concept


def test_search_mode_api_query_interpretation(client):
    res = client.get("/api/articles/search", params={"q": "Autonomie", "mode": "exact"})
    assert res.status_code == 200
    data = res.json()
    interp = data["query_interpretation"]
    assert interp["original_query"] == "Autonomie"
    assert interp["search_mode"] == "exact"
    assert interp["effective_fts"] == '"Autonomie"'
    assert len(interp["expansion_terms"]) >= 1
    assert interp["expansion_terms"][0]["category"] == "exact_phrase"


def test_date_range_filtering(client):
    res = client.get(
        "/api/articles/search",
        params={"q": "Autonomie", "min_date": "2020-01-01", "max_date": "2022-12-31"}
    )
    assert res.status_code == 200
    data = res.json()
    interp = data["query_interpretation"]
    assert interp["active_filters"]["min_date"] == "2020-01-01"
    assert interp["active_filters"]["max_date"] == "2022-12-31"


def test_coverage_warnings_generated(data_service):
    # Provinz news prior to July 2021 generates coverage warning
    warns = data_service.get_coverage_warnings(sources=["provinz_news"], min_date="2019-01-01")
    assert len(warns) > 0
    assert "Official press office coverage (Provinz News) begins in July 2021" in warns[0]

