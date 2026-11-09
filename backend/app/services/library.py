"""A project's set of articles, and who has worked on what."""

import uuid
from collections import Counter
from datetime import timedelta
from typing import Dict, List, Optional

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from src.languages import get_active_language_codes
from src.ui.data_service import LANGUAGE_LABELS, SOURCE_LABELS, DataService

from backend.app.errors import conflict, not_found
from backend.app.models import Annotation, ArticleProgress, Presence, ProjectArticle, User, utcnow
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


def remove_article(db: Session, project_id: uuid.UUID, user_id: uuid.UUID, article_id: str) -> None:
    """Remove an article from a project, unless it has segments. Nobody's coding is ever lost this way."""
    condition = (ProjectArticle.project_id == project_id, ProjectArticle.article_id == article_id)
    # Waits for any segment save in progress on this article, so the count below includes it.
    if db.scalar(select(ProjectArticle.article_id).where(*condition).with_for_update()) is None:
        raise not_found("This article in this project")
    segments, coders = db.execute(
        select(func.count(), func.count(Annotation.user_id.distinct())).where(
            Annotation.project_id == project_id, Annotation.article_id == article_id
        )
    ).one()
    if segments:
        raise conflict(
            f"This article can't be removed because it has {segments} coded {'passage' if segments == 1 else 'passages'} "
            f"from {coders} {'coder' if coders == 1 else 'coders'}. Each coder would have to delete their own first."
        )
    _delete_articles(db, project_id, [article_id])
    log_activity(db, "articles.removed", article_id, user_id=user_id, project_id=project_id)


def _worked_on(db: Session, project_id: uuid.UUID) -> set:
    """Articles with a segment or a status from anyone."""
    segments = select(Annotation.article_id).where(Annotation.project_id == project_id)
    progress = select(ArticleProgress.article_id).where(ArticleProgress.project_id == project_id)
    return set(db.scalars(segments.union(progress)))


def remove_unstarted_articles(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> int:
    """Remove every article nobody has started, as after adding too many by mistake."""
    # Taking the locks first means the check below sees any segment save that was in progress.
    locked = set(db.scalars(select(ProjectArticle.article_id).where(ProjectArticle.project_id == project_id).with_for_update()))
    unstarted = sorted(locked - _worked_on(db, project_id))
    _delete_articles(db, project_id, unstarted)
    if unstarted:
        log_activity(db, "articles.removed", f"{len(unstarted)} articles", user_id=user_id, project_id=project_id)
    return len(unstarted)


def _delete_articles(db: Session, project_id: uuid.UUID, article_ids: List[str]) -> None:
    for index in range(0, len(article_ids), 1000):
        batch = article_ids[index : index + 1000]
        for model in (ArticleProgress, Presence, ProjectArticle):
            db.execute(delete(model).where(model.project_id == project_id, model.article_id.in_(batch)))


PRESENCE_TIMEOUT_SECONDS = 90


def start_progress(db: Session, project_id: uuid.UUID, article_id: str, user_id: uuid.UUID) -> None:
    """Mark an article in progress on first coding. It doesn't reopen an article marked done."""
    db.execute(
        insert(ArticleProgress)
        .values(project_id=project_id, article_id=article_id, user_id=user_id, status="in_progress", updated_at=utcnow())
        .on_conflict_do_nothing()
    )


def set_progress(db: Session, project_id: uuid.UUID, article_id: str, user_id: uuid.UUID, status: str) -> None:
    statement = insert(ArticleProgress).values(
        project_id=project_id, article_id=article_id, user_id=user_id, status=status, updated_at=utcnow()
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=["project_id", "article_id", "user_id"],
            set_={"status": statement.excluded.status, "updated_at": statement.excluded.updated_at},
        )
    )


def get_progress(db: Session, project_id: uuid.UUID, article_id: str, user_id: uuid.UUID) -> str:
    progress = db.get(ArticleProgress, (project_id, article_id, user_id))
    return progress.status if progress else "not_started"


def heartbeat(db: Session, project_id: uuid.UUID, article_id: str, user_id: uuid.UUID, is_member: bool) -> List[User]:
    """Record that this person has the article open, and return who else does. It never blocks anyone."""
    now = utcnow()
    cutoff = now - timedelta(seconds=PRESENCE_TIMEOUT_SECONDS)
    db.execute(delete(Presence).where(Presence.last_seen < cutoff))
    if is_member:
        statement = insert(Presence).values(project_id=project_id, article_id=article_id, user_id=user_id, last_seen=now)
        db.execute(
            statement.on_conflict_do_update(
                index_elements=["project_id", "article_id", "user_id"], set_={"last_seen": statement.excluded.last_seen}
            )
        )
    rows = db.scalars(
        select(Presence).where(Presence.project_id == project_id, Presence.article_id == article_id, Presence.user_id != user_id)
    )
    return sorted((row.user for row in rows), key=lambda user: user.display_name.lower())


def leave(db: Session, project_id: uuid.UUID, article_id: str, user_id: uuid.UUID) -> None:
    db.execute(delete(Presence).where(Presence.project_id == project_id, Presence.article_id == article_id, Presence.user_id == user_id))


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
    active_codes = get_active_language_codes()

    hidden_articles = sum(1 for item in metadata.values() if item and item["language"] not in active_codes)
    language_counts = Counter(item["language"] for item in metadata.values() if item and item["language"] in active_codes)
    source_counts = Counter(item["source"] for item in metadata.values() if item and (item["language"] in active_codes or item["language"] is None))

    mine = dict(
        db.execute(
            select(ArticleProgress.article_id, ArticleProgress.status).where(
                ArticleProgress.project_id == project_id, ArticleProgress.user_id == user_id
            )
        ).all()
    )

    def matches(article_id: str) -> bool:
        item = metadata.get(article_id)
        # Articles in unconfigured languages are hidden from library view
        if item is not None and item["language"] not in active_codes:
            return False
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
        "unstarted_total": len(set(article_ids) - _worked_on(db, project_id)),
        "total": len(filtered),
        "page": page,
        "page_size": page_size,
        "results": results,
        "hidden_articles": hidden_articles,
        "languages": [{"id": key, "label": LANGUAGE_LABELS.get(key, key), "count": count} for key, count in sorted(language_counts.items())],
        "sources": [{"id": key, "label": SOURCE_LABELS.get(key, key), "count": count} for key, count in sorted(source_counts.items())],
    }
