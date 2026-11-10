import pytest


def test_analytics_endpoints_require_login(world):
    assert world.anonymous.get("/api/analytics/radar").status_code == 401
    assert world.anonymous.get("/api/analytics/timeline").status_code == 401
    assert world.anonymous.get("/api/analytics/focus-events").status_code == 401
    assert world.anonymous.get("/api/analytics/word-bubbles").status_code == 401


def test_radar_analytics_returns_data(client):
    res = client.get("/api/analytics/radar")
    assert res.status_code == 200
    data = res.json()
    assert "languages" in data
    assert "pairwise_jsd" in data
    if data["languages"]:
        lang0 = data["languages"][0]
        assert "language" in lang0
        assert "foundations" in lang0
        assert "care" in lang0["foundations"]
        assert "emotions" in lang0
        assert "joy" in lang0["emotions"]


def test_timeline_analytics_returns_series(client):
    res = client.get("/api/analytics/timeline")
    assert res.status_code == 200
    data = res.json()
    assert "series" in data
    assert isinstance(data["series"], list)


def test_focus_events_list_and_details(client):
    res = client.get("/api/analytics/focus-events")
    assert res.status_code == 200
    events = res.json()
    assert isinstance(events, list)
    assert len(events) > 0
    first_event = events[0]
    assert "id" in first_event
    assert "title" in first_event
    assert "coverage" in first_event

    # Test event details endpoint
    detail_res = client.get(f"/api/analytics/focus-events/{first_event['id']}", params={"window_days": 30})
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert "event_date" in detail
    assert "pre_count" in detail
    assert "post_count" in detail
    assert "moral_divergence" in detail
    assert "keyness" in detail


def test_word_bubbles_analytics(client):
    res = client.get("/api/analytics/word-bubbles")
    assert res.status_code == 200
    bubbles = res.json()
    assert isinstance(bubbles, list)
    assert len(bubbles) > 0
    b0 = bubbles[0]
    assert "id" in b0
    assert "term" in b0
    assert "category" in b0
    assert "salience" in b0
    assert "de_ratio" in b0
    assert "it_ratio" in b0
    assert "yearly_trend" in b0

    # Test other valid modes
    res_lang = client.get("/api/analytics/word-bubbles?mode=languages")
    assert res_lang.status_code == 200
    assert isinstance(res_lang.json(), list)

    res_disc = client.get("/api/analytics/word-bubbles?mode=discourse")
    assert res_disc.status_code == 200
    assert isinstance(res_disc.json(), list)

    # Invalid mode returns 422 Unprocessable Entity
    res_invalid = client.get("/api/analytics/word-bubbles?mode=invalid_mode")
    assert res_invalid.status_code == 422


