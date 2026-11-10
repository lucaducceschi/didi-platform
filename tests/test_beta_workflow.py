import json
import pytest


def test_full_didi_beta_research_workflow(world):
    """
    End-to-end verification of the DIDI Beta workflow:
    1. Search & Query Modes
    2. KWIC Concordance & Exact Coordinate Alignment
    3. Qualitative Coding & Annotation Linkage
    4. Inter-Coder Agreement (Cohen's Kappa & Confusion Matrix)
    5. Saved Corpus Selections (Subcorpora)
    6. Generalized Cross-Subcorpus Comparison (Radar, JSD, Dunning G²)
    7. Full Provenance & Reproducibility Manifest (JSON + Markdown)
    """
    coder1 = world.coder
    coder2 = world.coder2
    project_url = world.url

    # -------------------------------------------------------------
    # 1. Search & Query Interpretation
    # -------------------------------------------------------------
    search_resp = coder1.get("/api/articles/search?q=Autonomie&mode=word_family&language=de")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert "query_interpretation" in search_data
    assert search_data["query_interpretation"]["search_mode"] == "word_family"
    assert search_data["total"] >= 1
    sample_article_id = search_data["results"][0]["id"]

    # -------------------------------------------------------------
    # 2. KWIC Concordance & Exact Coordinate Alignment
    # -------------------------------------------------------------
    kwic_resp = coder1.get("/api/articles/concordance?q=Autonomie&mode=word_family&language=de")
    assert kwic_resp.status_code == 200
    kwic_data = kwic_resp.json()
    assert kwic_data["total_lines"] >= 1
    sample_hit = kwic_data["items"][0]
    art_id = sample_hit["article_id"]
    s_pos = sample_hit["start_char"]
    e_pos = sample_hit["end_char"]
    matched_term = sample_hit["keyword"]

    # Fetch article and verify coordinate integrity
    art_resp = coder1.get(f"/api/articles/{art_id}")
    assert art_resp.status_code == 200
    full_text = art_resp.json()["full_text"]
    extracted_text = full_text[s_pos:e_pos]
    assert extracted_text.lower() == matched_term.lower(), (
        f"Coordinate mismatch: expected '{matched_term}', got '{extracted_text}' at [{s_pos}:{e_pos}]"
    )

    # -------------------------------------------------------------
    # 3. Qualitative Coding in Project
    # -------------------------------------------------------------
    code1_resp = coder1.post(f"{project_url}/codes", json={"name": "Regional Autonomy", "color": "#1f77b4"})
    assert code1_resp.status_code == 201
    code1_id = code1_resp.json()["id"]

    code2_resp = coder1.post(f"{project_url}/codes", json={"name": "Minority Protection", "color": "#2ca02c"})
    assert code2_resp.status_code == 201
    code2_id = code2_resp.json()["id"]

    # Coder 1 creates annotation exactly at concordance coordinate
    ann1_resp = coder1.post(
        f"{project_url}/articles/{art_id}/annotations",
        json={"start": s_pos, "end": e_pos, "code_id": code1_id, "memo": "Key autonomy passage"},
    )
    assert ann1_resp.status_code == 201

    # Coder 2 creates overlapping annotation with different code (Disagreement)
    ann2_resp = coder2.post(
        f"{project_url}/articles/{art_id}/annotations",
        json={"start": s_pos, "end": e_pos, "code_id": code2_id, "memo": "Minority framing note"},
    )
    assert ann2_resp.status_code == 201

    # -------------------------------------------------------------
    # 4. Inter-Coder Reliability (Cohen's Kappa & Disagreements)
    # -------------------------------------------------------------
    ica_resp = coder1.get(f"{project_url}/codes/inter-coder-agreement")
    assert ica_resp.status_code == 200
    ica = ica_resp.json()
    assert ica["total_coders"] == 2
    assert ica["total_overlapping_segments"] >= 1
    assert len(ica["disagreements"]) >= 1
    disag = ica["disagreements"][0]
    assert disag["article_id"] == art_id
    assert disag["start_pos"] == s_pos
    assert disag["end_pos"] == e_pos

    # -------------------------------------------------------------
    # 5. Saved Corpus Selections
    # -------------------------------------------------------------
    sel_a_resp = coder1.post(
        f"{project_url}/selections",
        json={
            "name": "German Corpus Selection",
            "description": "German articles talking about autonomy",
            "article_ids": ["fx_de_1", "fx_de_nfd"],
        },
    )
    assert sel_a_resp.status_code == 201
    sel_a_id = sel_a_resp.json()["id"]

    sel_b_resp = coder1.post(
        f"{project_url}/selections",
        json={
            "name": "Italian Corpus Selection",
            "description": "Italian articles subset",
            "article_ids": ["fx_it_1", "fx_it_crlf"],
        },
    )
    assert sel_b_resp.status_code == 201
    sel_b_id = sel_b_resp.json()["id"]

    # -------------------------------------------------------------
    # 6. Generalized Subcorpus Comparison
    # -------------------------------------------------------------
    comp_resp = coder1.post(
        f"{project_url}/selections/compare",
        json={"selection_a_id": sel_a_id, "selection_b_id": sel_b_id},
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["comparison_type"] == "selection_vs_selection"
    assert comp_data["profile_a"]["article_count"] == 2
    assert comp_data["profile_b"]["article_count"] == 2
    assert "foundations" in comp_data["profile_a"]
    assert "emotions" in comp_data["profile_a"]
    assert "divergence" in comp_data
    assert "mfdi" in comp_data["divergence"]
    assert "emotion_jsd" in comp_data["divergence"]

    # -------------------------------------------------------------
    # 7. Reproducibility Manifest (JSON + Markdown)
    # -------------------------------------------------------------
    manifest_resp = coder1.get(f"{project_url}/exports/manifest.json")
    assert manifest_resp.status_code == 200
    assert "application/json" in manifest_resp.headers["content-type"]
    manifest = manifest_resp.json()
    assert manifest["project"]["name"] == "Autonomy"
    assert manifest["provenance"]["platform"] == "DIDI Platform"
    assert manifest["provenance"]["version"] == "0.2.0-beta"
    assert len(manifest["codebook"]) >= 2
    assert len(manifest["saved_selections"]) >= 2
    assert manifest["reliability"]["total_coders"] == 2
    assert "apa_bibliography" in manifest
    assert len(manifest["apa_bibliography"]) >= 1

    # Markdown export
    report_resp = coder1.get(f"{project_url}/exports/manifest.md")
    assert report_resp.status_code == 200
    assert "text/markdown" in report_resp.headers["content-type"]
    md_content = report_resp.text
    assert "# DIDI Platform: Reproducibility & Provenance Manifest" in md_content
    assert "Qualitative Codebook" in md_content
    assert "APA 7th Edition Bibliography" in md_content
