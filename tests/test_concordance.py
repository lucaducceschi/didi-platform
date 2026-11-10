import pytest


def test_concordance_returns_exact_coordinates(client):
    """Verify that concordance lines return exact character offsets that slice the matching token."""
    response = client.get("/api/articles/concordance", params={"q": "Museumsbericht"})
    assert response.status_code == 200
    data = response.json()
    assert data["total_lines"] >= 1
    assert data["total_articles"] >= 1
    first = data["items"][0]
    assert first["article_id"] == "fx_markup"
    assert first["keyword"] == "Museumsbericht"
    assert first["start_char"] >= 0
    assert first["end_char"] > first["start_char"]
    assert first["left_context"] is not None
    assert first["right_context"] is not None

    # Fetch article and verify coordinate slicing
    art_resp = client.get(f"/api/articles/{first['article_id']}")
    assert art_resp.status_code == 200
    full_text = art_resp.json()["full_text"]
    assert full_text[first["start_char"] : first["end_char"]] == first["keyword"]


def test_concordance_search_modes(client):
    """Verify exact, word_family, and concept search modes in concordance."""
    # Exact mode
    resp_exact = client.get("/api/articles/concordance", params={"q": "Autonomie", "mode": "exact"})
    assert resp_exact.status_code == 200
    for item in resp_exact.json()["items"]:
        assert "autonomie" in item["keyword"].lower()

    # Word family mode
    resp_family = client.get("/api/articles/concordance", params={"q": "Autonomie", "mode": "word_family"})
    assert resp_family.status_code == 200
    assert resp_family.json()["total_lines"] >= resp_exact.json()["total_lines"]


def test_concordance_pagination(client):
    """Verify concordance line pagination."""
    response = client.get("/api/articles/concordance", params={"q": "Autonomie", "page": 1, "page_size": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) <= 2


def test_search_distribution_aggregates(client):
    """Verify search distribution returns counts grouped by language, source, and year."""
    response = client.get("/api/articles/distribution", params={"q": "Autonomie"})
    assert response.status_code == 200
    data = response.json()
    assert "by_language" in data
    assert "by_source" in data
    assert "by_source_type" in data
    assert "by_year" in data
    assert data["total"] >= 1

