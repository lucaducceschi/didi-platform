import uuid
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, Query, Response

from backend.app.corpus import get_corpus
from backend.app.deps import Db, ReadAccess
from backend.app.schemas_work import PassagesResponse
from backend.app.services import exports
from backend.app.services import passages as service

router = APIRouter(prefix="/api/projects/{project_id}")


def _filters(
    code: Optional[uuid.UUID] = None,
    subcodes: bool = True,
    language: Annotated[Optional[List[str]], Query()] = None,
    source: Annotated[Optional[List[str]], Query()] = None,
    type: Annotated[Optional[List[str]], Query()] = None,
    coder: Optional[uuid.UUID] = None,
    status: Optional[Literal["active", "stale"]] = None,
    q: Optional[str] = None,
) -> service.PassageFilters:
    return service.PassageFilters(code, subcodes, language, source, type, coder, status, query=q)


Filters = Annotated[service.PassageFilters, Depends(_filters)]


@router.get("/passages", response_model=PassagesResponse)
def list_passages(
    access: ReadAccess,
    db: Db,
    filters: Filters,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    res = service.find_passages(db, get_corpus(), access.project.id, filters, page, page_size)
    if not (access.is_lead or access.user.is_admin):
        res["hidden_passages"] = 0
    return res


@router.get("/passages.csv")
def export_passages(access: ReadAccess, db: Db, filters: Filters) -> Response:
    corpus = get_corpus()
    annotations = service.matching_annotations(db, corpus, access.project.id, filters)
    content = exports.write_annotations_csv(db, corpus, access.project.id, access.project.name, annotations)
    return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="didi_passages.csv"'})
