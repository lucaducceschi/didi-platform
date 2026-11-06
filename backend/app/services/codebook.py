"""Per-project codebooks: the rules in docs/coding/PRD.md, Section 7."""

import uuid
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from backend.app.errors import conflict, invalid, not_found, stale_revision
from backend.app.models import Annotation, Code, Project, utcnow
from backend.app.services.activity import log_activity

# Mid-tone colors that read on light and dark backgrounds once shown as translucent highlights.
PALETTE = (
    "#D1495B", "#E8A33D", "#4C9F70", "#2E86AB", "#8E6BBF", "#C9587F",
    "#3CA6A6", "#B7791F", "#5C7CFA", "#7A9E3E", "#E0703A", "#6D7B8D",
)

# The tags from the original Streamlit form, offered as a ready-made starting point.
STARTER_CODES = (
    "Autonomy:Competences",
    "Minority:Language Rights",
    "School:Bilingualism",
    "Brenner:Transit",
    "Coalition:Politics",
    "Fiscal:Financial Autonomy",
    "Identity:Ethnicity",
    "Culture:Literature",
)


def _lock_codebook(db: Session, project_id: uuid.UUID) -> None:
    """
    Run structural changes one at a time per project, so checks such as cycles stay true.

    key_share keeps foreign-key checks from waiting on this lock. Otherwise a segment being saved
    and a merge could deadlock, each waiting on a row the other has locked.
    """
    db.execute(select(Project.id).where(Project.id == project_id).with_for_update(key_share=True))


def active_codes(db: Session, project_id: uuid.UUID) -> List[Code]:
    return list(
        db.scalars(
            select(Code)
            .where(Code.project_id == project_id, Code.merged_into.is_(None))
            .order_by(Code.sort_order, func.lower(Code.name))
        )
    )


def segment_counts(db: Session, project_id: uuid.UUID) -> Dict[uuid.UUID, Tuple[int, int]]:
    """Return {code id: (segments, distinct coders)}."""
    rows = db.execute(
        select(Annotation.code_id, func.count(), func.count(Annotation.user_id.distinct()))
        .where(Annotation.project_id == project_id)
        .group_by(Annotation.code_id)
    )
    return {code_id: (segments, coders) for code_id, segments, coders in rows}


def _next_color(db: Session, project_id: uuid.UUID) -> str:
    return PALETTE[db.scalar(select(func.count()).select_from(Code).where(Code.project_id == project_id)) % len(PALETTE)]


def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise invalid("A code needs a name.")
    if len(name) > 120:
        raise invalid("Code names can have at most 120 characters.")
    return name


def _get_code(db: Session, project_id: uuid.UUID, code_id: uuid.UUID) -> Code:
    code = db.get(Code, code_id)
    if code is None or code.project_id != project_id:
        raise not_found("This code")
    return code


def _get_active(db: Session, project_id: uuid.UUID, code_id: uuid.UUID, what: str = "This code") -> Code:
    code = _get_code(db, project_id, code_id)
    if code.merged_into is not None:
        raise conflict(f"{what} was merged into another code. Reload the codebook and try again.")
    return code


def _check_name_free(
    db: Session, project_id: uuid.UUID, parent_id: Optional[uuid.UUID], name: str, ignore: Iterable[uuid.UUID] = ()
) -> None:
    query = select(Code.id).where(
        Code.project_id == project_id,
        Code.merged_into.is_(None),
        func.lower(Code.name) == name.lower(),
        Code.parent_id.is_(None) if parent_id is None else Code.parent_id == parent_id,
    )
    ignored = set(ignore)
    if any(found not in ignored for found in db.scalars(query)):
        raise conflict(f"A code named '{name}' already exists at this level.")


def _insert_code(db, project_id, user_id, name, parent_id=None, definition="", color=None, sort_order=0) -> Code:
    code = Code(
        project_id=project_id,
        name=name,
        parent_id=parent_id,
        definition=definition,
        color=color or _next_color(db, project_id),
        sort_order=sort_order,
        created_by=user_id,
    )
    db.add(code)
    db.flush()
    return code


def create_code(db, project_id, user_id, name, parent_id=None, definition="", color=None) -> Code:
    _lock_codebook(db, project_id)
    name = _clean_name(name)
    if parent_id is not None:
        _get_active(db, project_id, parent_id, "The parent code")
    _check_name_free(db, project_id, parent_id, name)
    code = _insert_code(db, project_id, user_id, name, parent_id, definition or "", color)
    log_activity(db, "code.created", name, user_id=user_id, project_id=project_id, code_id=str(code.id))
    return code


def _descendant_ids(db: Session, project_id: uuid.UUID, code_id: uuid.UUID) -> set:
    children: Dict[Optional[uuid.UUID], List[uuid.UUID]] = {}
    for item_id, parent_id in db.execute(
        select(Code.id, Code.parent_id).where(Code.project_id == project_id, Code.merged_into.is_(None))
    ):
        children.setdefault(parent_id, []).append(item_id)
    found, pending = set(), [code_id]
    while pending:
        for child in children.get(pending.pop(), []):
            found.add(child)
            pending.append(child)
    return found


def update_code(db, project_id, user_id, code_id, revision: int, changes: dict) -> Code:
    _lock_codebook(db, project_id)
    code = _get_active(db, project_id, code_id)
    if code.revision != revision:
        raise stale_revision("This code")

    new_name = _clean_name(changes["name"]) if "name" in changes else code.name
    new_parent = changes["parent_id"] if "parent_id" in changes else code.parent_id
    if "parent_id" in changes and new_parent is not None:
        if new_parent == code.id or new_parent in _descendant_ids(db, project_id, code.id):
            raise conflict("A code can't be moved inside itself.")
        _get_active(db, project_id, new_parent, "The parent code")
    if new_name.lower() != code.name.lower() or new_parent != code.parent_id:
        _check_name_free(db, project_id, new_parent, new_name, ignore=[code.id])

    logged = {}
    if new_name != code.name:
        logged["old_name"], logged["new_name"] = code.name, new_name
        code.name = new_name
    if new_parent != code.parent_id:
        logged["old_parent"], logged["new_parent"] = str(code.parent_id), str(new_parent)
        code.parent_id = new_parent
    for field in ("definition", "color", "sort_order"):
        if field in changes and changes[field] != getattr(code, field):
            logged[field] = "changed"
            setattr(code, field, changes[field])
    if logged:
        code.revision += 1
        code.updated_at = utcnow()
        log_activity(db, "code.updated", code.name, user_id=user_id, project_id=project_id, code_id=str(code.id), **logged)
    return code


def delete_code(db, project_id, user_id, code_id, revision: int) -> None:
    _lock_codebook(db, project_id)
    code = _get_active(db, project_id, code_id)
    if code.revision != revision:
        raise stale_revision("This code")
    segments = db.scalar(select(func.count()).select_from(Annotation).where(Annotation.code_id == code_id))
    if segments:
        raise conflict(f"This code is used by {segments} segments. Merge it into another code instead.")
    if db.scalar(select(func.count()).select_from(Code).where(Code.parent_id == code_id, Code.merged_into.is_(None))):
        raise conflict("This code has child codes. Move or merge them first.")
    if db.scalar(select(func.count()).select_from(Code).where(Code.merged_into == code_id)):
        raise conflict("Other codes were merged into this one, so it must stay to keep that record.")
    # Merged codes may still name it as their old parent.
    db.execute(update(Code).where(Code.parent_id == code_id).values(parent_id=None))
    log_activity(db, "code.deleted", code.name, user_id=user_id, project_id=project_id, code_id=str(code.id))
    db.execute(delete(Code).where(Code.id == code_id))


def _merge_counts(db, source_id, target_id) -> dict:
    rows = db.execute(
        select(Annotation.start_pos, Annotation.end_pos, Annotation.article_id, Annotation.user_id).where(
            Annotation.code_id == target_id
        )
    ).all()
    existing = {tuple(row) for row in rows}
    moved = duplicates = 0
    coders = set()
    for row in db.execute(
        select(Annotation.start_pos, Annotation.end_pos, Annotation.article_id, Annotation.user_id).where(
            Annotation.code_id == source_id
        )
    ):
        coders.add(row.user_id)
        if tuple(row) in existing:
            duplicates += 1
        else:
            moved += 1
    return {"segments": moved + duplicates, "duplicates": duplicates, "coders": len(coders)}


def _child_name_conflicts(db, project_id, source: Code, target: Code) -> List[str]:
    """Children of the source would join the target's children, so their names must not collide."""
    target_children = {
        name.lower()
        for name in db.scalars(
            select(Code.name).where(Code.project_id == project_id, Code.parent_id == target.id, Code.merged_into.is_(None))
        )
    }
    return sorted(
        name
        for name in db.scalars(
            select(Code.name).where(
                Code.project_id == project_id,
                Code.parent_id == source.id,
                Code.merged_into.is_(None),
                Code.id != target.id,
            )
        )
        if name.lower() in target_children
    )


def merge_preview(db, project_id, source_id, target_id) -> dict:
    source = _get_active(db, project_id, source_id)
    target = _get_active(db, project_id, target_id, "The target code")
    if source.id == target.id:
        raise invalid("A code can't be merged into itself.")
    return {
        **_merge_counts(db, source.id, target.id),
        "name_conflicts": _child_name_conflicts(db, project_id, source, target),
    }


def merge_codes(db, project_id, user_id, source_id, target_id, source_revision: int, target_revision: int) -> Code:
    """Merge one code into another in the caller's transaction, which rolls back whole on any failure."""
    _lock_codebook(db, project_id)
    source = _get_active(db, project_id, source_id)
    target = _get_active(db, project_id, target_id, "The target code")
    if source.id == target.id:
        raise invalid("A code can't be merged into itself.")
    if source.revision != source_revision or target.revision != target_revision:
        raise stale_revision("One of these codes")
    # Blocks segment saves on the source until the merge ends; they then follow merged_into.
    db.execute(select(Code.id).where(Code.id.in_([source.id, target.id])).with_for_update(key_share=True))
    conflicts = _child_name_conflicts(db, project_id, source, target)
    if conflicts:
        raise conflict(f"Both codes have a child named: {', '.join(conflicts)}. Rename or merge those first.")

    # Merging into its own descendant: lift the target out, so it doesn't end up under a merged code.
    if target.id in _descendant_ids(db, project_id, source.id):
        _check_name_free(db, project_id, source.parent_id, target.name, ignore=[source.id, target.id])
        target.parent_id = source.parent_id

    now = utcnow()
    existing = {
        (a.article_id, a.start_pos, a.end_pos, a.user_id): a
        for a in db.scalars(select(Annotation).where(Annotation.code_id == target.id).with_for_update())
    }
    moved, removed = [], []
    for annotation in db.scalars(select(Annotation).where(Annotation.code_id == source.id).with_for_update()):
        match = existing.get((annotation.article_id, annotation.start_pos, annotation.end_pos, annotation.user_id))
        if match is None:
            annotation.code_id = target.id
            annotation.revision += 1
            annotation.updated_at = now
            moved.append(str(annotation.id))
            continue
        if annotation.memo and annotation.memo != match.memo:
            match.memo = f"{match.memo}\n\n{annotation.memo}" if match.memo else annotation.memo
            match.revision += 1
            match.updated_at = now
        removed.append({"id": str(annotation.id), "kept": str(match.id)})
        db.delete(annotation)
    db.flush()

    db.execute(
        update(Code)
        .where(Code.parent_id == source.id, Code.merged_into.is_(None), Code.id != target.id)
        .values(parent_id=target.id, updated_at=now, revision=Code.revision + 1)
    )
    source.merged_into = target.id
    source.revision += 1
    source.updated_at = now
    target.revision += 1
    target.updated_at = now
    db.flush()
    db.expire_all()
    log_activity(
        db,
        "code.merged",
        f"{source.name} into {target.name}",
        user_id=user_id,
        project_id=project_id,
        source_id=str(source.id),
        target_id=str(target.id),
        moved_segments=moved,
        removed_duplicates=removed,
    )
    return target


def resolve_code(db: Session, project_id: uuid.UUID, code_id: uuid.UUID) -> Tuple[Code, Optional[Code]]:
    """
    Return (current code, the merged code that was asked for, if any).

    Takes a shared lock, so a merge in progress finishes first and its result is seen here.
    """
    requested = db.execute(
        select(Code).where(Code.id == code_id, Code.project_id == project_id).with_for_update(read=True)
    ).scalar_one_or_none()
    if requested is None:
        raise not_found("This code")
    db.refresh(requested)
    current, seen = requested, {requested.id}
    while current.merged_into is not None:
        if current.merged_into in seen:
            raise conflict("This code's merge history is inconsistent.")
        seen.add(current.merged_into)
        current = db.execute(select(Code).where(Code.id == current.merged_into).with_for_update(read=True)).scalar_one()
    return current, (requested if current.id != requested.id else None)


def start_codebook(db: Session, project_id: uuid.UUID, user_id: uuid.UUID, mode: str, source_project_id=None) -> None:
    if mode == "empty":
        return
    if mode == "starter":
        parents: Dict[str, Code] = {}
        for entry in STARTER_CODES:
            parent_name, child_name = entry.split(":")
            if parent_name not in parents:
                parents[parent_name] = _insert_code(db, project_id, user_id, parent_name, sort_order=len(parents))
            _insert_code(db, project_id, user_id, child_name, parent_id=parents[parent_name].id)
        return
    if mode == "copy":
        if source_project_id is None or db.get(Project, source_project_id) is None:
            raise invalid("Choose a project to copy the codebook from.")
        pending = active_codes(db, source_project_id)
        new_ids: Dict[Optional[uuid.UUID], Optional[uuid.UUID]] = {None: None}
        # Parents first, however deep the tree is.
        while pending:
            ready = [code for code in pending if code.parent_id in new_ids]
            if not ready:
                raise conflict("The source codebook has an inconsistent tree.")
            for code in ready:
                copy = _insert_code(
                    db, project_id, user_id, code.name, new_ids[code.parent_id], code.definition, code.color, code.sort_order
                )
                new_ids[code.id] = copy.id
            pending = [code for code in pending if code.id not in new_ids]
        return
    raise invalid("Unknown way to start a codebook.")


def code_paths(db: Session, project_id: uuid.UUID) -> Dict[uuid.UUID, str]:
    """Return {code id: 'Parent > Child'} for every code in the project, including merged ones."""
    codes = {code.id: code for code in db.scalars(select(Code).where(Code.project_id == project_id))}
    paths: Dict[uuid.UUID, str] = {}

    def path(code_id: uuid.UUID) -> str:
        if code_id not in paths:
            names, seen, current = [], set(), codes[code_id]
            while current is not None and current.id not in seen:
                seen.add(current.id)
                names.append(current.name)
                current = codes.get(current.parent_id)
            paths[code_id] = " > ".join(reversed(names))
        return paths[code_id]

    for code_id in codes:
        path(code_id)
    return paths
