"""CSV exports of a project's work."""

import csv
import io
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from src.ui.data_service import DataService

from backend.app.models import Annotation, Code
from backend.app.services.codebook import code_paths, segment_counts

ANNOTATION_COLUMNS = (
    "annotation_id", "project", "article_id", "article_title", "source", "language", "publish_date", "article_url",
    "coder_username", "coder_name", "code_id", "code_path", "start_pos", "end_pos", "quote", "memo", "status",
    "text_sha256", "created_at", "updated_at",
)
CODE_COLUMNS = ("code_id", "code_path", "name", "parent_id", "definition", "color", "segments", "coders", "merged_into", "created_at")


def _as_csv(columns, rows) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    # The byte order mark makes Excel read accented text correctly.
    return buffer.getvalue().encode("utf-8-sig")


def annotations_csv(db: Session, corpus: DataService, project_id: uuid.UUID, project_name: str) -> bytes:
    annotations = list(
        db.scalars(
            select(Annotation)
            .where(Annotation.project_id == project_id)
            .order_by(Annotation.article_id, Annotation.start_pos, Annotation.created_at)
        )
    )
    paths = code_paths(db, project_id)
    articles = corpus.get_article_metadata([a.article_id for a in annotations])
    rows = []
    for a in annotations:
        article = articles.get(a.article_id, {})
        rows.append({
            "annotation_id": a.id,
            "project": project_name,
            "article_id": a.article_id,
            "article_title": article.get("title", ""),
            "source": article.get("source", ""),
            "language": article.get("language", ""),
            "publish_date": (article.get("publish_date") or "")[:10],
            "article_url": article.get("url", ""),
            "coder_username": a.user.username,
            "coder_name": a.user.display_name,
            "code_id": a.code_id,
            "code_path": paths.get(a.code_id, ""),
            "start_pos": a.start_pos,
            "end_pos": a.end_pos,
            "quote": a.quote,
            "memo": a.memo,
            "status": a.status,
            "text_sha256": a.text_sha256,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        })
    return _as_csv(ANNOTATION_COLUMNS, rows)


def codes_csv(db: Session, project_id: uuid.UUID) -> bytes:
    paths = code_paths(db, project_id)
    counts = segment_counts(db, project_id)
    codes = db.scalars(select(Code).where(Code.project_id == project_id).order_by(Code.created_at))
    rows = [
        {
            "code_id": code.id,
            "code_path": paths[code.id],
            "name": code.name,
            "parent_id": code.parent_id or "",
            "definition": code.definition,
            "color": code.color,
            "segments": counts.get(code.id, (0, 0))[0],
            "coders": counts.get(code.id, (0, 0))[1],
            "merged_into": code.merged_into or "",
            "created_at": code.created_at.isoformat(),
        }
        for code in codes
    ]
    return _as_csv(CODE_COLUMNS, rows)
