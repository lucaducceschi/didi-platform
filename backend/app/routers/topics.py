"""Read the light LDA topic models (src/nlp/topics.py); training is offline (scripts/train_topics.py)."""

from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from src.languages import get_active_language_codes
from src.nlp import topics as topic_store
from src.ui.data_service import DataService

from backend.app.corpus import get_corpus
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/topics", tags=["topics"])
Corpus = Annotated[DataService, Depends(get_corpus)]


@router.get("/models")
def list_topic_models() -> Dict[str, Any]:
    models = topic_store.list_models(get_settings().topics_path, get_active_language_codes())
    return {"models": models}


def _active_model(path, model_id: str, topic_id: int) -> Dict[str, Any]:
    info = topic_store.get_model_info(path, model_id)
    if info is None or info["language"] not in get_active_language_codes():
        raise HTTPException(404, "Topic model not found")
    if not 0 <= topic_id < info["n_topics"]:
        raise HTTPException(404, "Topic not found")
    return info


@router.get("/models/{model_id}/topics/{topic_id}/terms")
def get_topic_terms(
    model_id: str,
    topic_id: int,
    lam: Annotated[float, Query(ge=0.0, le=1.0, alias="lambda")] = topic_store.DEFAULT_LAMBDA,
    n: Annotated[int, Query(ge=5, le=50)] = 30,
) -> Dict[str, Any]:
    """Terms ranked by LDAvis relevance, with their estimated count in the topic and in the corpus,
    and the closest topics by Jensen-Shannon divergence."""
    path = get_settings().topics_path
    _active_model(path, model_id, topic_id)
    stats = topic_store.load_stats(path, model_id)
    if stats is None:
        raise HTTPException(404, "This model has no term data; retrain it")
    return {
        "model_id": model_id,
        "topic_id": topic_id,
        "lambda": lam,
        "word_share": round(float(stats.word_share[topic_id]), 5),
        "terms": topic_store.ranked_terms(stats, topic_id, lam, n),
        "closest": topic_store.closest_topics(stats, topic_id),
    }


@router.get("/models/{model_id}/topics/{topic_id}/articles")
def get_topic_articles(
    model_id: str,
    topic_id: int,
    corpus: Corpus,
    min_weight: Annotated[float, Query(ge=0.05, le=1.0)] = 0.3,
    source_type: Optional[str] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Dict[str, Any]:
    """Articles where the topic weighs at least min_weight, highest first.

    `article_ids` lists all of them, so the client can save them as a selection;
    `articles` carries metadata for the first `limit`.
    """
    path = get_settings().topics_path
    _active_model(path, model_id, topic_id)
    hits = topic_store.topic_articles(path, model_id, topic_id, min_weight)
    meta = corpus.get_article_metadata([aid for aid, _ in hits])
    hits = [(aid, w) for aid, w in hits
            if aid in meta and (source_type is None or meta[aid]["source_type"] == source_type)]
    return {
        "model_id": model_id,
        "topic_id": topic_id,
        "min_weight": min_weight,
        "total": len(hits),
        "article_ids": [aid for aid, _ in hits],
        "articles": [
            {"id": aid, "weight": w, "title": meta[aid]["title"], "source": meta[aid]["source"],
             "source_type": meta[aid]["source_type"], "language": meta[aid]["language"],
             "publish_date": meta[aid]["publish_date"]}
            for aid, w in hits[:limit]
        ],
    }
