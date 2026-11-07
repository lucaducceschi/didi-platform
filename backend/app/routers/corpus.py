import logging
import sqlite3
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from src.ui.data_service import LANGUAGE_LABELS, SOURCE_LABELS, DataService

from backend.app.corpus import get_corpus, snippet_parts
from backend.app.deps import CurrentUser, Db
from backend.app.models import Project, ProjectArticle, ProjectMember
from backend.app.schemas import ArticleDetail, ArticleMetrics, ArticleSummary, CorpusSummary, Facet, SearchResponse
from backend.app.schemas_work import ArticleProject

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
Corpus = Annotated[DataService, Depends(get_corpus)]


@router.get("/corpus/summary", response_model=CorpusSummary)
def corpus_summary(corpus: Corpus) -> CorpusSummary:
    summary = corpus.get_corpus_summary()
    return CorpusSummary(
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
    )


@router.get("/articles/search", response_model=SearchResponse)
def search_articles(
    corpus: Corpus,
    q: str = "",
    source: Annotated[Optional[List[str]], Query()] = None,
    language: Annotated[Optional[List[str]], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchResponse:
    try:
        rows, total = corpus.search_articles(
            query=q,
            sources=source,
            languages=language,
            use_hybrid=False,
            limit=page_size,
            offset=(page - 1) * page_size,
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


def article_detail(corpus: DataService, article_id: str) -> ArticleDetail:
    article = corpus.get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found.")
    return ArticleDetail(
        **{key: article[key] for key in ("id", "source", "language", "url", "title", "publish_date", "author", "category", "word_count", "full_text")},
        source_label=SOURCE_LABELS.get(article["source"], article["source"]),
        language_label=LANGUAGE_LABELS.get(article["language"], article["language"]),
        metrics=ArticleMetrics(**{key: article.get(key) for key in ArticleMetrics.model_fields}),
        metadata=article.get("metadata") or {},
    )


@router.get("/articles/{article_id}", response_model=ArticleDetail)
def get_article(article_id: str, corpus: Corpus) -> ArticleDetail:
    return article_detail(corpus, article_id)


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
