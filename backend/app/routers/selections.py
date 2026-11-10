import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from src.ui.data_service import DataService

from backend.app.corpus import get_corpus
from backend.app.deps import Db, MemberAccess, ReadAccess
from backend.app.errors import forbidden, not_found
from backend.app.models import ActivityLog, ProjectArticle, SavedCorpusSelection, SavedSelectionMember
from backend.app.schemas_work import (
    SavedSelectionCreate,
    SavedSelectionDetail,
    SavedSelectionOut,
    SelectionCompareRequest,
    SelectionCompareResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects/{project_id}")


@router.get("/selections", response_model=List[SavedSelectionOut])
def list_selections(access: ReadAccess, db: Db) -> List[SavedSelectionOut]:
    """List all saved corpus selections within the project."""
    rows = db.scalars(
        select(SavedCorpusSelection)
        .where(SavedCorpusSelection.project_id == access.project.id)
        .order_by(SavedCorpusSelection.created_at.desc())
    ).all()
    return [SavedSelectionOut.model_validate(row) for row in rows]


@router.post("/selections", response_model=SavedSelectionOut, status_code=201)
def create_selection(
    body: SavedSelectionCreate,
    access: MemberAccess,
    db: Db,
    corpus: DataService = Depends(get_corpus),
) -> SavedSelectionOut:
    """
    Save a reusable corpus selection.
    If query_definition is provided, materializes matching article IDs into snapshot members.
    """
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Selection name cannot be empty.")

    article_ids: List[str] = []
    if body.article_ids:
        article_ids = list(dict.fromkeys(body.article_ids))
    elif body.query_definition:
        # Materialize articles matching query definition
        q = body.query_definition.get("q", "")
        mode = body.query_definition.get("mode", "concept")
        sources = body.query_definition.get("sources")
        languages = body.query_definition.get("languages")
        types = body.query_definition.get("types")
        min_date = body.query_definition.get("min_date")
        max_date = body.query_definition.get("max_date")

        matched_rows, total = corpus.search_articles(
            query=q,
            search_mode=mode,
            sources=sources,
            source_types=types,
            languages=languages,
            min_date=min_date,
            max_date=max_date,
            active_only=True,
            limit=5000,
            offset=0,
        )
        article_ids = [r["id"] for r in matched_rows]

    now = datetime.now(timezone.utc)
    selection = SavedCorpusSelection(
        id=uuid.uuid4(),
        project_id=access.project.id,
        name=name,
        description=body.description.strip(),
        query_definition=body.query_definition,
        article_count=len(article_ids),
        created_by=access.user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(selection)
    db.flush()

    for aid in article_ids:
        db.add(SavedSelectionMember(selection_id=selection.id, article_id=aid, added_at=now))

    db.add(
        ActivityLog(
            user_id=access.user.id,
            project_id=access.project.id,
            action="create_selection",
            target=selection.name,
            details={"selection_id": str(selection.id), "article_count": len(article_ids)},
        )
    )
    db.commit()
    db.refresh(selection)
    return SavedSelectionOut.model_validate(selection)


@router.get("/selections/{selection_id}", response_model=SavedSelectionDetail)
def get_selection(selection_id: uuid.UUID, access: ReadAccess, db: Db) -> SavedSelectionDetail:
    """Retrieve selection details including member article IDs."""
    selection = db.get(SavedCorpusSelection, selection_id)
    if selection is None or selection.project_id != access.project.id:
        raise not_found("This selection")

    members = db.scalars(
        select(SavedSelectionMember.article_id)
        .where(SavedSelectionMember.selection_id == selection_id)
        .order_by(SavedSelectionMember.added_at.asc())
    ).all()

    out = SavedSelectionDetail.model_validate(selection)
    out.article_ids = list(members)
    return out


@router.delete("/selections/{selection_id}", status_code=204)
def delete_selection(selection_id: uuid.UUID, access: MemberAccess, db: Db) -> None:
    """Delete a saved selection."""
    selection = db.get(SavedCorpusSelection, selection_id)
    if selection is None or selection.project_id != access.project.id:
        raise not_found("This selection")

    if not (access.is_lead or access.user.is_admin or selection.created_by == access.user.id):
        raise forbidden("Only the selection creator, a project lead, or an admin can delete it.")

    name = selection.name
    db.execute(delete(SavedCorpusSelection).where(SavedCorpusSelection.id == selection_id))
    db.add(
        ActivityLog(
            user_id=access.user.id,
            project_id=access.project.id,
            action="delete_selection",
            target=name,
            details={"selection_id": str(selection_id)},
        )
    )
    db.commit()


@router.post("/selections/{selection_id}/refresh", response_model=SavedSelectionDetail)
def refresh_selection(
    selection_id: uuid.UUID,
    access: MemberAccess,
    db: Db,
    corpus: DataService = Depends(get_corpus),
) -> SavedSelectionDetail:
    """Re-materialize a saved selection snapshot against the corpus based on its query definition."""
    selection = db.get(SavedCorpusSelection, selection_id)
    if selection is None or selection.project_id != access.project.id:
        raise not_found("This selection")

    if not selection.query_definition:
        raise HTTPException(status_code=400, detail="Cannot refresh a selection that has no query definition.")

    q = selection.query_definition.get("q", "")
    mode = selection.query_definition.get("mode", "concept")
    sources = selection.query_definition.get("sources")
    languages = selection.query_definition.get("languages")
    types = selection.query_definition.get("types")
    min_date = selection.query_definition.get("min_date")
    max_date = selection.query_definition.get("max_date")

    matched_rows, total = corpus.search_articles(
        query=q,
        search_mode=mode,
        sources=sources,
        source_types=types,
        languages=languages,
        min_date=min_date,
        max_date=max_date,
        active_only=True,
        limit=5000,
        offset=0,
    )
    new_ids = [r["id"] for r in matched_rows]
    now = datetime.now(timezone.utc)

    # Replace members
    db.execute(delete(SavedSelectionMember).where(SavedSelectionMember.selection_id == selection_id))
    for aid in new_ids:
        db.add(SavedSelectionMember(selection_id=selection_id, article_id=aid, added_at=now))

    selection.article_count = len(new_ids)
    selection.updated_at = now
    db.add(
        ActivityLog(
            user_id=access.user.id,
            project_id=access.project.id,
            action="refresh_selection",
            target=selection.name,
            details={"selection_id": str(selection_id), "new_article_count": len(new_ids)},
        )
    )
    db.commit()
    db.refresh(selection)

    out = SavedSelectionDetail.model_validate(selection)
    out.article_ids = new_ids
    return out


@router.post("/selections/compare", response_model=SelectionCompareResponse)
def compare_corpus_selections(
    body: SelectionCompareRequest,
    access: ReadAccess,
    db: Db,
) -> SelectionCompareResponse:
    """
    Generalized comparison engine:
    - Selection A vs Selection B
    - Selection A vs Regional Corpus Baseline
    - Partitions within Selection A (e.g. language, source_type, source, year)
    """
    from backend.app.services.comparisons import compare_selections

    result = compare_selections(
        db=db,
        project=access.project,
        selection_a_id=body.selection_a_id,
        selection_b_id=body.selection_b_id,
        partition_by=body.partition_by,
    )
    return SelectionCompareResponse.model_validate(result)

