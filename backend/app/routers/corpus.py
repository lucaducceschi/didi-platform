import logging
import sqlite3
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from src.sources import SOURCE_TYPE_LABELS, get_source_type
from src.ui.data_service import LANGUAGE_LABELS, SOURCE_LABELS, DataService

from backend.app.corpus import get_corpus, snippet_parts
from backend.app.deps import CurrentUser, Db, OptionalUser
from backend.app.models import Project, ProjectArticle, ProjectMember
from backend.app.schemas import (
    ArticleDetail,
    ArticleMetrics,
    ArticleSummary,
    ConcordanceLine,
    ConcordanceResponse,
    CorpusSummary,
    Facet,
    QueryInterpretation,
    SearchDistribution,
    SearchResponse,
)
from backend.app.schemas_work import ArticleProject

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
Corpus = Annotated[DataService, Depends(get_corpus)]

_CORPUS_SUMMARY_CACHE: Optional[CorpusSummary] = None


@router.get("/corpus/summary", response_model=CorpusSummary)
def corpus_summary(corpus: Corpus) -> CorpusSummary:
    global _CORPUS_SUMMARY_CACHE
    if _CORPUS_SUMMARY_CACHE is not None:
        return _CORPUS_SUMMARY_CACHE

    summary = corpus.get_corpus_summary(active_only=True)
    _CORPUS_SUMMARY_CACHE = CorpusSummary(
        total_articles=summary["total_articles"],
        total_words=summary["total_words"],
        min_date=summary["min_date"][:10],
        max_date=summary["max_date"][:10],
        sources=[
            Facet(id=key, label=SOURCE_LABELS.get(key, key), count=value["count"])
            for key, value in sorted(summary["sources"].items())
        ],
        languages=[
            Facet(id=key, label=LANGUAGE_LABELS.get(key, key), count=value["count"])
            for key, value in sorted(summary["languages"].items())
        ],
        source_types=[
            Facet(id=key, label=SOURCE_TYPE_LABELS.get(key, key), count=value["count"])
            for key, value in sorted(summary.get("source_types", {}).items())
        ],
    )
    return _CORPUS_SUMMARY_CACHE


@router.get("/articles/search", response_model=SearchResponse)
def search_articles(
    corpus: Corpus,
    db: Db,
    user: OptionalUser = None,
    q: str = "",
    mode: Annotated[str, Query()] = "word_family",
    source: Annotated[Optional[List[str]], Query()] = None,
    type: Annotated[Optional[List[str]], Query()] = None,
    language: Annotated[Optional[List[str]], Query()] = None,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchResponse:
    try:
        rows, total = corpus.search_articles(
            query=q,
            sources=source,
            source_types=type,
            languages=language,
            min_date=min_date,
            max_date=max_date,
            search_mode=mode,
            use_hybrid=False,
            active_only=True,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        can_see_hidden = False
        if user:
            if user.is_admin:
                can_see_hidden = True
            else:
                is_lead = db.scalar(
                    select(ProjectMember.project_id).where(
                        ProjectMember.user_id == user.id, ProjectMember.role == "lead"
                    ).limit(1)
                )
                can_see_hidden = is_lead is not None
        hidden_articles = (corpus.count_unconfigured_matches(query=q, sources=source) if q.strip() else 0) if can_see_hidden else 0

        interpretation = corpus.interpret_query(
            raw_query=q,
            search_mode=mode,
            sources=source,
            languages=language,
            source_types=type,
            min_date=min_date,
            max_date=max_date,
            total_results=total,
        )
    except sqlite3.OperationalError:
        # FTS5 reports bad user syntax, such as an unbalanced quote, as an OperationalError.
        # The corpus is read-only, so with a query present this is almost always the search text.
        if q.strip():
            logger.info("Rejected search query %r", q, exc_info=True)
            raise HTTPException(status_code=400, detail="This search could not be understood. Check its quotes and operators.")
        raise
    return SearchResponse(
        total=total,
        page=page,
        page_size=page_size,
        hidden_articles=hidden_articles,
        query_interpretation=QueryInterpretation(**interpretation),
        results=[
            ArticleSummary(
                **{
                    **row,
                    "snippet": snippet_parts(row["snippet"]),
                    "source_label": SOURCE_LABELS.get(row["source"], row["source"]),
                    "language_label": LANGUAGE_LABELS.get(row["language"], row["language"]),
                }
            )
            for row in rows
        ],
    )


@router.get("/articles/concordance", response_model=ConcordanceResponse)
def get_concordance(
    corpus: Corpus,
    q: str = "",
    mode: Annotated[str, Query()] = "word_family",
    source: Annotated[Optional[List[str]], Query()] = None,
    type: Annotated[Optional[List[str]], Query()] = None,
    language: Annotated[Optional[List[str]], Query()] = None,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    window_size: Annotated[int, Query(ge=10, le=200)] = 50,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ConcordanceResponse:
    try:
        data = corpus.get_concordance(
            query=q,
            search_mode=mode,
            sources=source,
            source_types=type,
            languages=language,
            min_date=min_date,
            max_date=max_date,
            window_size=window_size,
            page=page,
            page_size=page_size,
            active_only=True,
        )
        return ConcordanceResponse(
            total_lines=data["total_lines"],
            total_articles=data["total_articles"],
            page=data["page"],
            page_size=data["page_size"],
            items=[ConcordanceLine(**item) for item in data["items"]],
        )
    except sqlite3.OperationalError:
        if q.strip():
            logger.info("Rejected concordance query %r", q, exc_info=True)
            raise HTTPException(status_code=400, detail="This search could not be understood. Check its quotes and operators.")
        raise


@router.get("/articles/distribution", response_model=SearchDistribution)
def get_search_distribution(
    corpus: Corpus,
    q: str = "",
    mode: Annotated[str, Query()] = "word_family",
    source: Annotated[Optional[List[str]], Query()] = None,
    type: Annotated[Optional[List[str]], Query()] = None,
    language: Annotated[Optional[List[str]], Query()] = None,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> SearchDistribution:
    try:
        data = corpus.get_search_distribution(
            query=q,
            search_mode=mode,
            sources=source,
            source_types=type,
            languages=language,
            min_date=min_date,
            max_date=max_date,
            active_only=True,
        )
        return SearchDistribution(**data)
    except sqlite3.OperationalError:
        if q.strip():
            logger.info("Rejected distribution query %r", q, exc_info=True)
            raise HTTPException(status_code=400, detail="This search could not be understood. Check its quotes and operators.")
        raise


def article_detail(corpus: DataService, article_id: str) -> ArticleDetail:
    article = corpus.get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return ArticleDetail(
        **{key: article[key] for key in ("id", "source", "language", "url", "title", "publish_date", "author", "category", "word_count", "full_text")},
        source_label=SOURCE_LABELS.get(article["source"], article["source"]),
        source_type=article.get("source_type") or get_source_type(article["source"]),
        twin_article_id=article.get("twin_article_id"),
        language_label=LANGUAGE_LABELS.get(article["language"], article["language"]),
        metrics=ArticleMetrics(**{key: article.get(key) for key in ArticleMetrics.model_fields}),
        metadata=article.get("metadata") or {},
    )


@router.get("/articles/{article_id}", response_model=ArticleDetail)
def get_article(article_id: str, corpus: Corpus) -> ArticleDetail:
    return article_detail(corpus, article_id)


@router.get("/articles/{article_id}/dictionary-spans")
def article_dictionary_spans(article_id: str, corpus: Corpus):
    from backend.app.services.measures import get_article_dictionary_spans
    meta = corpus.get_article_metadata([article_id]).get(article_id, {})
    lang = meta.get("language", "de")
    return get_article_dictionary_spans(article_id, lang)


@router.get("/articles/{article_id}/projects", response_model=List[ArticleProject])
def article_projects(article_id: str, corpus: Corpus, user: CurrentUser, db: Db):
    """The caller's own projects and whether each holds this article, so the corpus page can lead to coding."""
    if not corpus.get_article_metadata([article_id]):
        raise HTTPException(status_code=404, detail="Article not found.")
    rows = db.execute(
        select(Project, ProjectMember.role, ProjectArticle.article_id)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .outerjoin(ProjectArticle, (ProjectArticle.project_id == Project.id) & (ProjectArticle.article_id == article_id))
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.archived, func.lower(Project.name))
    )
    return [
        ArticleProject(id=project.id, name=project.name, archived=project.archived, role=role, in_project=held is not None)
        for project, role, held in rows
    ]
