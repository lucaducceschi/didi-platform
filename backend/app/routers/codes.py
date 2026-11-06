import uuid
from typing import List

from fastapi import APIRouter, Query

from backend.app.deps import CodebookLeadAccess, Db, MemberAccess, ReadAccess
from backend.app.schemas_work import CodeCreate, CodeOut, CodeUpdate, MergePreview, MergeRequest
from backend.app.services import codebook

router = APIRouter(prefix="/api/projects/{project_id}/codes")


def _with_counts(db, project_id, code) -> CodeOut:
    out = CodeOut.model_validate(code)
    out.segment_count, out.coder_count = codebook.segment_counts(db, project_id).get(code.id, (0, 0))
    return out


@router.get("", response_model=List[CodeOut])
def list_codes(access: ReadAccess, db: Db):
    counts = codebook.segment_counts(db, access.project.id)
    results = []
    for code in codebook.active_codes(db, access.project.id):
        out = CodeOut.model_validate(code)
        out.segment_count, out.coder_count = counts.get(code.id, (0, 0))
        results.append(out)
    return results


@router.post("", response_model=CodeOut, status_code=201)
def create_code(body: CodeCreate, access: MemberAccess, db: Db):
    code = codebook.create_code(db, access.project.id, access.user.id, body.name, body.parent_id, body.definition, body.color)
    db.commit()
    return _with_counts(db, access.project.id, code)


@router.patch("/{code_id}", response_model=CodeOut)
def update_code(code_id: uuid.UUID, body: CodeUpdate, access: CodebookLeadAccess, db: Db):
    changes = body.model_dump(exclude_unset=True, exclude={"revision"})
    code = codebook.update_code(db, access.project.id, access.user.id, code_id, body.revision, changes)
    db.commit()
    return _with_counts(db, access.project.id, code)


@router.delete("/{code_id}", status_code=204)
def delete_code(code_id: uuid.UUID, access: CodebookLeadAccess, db: Db, revision: int = Query(...)) -> None:
    codebook.delete_code(db, access.project.id, access.user.id, code_id, revision)
    db.commit()


@router.get("/{code_id}/merge-preview", response_model=MergePreview)
def merge_preview(code_id: uuid.UUID, access: CodebookLeadAccess, db: Db, into: uuid.UUID = Query(...)):
    return codebook.merge_preview(db, access.project.id, code_id, into)


@router.post("/{code_id}/merge", response_model=CodeOut)
def merge(code_id: uuid.UUID, body: MergeRequest, access: CodebookLeadAccess, db: Db):
    target = codebook.merge_codes(
        db, access.project.id, access.user.id, code_id, body.target_id, body.source_revision, body.target_revision
    )
    db.commit()
    return _with_counts(db, access.project.id, target)
