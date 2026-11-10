import uuid
import pytest
from backend.app.models import Annotation, Code


def test_inter_coder_agreement_calculation(world):
    coder = world.coder
    coder2 = world.coder2
    lead = world.lead
    project_url = world.url

    # 1. Create two codes: "Autonomy:Competences" and "Autonomy:Fiscal"
    resp_c1 = coder.post(f"{project_url}/codes", json={"name": "Competences", "color": "#2E86AB"})
    assert resp_c1.status_code == 201
    code1_id = resp_c1.json()["id"]

    resp_c2 = coder.post(f"{project_url}/codes", json={"name": "Fiscal", "color": "#D1495B"})
    assert resp_c2.status_code == 201
    code2_id = resp_c2.json()["id"]

    # 2. Coder 1 annotates span [10, 50] with Code 1
    resp_a1 = coder.post(
        f"{project_url}/articles/fx_de_1/annotations",
        json={"start": 10, "end": 50, "code_id": code1_id, "memo": "Coder 1 note"},
    )
    assert resp_a1.status_code == 201

    # 3. Coder 2 annotates overlapping span [12, 48] with Code 1 (AGREEMENT)
    resp_a2 = coder2.post(
        f"{project_url}/articles/fx_de_1/annotations",
        json={"start": 12, "end": 48, "code_id": code1_id, "memo": "Coder 2 note"},
    )
    assert resp_a2.status_code == 201

    # 4. Coder 1 annotates span [50, 75] with Code 1
    resp_a3 = coder.post(
        f"{project_url}/articles/fx_de_1/annotations",
        json={"start": 50, "end": 75, "code_id": code1_id},
    )
    assert resp_a3.status_code == 201, resp_a3.text

    # 5. Coder 2 annotates overlapping span [52, 73] with Code 2 (DISAGREEMENT)
    resp_a4 = coder2.post(
        f"{project_url}/articles/fx_de_1/annotations",
        json={"start": 52, "end": 73, "code_id": code2_id},
    )
    assert resp_a4.status_code == 201, resp_a4.text

    # 6. Fetch inter-coder agreement
    ica_resp = coder.get(f"{project_url}/codes/inter-coder-agreement")
    assert ica_resp.status_code == 200
    data = ica_resp.json()

    assert data["total_overlapping_segments"] >= 2
    assert data["total_agreed_segments"] >= 1
    assert 0.0 <= data["global_observed_agreement"] <= 1.0
    assert "global_kappa" in data
    assert "global_interpretation" in data

    # Check pair statistics
    assert len(data["pairs"]) >= 1
    pair = data["pairs"][0]
    assert pair["overlapping_segments"] == 2
    assert pair["agreed_segments"] == 1
    assert pair["observed_agreement"] == 0.5

    # Check confusion matrix
    assert len(data["confusion_matrix"]) >= 1
    conf = data["confusion_matrix"][0]
    assert conf["count"] == 1

    # Check disagreements list
    assert len(data["disagreements"]) >= 1
    disag = data["disagreements"][0]
    assert disag["article_id"] == "fx_de_1"
    assert disag["code_1_name"] in ["Competences", "Fiscal"]
    assert disag["code_2_name"] in ["Competences", "Fiscal"]
    assert disag["code_1_name"] != disag["code_2_name"]
