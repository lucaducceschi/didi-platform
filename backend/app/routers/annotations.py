import uuid
from typing import List, Literal

from fastapi import APIRouter, Query, Response, status

from backend.app.corpus import get_corpus
from backend.app.deps import Db, MemberAccess, ReadAccess
from backend.app.errors import not_found
from backend.app.schemas_work import AnnotationCreate, AnnotationOut, AnnotationUpdate
from backend.app.services import annotations as service

router = APIRouter(prefix="/api/projects/{project_id}")


def _out(annotation, created=None, merged_from=None) -> AnnotationOut:
    out = AnnotationOut.model_validate(annotation)
    out.created = created
    out.merged_from = merged_from
    return out


@router.get("/articles/{article_id}/annotations", response_model=List[AnnotationOut])
def list_annotations(article_id: str, access: ReadAccess, db: Db, scope: Literal["mine", "all"] = "mine"):
    user_id = access.user.id if scope == "mine" else None
    return [_out(item) for item in service.list_annotations(db, access.project.id, article_id, user_id)]


@router.post("/articles/{article_id}/annotations", response_model=AnnotationOut, status_code=201)
def create_annotation(article_id: str, body: AnnotationCreate, access: MemberAccess, db: Db, response: Response):
    service.require_article_in_project(db, access.project.id, article_id)
    article = get_corpus().get_article_by_id(article_id)
    if article is None:
        raise not_found("This article")
    annotation, created, merged_from = service.create_annotation(
        db, access.project.id, access.user.id, article_id, article["full_text"], body.start, body.end, body.code_id, body.memo
    )
    db.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return _out(annotation, created=created, merged_from=merged_from)


@router.patch("/annotations/{annotation_id}", response_model=AnnotationOut)
def update_annotation(annotation_id: uuid.UUID, body: AnnotationUpdate, access: MemberAccess, db: Db):
    changes = body.model_dump(exclude_unset=True, exclude={"revision"})
    annotation, merged_from = service.update_annotation(db, access.project.id, access.user.id, annotation_id, body.revision, changes)
    db.commit()
    return _out(annotation, merged_from=merged_from)


@router.delete("/annotations/{annotation_id}", status_code=204)
def delete_annotation(annotation_id: uuid.UUID, access: MemberAccess, db: Db, revision: int = Query(...)) -> None:
    service.delete_annotation(db, access.project.id, access.user.id, annotation_id, revision)
    db.commit()
