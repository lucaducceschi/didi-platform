import pytest


def test_create_and_list_selections(world):
    client = world.coder
    project_url = world.url

    # Create selection with explicit article IDs
    create_payload = {
        "name": "Autonomy Articles Cohort",
        "description": "Key articles discussing autonomy statute",
        "article_ids": ["fx_de_1", "fx_it_1"],
    }
    resp = client.post(f"{project_url}/selections", json=create_payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Autonomy Articles Cohort"
    assert created["article_count"] == 2
    selection_id = created["id"]

    # List selections
    list_resp = client.get(f"{project_url}/selections")
    assert list_resp.status_code == 200
    selections = list_resp.json()
    assert any(s["id"] == selection_id for s in selections)

    # Get selection details
    detail_resp = client.get(f"{project_url}/selections/{selection_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["article_count"] == 2
    assert set(detail["article_ids"]) == {"fx_de_1", "fx_it_1"}

    # Delete selection
    del_resp = client.delete(f"{project_url}/selections/{selection_id}")
    assert del_resp.status_code == 204

    # Verify deleted
    assert client.get(f"{project_url}/selections/{selection_id}").status_code == 404


def test_create_selection_from_query_definition(world):
    client = world.coder
    project_url = world.url

    create_payload = {
        "name": "Dynamic Autonomie Query",
        "query_definition": {
            "q": "Autonomie",
            "mode": "word_family",
        },
    }
    resp = client.post(f"{project_url}/selections", json=create_payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["article_count"] >= 1
    selection_id = created["id"]

    # Refresh selection
    refresh_resp = client.post(f"{project_url}/selections/{selection_id}/refresh")
    assert refresh_resp.status_code == 200
    refreshed = refresh_resp.json()
    assert refreshed["article_count"] >= 1


def test_selection_permissions(world):
    coder = world.coder
    outsider = world.outsider
    project_url = world.url

    # Outsider cannot list or create
    assert outsider.get(f"{project_url}/selections").status_code == 404
    assert outsider.post(f"{project_url}/selections", json={"name": "Hacked"}).status_code == 404

    # Coder creates
    resp = coder.post(f"{project_url}/selections", json={"name": "Coder Sel", "article_ids": ["fx_de_1"]})
    assert resp.status_code == 201
    sel_id = resp.json()["id"]

    # Outsider cannot get or delete
    assert outsider.get(f"{project_url}/selections/{sel_id}").status_code == 404
    assert outsider.delete(f"{project_url}/selections/{sel_id}").status_code == 404


def test_compare_selections(world):
    client = world.coder
    project_url = world.url

    # 1. Create Selection A (German articles)
    resp_a = client.post(
        f"{project_url}/selections",
        json={"name": "Selection German", "article_ids": ["fx_de_1", "fx_de_nfd"]},
    )
    assert resp_a.status_code == 201
    sel_a_id = resp_a.json()["id"]

    # 2. Create Selection B (Italian articles)
    resp_b = client.post(
        f"{project_url}/selections",
        json={"name": "Selection Italian", "article_ids": ["fx_it_1", "fx_it_crlf"]},
    )
    assert resp_b.status_code == 201
    sel_b_id = resp_b.json()["id"]

    # 3. Create Selection Mixed (DE + IT)
    resp_mixed = client.post(
        f"{project_url}/selections",
        json={"name": "Selection Mixed", "article_ids": ["fx_de_1", "fx_it_1"]},
    )
    assert resp_mixed.status_code == 201
    sel_mixed_id = resp_mixed.json()["id"]

    # Test Mode 1: Selection A vs Selection B
    comp_ab = client.post(
        f"{project_url}/selections/compare",
        json={"selection_a_id": sel_a_id, "selection_b_id": sel_b_id},
    )
    assert comp_ab.status_code == 200, comp_ab.text
    data_ab = comp_ab.json()
    assert data_ab["comparison_type"] == "selection_vs_selection"
    assert data_ab["profile_a"]["article_count"] == 2
    assert data_ab["profile_b"]["article_count"] == 2
    assert "divergence" in data_ab
    assert "mfdi" in data_ab["divergence"]
    assert "emotion_jsd" in data_ab["divergence"]

    # Test Mode 2: Selection A vs Regional Corpus Baseline
    comp_base = client.post(
        f"{project_url}/selections/compare",
        json={"selection_a_id": sel_a_id},
    )
    assert comp_base.status_code == 200, comp_base.text
    data_base = comp_base.json()
    assert data_base["comparison_type"] == "selection_vs_baseline"
    assert "Corpus Baseline" in data_base["profile_b"]["label"]

    # Test Mode 3: Partition within Mixed Selection by Language
    comp_part = client.post(
        f"{project_url}/selections/compare",
        json={"selection_a_id": sel_mixed_id, "partition_by": "language"},
    )
    assert comp_part.status_code == 200, comp_part.text
    data_part = comp_part.json()
    assert data_part["comparison_type"] == "partition"
    assert data_part["partition_label"] == "language"
    assert data_part["profile_a"]["dominant_language"] == "de"
    assert data_part["profile_b"]["dominant_language"] == "it"


