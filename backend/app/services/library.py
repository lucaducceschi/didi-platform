"""A project's set of articles, and who has worked on what."""

import uuid
from collections import Counter
from typing import Dict, List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from src.ui.data_service import LANGUAGE_LABELS, SOURCE_LABELS, DataService

from backend.app.models import Annotation, ArticleProgress, ProjectArticle, User, utcnow
from backend.app.services.activity import log_activity


def add_articles(db: Session, project_id: uuid.UUID, user_id: uuid.UUID, article_ids: List[str]) -> int:
    """Add articles to a project and return how many were new. Safe with thousands of articles."""
    added = 0
    now = utcnow()
    for index in range(0, len(article_ids), 1000):
        rows = [
            {"project_id": project_id, "article_id": article_id, "added_by": user_id, "added_at": now}
            for article_id in article_ids[index : index + 1000]
        ]
        result = db.execute(insert(ProjectArticle).values(rows).on_conflict_do_nothing().returning(ProjectArticle.article_id))
        added += len(result.all())
    if added:
        log_activity(db, "articles.added", f"{added} articles", user_id=user_id, project_id=project_id)
    return added


def project_article_ids(db: Session, project_id: uuid.UUID) -> List[str]:
    return list(db.scalars(select(ProjectArticle.article_id).where(ProjectArticle.project_id == project_id)))


def _progress(db: Session, project_id: uuid.UUID, article_ids: List[str]) -> Dict[str, Dict[uuid.UUID, str]]:
    found: Dict[str, Dict[uuid.UUID, str]] = {}
    rows = db.execute(
        select(ArticleProgress.article_id, ArticleProgress.user_id, ArticleProgress.status).where(
            ArticleProgress.project_id == project_id, ArticleProgress.article_id.in_(article_ids)
        )
    )
    for article_id, user_id, status in rows:
        found.setdefault(article_id, {})[user_id] = status
    return found


def _segment_counts(db: Session, project_id: uuid.UUID, article_ids: List[str]) -> Dict[str, Dict[uuid.UUID, tuple]]:
    found: Dict[str, Dict[uuid.UUID, tuple]] = {}
    rows = db.execute(
        select(
            Annotation.article_id,
            Annotation.user_id,
            func.count(),
            func.sum(case((Annotation.status == "stale", 1), else_=0)),
        )
        .where(Annotation.project_id == project_id, Annotation.article_id.in_(article_ids))
        .group_by(Annotation.article_id, Annotation.user_id)
    )
    for article_id, user_id, total, stale in rows:
        found.setdefault(article_id, {})[user_id] = (total, stale)
    return found


def get_library(
    db: Session,
    corpus: DataService,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    languages: Optional[List[str]],
    sources: Optional[List[str]],
    status: Optional[str],
    page: int,
    page_size: int,
) -> dict:
    article_ids = project_article_ids(db, project_id)
    metadata = corpus.get_article_metadata(article_ids)
    language_counts = Counter(item["language"] for item in metadata.values())
    source_counts = Counter(item["source"] for item in metadata.values())

    mine = dict(
        db.execute(
            select(ArticleProgress.article_id, ArticleProgress.status).where(
                ArticleProgress.project_id == project_id, ArticleProgress.user_id == user_id
            )
        ).all()
    )

    def matches(article_id: str) -> bool:
        item = metadata.get(article_id)
        # An article that left the corpus has no variety or source, so those filters hide it.
        if languages and (item is None or item["language"] not in languages):
            return False
        if sources and (item is None or item["source"] not in sources):
            return False
        return not status or mine.get(article_id, "not_started") == status

    # Newest first; articles no longer in the corpus sort last, so they aren't lost among results.
    filtered = sorted(
        filter(matches, article_ids),
        key=lambda article_id: (article_id in metadata, metadata.get(article_id, {}).get("publish_date", ""), article_id),
        reverse=True,
    )
    page_ids = filtered[(page - 1) * page_size : page * page_size]

    progress = _progress(db, project_id, page_ids)
    counts = _segment_counts(db, project_id, page_ids)
    user_ids = {uid for by_user in (*progress.values(), *counts.values()) for uid in by_user}
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}

    results = []
    for article_id in page_ids:
        item = metadata.get(article_id)
        coders = []
        for uid in sorted(
            set(progress.get(article_id, {})) | set(counts.get(article_id, {})),
            key=lambda value: users[value].display_name.lower(),
        ):
            total, stale = counts.get(article_id, {}).get(uid, (0, 0))
            coders.append({"user": users[uid], "status": progress.get(article_id, {}).get(uid), "segments": total, "stale_segments": stale})
        results.append({
            "id": article_id,
            "in_corpus": item is not None,
            "title": item["title"] if item else article_id,
            "source": item["source"] if item else None,
            "source_label": SOURCE_LABELS.get(item["source"], item["source"]) if item else None,
            "language": item["language"] if item else None,
            "language_label": LANGUAGE_LABELS.get(item["language"], item["language"]) if item else None,
            "publish_date": item["publish_date"][:10] if item else None,
            "author": item["author"] if item else None,
            "word_count": item["word_count"] if item else None,
            "my_status": mine.get(article_id, "not_started"),
            "coders": coders,
        })

    return {
        "project_total": len(article_ids),
        "total": len(filtered),
        "page": page,
        "page_size": page_size,
        "results": results,
        "languages": [{"id": key, "label": LANGUAGE_LABELS.get(key, key), "count": count} for key, count in sorted(language_counts.items())],
        "sources": [{"id": key, "label": SOURCE_LABELS.get(key, key), "count": count} for key, count in sorted(source_counts.items())],
    }
