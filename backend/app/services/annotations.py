"""Coded segments. Positions are 0-based code points with an exclusive end, as Python slices them."""

import hashlib
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.errors import forbidden, invalid, not_found, stale_revision
from backend.app.models import Annotation, ProjectArticle, utcnow
from backend.app.services.codebook import resolve_code


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def trim_selection(text: str, start: int, end: int) -> Tuple[int, int]:
    if start < 0 or end > len(text) or start >= end:
        raise invalid("The selection is outside the article text.")
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start >= end:
        raise invalid("The selection contains only spaces.")
    return start, end


def require_article_in_project(db: Session, project_id: uuid.UUID, article_id: str) -> None:
    if db.get(ProjectArticle, (project_id, article_id)) is None:
        raise not_found("This article in this project")


def create_annotation(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID, article_id: str, full_text: str,
    start: int, end: int, code_id: uuid.UUID, memo: str,
) -> Tuple[Annotation, bool, Optional[str]]:
    """Return (segment, whether it is new, the old code's name if the chosen code had been merged)."""
    require_article_in_project(db, project_id, article_id)
    start, end = trim_selection(full_text, start, end)
    code, merged_from = resolve_code(db, project_id, code_id)
    merged_name = merged_from.name if merged_from else None

    existing = db.scalar(
        select(Annotation).where(
            Annotation.project_id == project_id,
            Annotation.article_id == article_id,
            Annotation.start_pos == start,
            Annotation.end_pos == end,
            Annotation.code_id == code.id,
            Annotation.user_id == user_id,
        )
    )
    if existing:
        return existing, False, merged_name

    annotation = Annotation(
        project_id=project_id,
        article_id=article_id,
        user_id=user_id,
        code_id=code.id,
        start_pos=start,
        end_pos=end,
        quote=full_text[start:end],
        text_sha256=text_hash(full_text),
        memo=memo or "",
    )
    db.add(annotation)
    db.flush()
    db.refresh(annotation)
    return annotation, True, merged_name


def _owned(db: Session, project_id: uuid.UUID, annotation_id: uuid.UUID, user_id: uuid.UUID, revision: int) -> Annotation:
    annotation = db.scalar(select(Annotation).where(Annotation.id == annotation_id).with_for_update())
    if annotation is None or annotation.project_id != project_id:
        raise not_found("This segment")
    if annotation.user_id != user_id:
        raise forbidden("Only the researcher who made this segment can change it.")
    if annotation.revision != revision:
        raise stale_revision("This segment")
    return annotation


def update_annotation(db, project_id, user_id, annotation_id, revision: int, changes: dict) -> Tuple[Annotation, Optional[str]]:
    annotation = _owned(db, project_id, annotation_id, user_id, revision)
    merged_name = None
    changed = False
    if "code_id" in changes and changes["code_id"] != annotation.code_id:
        code, merged_from = resolve_code(db, project_id, changes["code_id"])
        merged_name = merged_from.name if merged_from else None
        if code.id != annotation.code_id:
            annotation.code_id = code.id
            changed = True
    if "memo" in changes and (changes["memo"] or "") != annotation.memo:
        annotation.memo = changes["memo"] or ""
        changed = True
    if changed:
        annotation.revision += 1
        annotation.updated_at = utcnow()
        db.flush()
    return annotation, merged_name


def delete_annotation(db, project_id, user_id, annotation_id, revision: int) -> None:
    db.delete(_owned(db, project_id, annotation_id, user_id, revision))


def list_annotations(db: Session, project_id: uuid.UUID, article_id: str, user_id: Optional[uuid.UUID]) -> List[Annotation]:
    query = select(Annotation).where(Annotation.project_id == project_id, Annotation.article_id == article_id)
    if user_id is not None:
        query = query.where(Annotation.user_id == user_id)
    return list(db.scalars(query.order_by(Annotation.start_pos, Annotation.end_pos, Annotation.created_at)))
