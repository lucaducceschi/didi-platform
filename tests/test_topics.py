import numpy as np
import pytest

from src.nlp import topics


def _corpus():
    """30 documents with two clear vocabularies plus one term shared by all."""
    a = np.array([5, 5, 5, 0, 0, 0, 8], dtype=np.uint32)
    b = np.array([0, 0, 0, 5, 5, 5, 8], dtype=np.uint32)
    terms = ["autonomie", "statut", "land", "schule", "lehrer", "klasse", "jahr"]
    docs = {}
    for i in range(30):
        counts = a if i < 15 else b
        docs[f"d{i:02d}"] = topics.array("I", np.repeat(np.arange(7), counts).tolist())
    return docs, terms


@pytest.fixture(scope="module")
def fitted():
    docs, terms = _corpus()
    params = topics.LdaParams(n_topics=2, min_df=2, max_df=1.0, max_iter=30)
    ids, X, vocab = topics.build_matrix(docs, terms, params)
    doc_topic, stats = topics.fit_lda(X, vocab, params)
    return ids, doc_topic, stats, params


def test_build_matrix_prunes_by_document_frequency():
    docs, terms = _corpus()
    docs["rare"] = topics.array("I", [0, 1])
    params = topics.LdaParams(min_df=2, max_df=0.9)
    ids, X, vocab = topics.build_matrix(docs, terms, params, min_terms=3)
    assert "rare" not in ids                 # too few terms
    assert "jahr" not in vocab               # in every document: above max_df
    assert X.shape == (30, len(vocab)) and X[0].sum() == 15


def test_fit_separates_topics_and_stats_are_consistent(fitted):
    ids, doc_topic, stats, _ = fitted
    t_a, t_b = doc_topic[0].argmax(), doc_topic[-1].argmax()
    assert t_a != t_b
    assert {x["term"] for x in topics.ranked_terms(stats, t_a, 1.0, 3)} <= {"autonomie", "statut", "land", "jahr"}
    assert stats.word_share.sum() == pytest.approx(1.0)
    est = stats.term_topic_counts()
    assert est.sum(axis=0) == pytest.approx(stats.term_counts)  # LDAvis: counts add up per term
    assert topics.closest_topics(stats, t_a)[0]["topic_id"] == t_b


def test_relevance_lambda_demotes_terms_common_to_all_topics(fitted):
    _, doc_topic, stats, _ = fitted
    t = doc_topic[0].argmax()
    frequent = [x["term"] for x in topics.ranked_terms(stats, t, 1.0, 7)]
    distinctive = [x["term"] for x in topics.ranked_terms(stats, t, 0.0, 7)]
    assert frequent[0] == "jahr"              # most probable term in both topics
    assert distinctive.index("jahr") > frequent.index("jahr")


def test_normalize_lemma():
    assert topics.normalize_lemma(" Südtirol ") == "südtirol"
    assert topics.normalize_lemma("SVP-Parteitag") == "svp-parteitag"
    assert topics.normalize_lemma("zu") is None
    assert topics.normalize_lemma("2024") is None


def test_build_matrix_drops_stopwords():
    docs, terms = _corpus()
    params = topics.LdaParams(min_df=2, max_df=1.0)
    _, _, vocab = topics.build_matrix(docs, terms, params, stopwords={"land", "jahr"})
    assert "land" not in vocab and "jahr" not in vocab and "statut" in vocab


def test_timeline_shares_add_up_per_period():
    doc_topic = np.array([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]])
    arrays = topics.timeline_arrays(doc_topic, np.array([10, 10, 20]),
                                    ["2020-01", "2020-02", "2021-03"],
                                    ["journalism", "journalism", "official_press"])
    (journalism, press) = topics.topic_timeline(arrays, 0, "year")
    assert journalism["points"] == [{"period": "2020", "share": 0.75, "articles": 2, "words": 20}]
    assert press["points"][0]["share"] == 0.0
    monthly = topics.topic_timeline(arrays, 0, "month")[0]["points"]
    assert [p["period"] for p in monthly] == ["2020-01", "2020-02"]


def _save(path, fitted, ids=None, language="de"):
    model_ids, doc_topic, stats, params = fitted
    ids = ids or model_ids
    timeline = topics.timeline_arrays(doc_topic[: len(ids)], np.full(len(ids), 10),
                                      ["2020-01"] * len(ids), ["journalism"] * len(ids))
    topics.save_model(path, f"lda_{language}_k2", language, ids, doc_topic[: len(ids)], stats, params, timeline)


def test_save_and_read_round_trip(tmp_path, fitted):
    path = tmp_path / "topics.db"
    _save(path, fitted)
    (model,) = topics.list_models(path)
    assert sum(t["dominant_articles"] for t in model["topics"]) == 30
    assert sum(t["word_share"] for t in model["topics"]) == pytest.approx(1.0, abs=1e-3)
    stats = topics.load_stats(path, "lda_de_k2")
    assert stats.phi.shape == fitted[2].phi.shape and stats.vocabulary[0] == fitted[2].vocabulary[0]
    assert topics.list_models(path, languages={"it"}) == []
    assert topics.list_models(tmp_path / "missing.db") == []


def test_topic_api(world, fixture_records, tmp_path, monkeypatch, fitted):
    from backend.app.settings import get_settings

    ids = [r["id"] for r in fixture_records if r["language"] == "de"][:3]
    path = tmp_path / "topics.db"
    _save(path, fitted, ids=ids)
    _save(path, fitted, ids=["x"], language="lld_gherd")  # deferred language: never listed
    monkeypatch.setenv("DIDI_TOPICS_PATH", str(path))
    get_settings.cache_clear()

    assert world.anonymous.get("/api/topics/models").status_code == 401
    models = world.coder.get("/api/topics/models").json()["models"]
    assert [m["language"] for m in models] == ["de"]

    t = int(fitted[1][0].argmax())
    res = world.coder.get(f"/api/topics/models/lda_de_k2/topics/{t}/articles", params={"min_weight": 0.5}).json()
    assert res["article_ids"] and set(res["article_ids"]) <= set(ids)
    assert res["articles"][0]["title"]

    terms = world.coder.get(f"/api/topics/models/lda_de_k2/topics/{t}/terms", params={"lambda": 0.6, "n": 5}).json()
    assert len(terms["terms"]) == 5 and terms["closest"][0]["topic_id"] == 1 - t
    assert world.coder.get("/api/topics/models/lda_de_k2/topics/9/terms").status_code == 404

    timeline = world.coder.get(f"/api/topics/models/lda_de_k2/topics/{t}/timeline").json()
    (series,) = timeline["series"]
    assert series["source_type"] == "journalism" and series["points"][0]["small_sample"] is True
    assert world.coder.get(f"/api/topics/models/lda_de_k2/topics/{t}/timeline",
                           params={"granularity": "week"}).status_code == 422
    assert world.coder.get("/api/topics/models/lda_lld_gherd_k2/topics/0/articles").status_code == 404
