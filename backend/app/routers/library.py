import logging
import sqlite3
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from src.sources import get_source_type
from src.ui.data_service import LANGUAGE_LABELS, SOURCE_LABELS

from backend.app.corpus import get_corpus, snippet_parts
from backend.app.deps import Db, ManagerAccess, MemberAccess, ReadAccess
from backend.app.errors import not_found
from backend.app.models import ProjectArticle
from backend.app.routers.corpus import article_detail
from backend.app.schemas import ArticleDetail
from backend.app.schemas_work import (
    LibraryResponse,
    PresenceOut,
    ProgressOut,
    ProgressUpdate,
    ProjectArticlesAdded,
    ProjectArticlesFromSearch,
    ProjectArticlesRemoved,
    ProjectSearchResponse,
)
from backend.app.services import library

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}")

BAD_SEARCH = "This search could not be understood. Check its quotes and operators."


@router.get("/library", response_model=LibraryResponse)
def get_library(
    access: ReadAccess,
    db: Db,
    language: Annotated[Optional[List[str]], Query()] = None,
    source: Annotated[Optional[List[str]], Query()] = None,
    type: Annotated[Optional[List[str]], Query()] = None,
    status: Optional[Literal["not_started", "in_progress", "done"]] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    res = library.get_library(db, get_corpus(), access.project.id, access.user.id, language, source, type, status, page, page_size)
    if not (access.is_lead or access.user.is_admin):
        res["hidden_articles"] = 0
    return res


@router.post("/articles/remove-unstarted", response_model=ProjectArticlesRemoved)
def remove_unstarted_articles(access: ManagerAccess, db: Db):
    removed = library.remove_unstarted_articles(db, access.project.id, access.user.id)
    db.commit()
    return {"removed": removed}


@router.delete("/articles/{article_id}", status_code=204)
def remove_article(article_id: str, access: ManagerAccess, db: Db) -> None:
    library.remove_article(db, access.project.id, access.user.id, article_id)
    db.commit()


@router.get("/article-search", response_model=ProjectSearchResponse)
def search_for_project(
    access: ReadAccess,
    db: Db,
    q: str = "",
    source: Annotated[Optional[List[str]], Query()] = None,
    type: Annotated[Optional[List[str]], Query()] = None,
    language: Annotated[Optional[List[str]], Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    corpus = get_corpus()
    try:
        rows, total = corpus.search_articles(
            query=q, sources=source, source_types=type, languages=language, use_hybrid=False, active_only=True, limit=page_size, offset=(page - 1) * page_size
        )
        all_matches = set(corpus.search_article_ids(q, sources=source, source_types=type, languages=language, active_only=True))
        can_see_hidden = access.is_lead or access.user.is_admin
        hidden_articles = (corpus.count_unconfigured_matches(query=q, sources=source) if q.strip() else 0) if can_see_hidden else 0
    except sqlite3.OperationalError:
        if q.strip():
            logger.info("Rejected search query %r", q, exc_info=True)
            raise HTTPException(status_code=400, detail=BAD_SEARCH)
        raise
    in_project = set(library.project_article_ids(db, access.project.id))
    return {
        "total": total,
        "in_project_total": len(all_matches & in_project),
        "page": page,
        "page_size": page_size,
        "hidden_articles": hidden_articles,
        "results": [
            {
                "id": row["id"],
                "title": row["title"],
                "source_label": SOURCE_LABELS.get(row["source"], row["source"]),
                "source_type": row.get("source_type") or get_source_type(row["source"]),
                "language_label": LANGUAGE_LABELS.get(row["language"], row["language"]),
                "publish_date": row["publish_date"][:10],
                "word_count": row["word_count"],
                "snippet": snippet_parts(row["snippet"]),
                "in_project": row["id"] in in_project,
            }
            for row in rows
        ],
    }


@router.post("/articles/from-search", response_model=ProjectArticlesAdded)
def add_from_search(body: ProjectArticlesFromSearch, access: ManagerAccess, db: Db):
    try:
        ids = get_corpus().search_article_ids(body.q, sources=body.source, source_types=body.type, languages=body.language, active_only=True)
    except sqlite3.OperationalError:
        if body.q.strip():
            raise HTTPException(status_code=400, detail=BAD_SEARCH)
        raise
    added = library.add_articles(db, access.project.id, access.user.id, ids) if ids else 0
    db.commit()
    return ProjectArticlesAdded(added=added, already_present=len(ids) - added)


def _require_article(db, project_id, article_id: str) -> None:
    if db.get(ProjectArticle, (project_id, article_id)) is None:
        raise not_found("This article in this project")


@router.get("/articles/{article_id}", response_model=ArticleDetail)
def get_project_article(article_id: str, access: ReadAccess, db: Db):
    _require_article(db, access.project.id, article_id)
    return article_detail(get_corpus(), article_id)


@router.get("/articles/{article_id}/dictionary-spans")
def get_project_article_dictionary_spans(article_id: str, access: ReadAccess, db: Db):
    _require_article(db, access.project.id, article_id)
    from backend.app.services.measures import get_article_dictionary_spans
    corpus = get_corpus()
    meta = corpus.get_article_metadata([article_id]).get(article_id, {})
    lang = meta.get("language", "de")
    return get_article_dictionary_spans(article_id, lang)


@router.get("/articles/{article_id}/progress", response_model=ProgressOut)
def get_progress(article_id: str, access: ReadAccess, db: Db):
    _require_article(db, access.project.id, article_id)
    return {"status": library.get_progress(db, access.project.id, article_id, access.user.id)}


@router.put("/articles/{article_id}/progress", response_model=ProgressOut)
def set_progress(article_id: str, body: ProgressUpdate, access: MemberAccess, db: Db):
    _require_article(db, access.project.id, article_id)
    library.set_progress(db, access.project.id, article_id, access.user.id, body.status)
    db.commit()
    return {"status": body.status}


@router.post("/articles/{article_id}/presence", response_model=PresenceOut)
def heartbeat(article_id: str, access: ReadAccess, db: Db):
    _require_article(db, access.project.id, article_id)
    others = library.heartbeat(db, access.project.id, article_id, access.user.id, access.is_member and not access.project.archived)
    db.commit()
    return {"others": others}


@router.delete("/articles/{article_id}/presence", status_code=204)
def leave(article_id: str, access: ReadAccess, db: Db) -> None:
    library.leave(db, access.project.id, article_id, access.user.id)
    db.commit()
