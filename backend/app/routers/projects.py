import uuid
from typing import List

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.corpus import get_corpus
from backend.app.deps import AdminUser, CurrentUser, Db, ManagerAccess, ProjectAccess, ReadAccess
from backend.app.errors import conflict, forbidden, invalid, not_found, stale_revision
from backend.app.models import ActivityLog, Annotation, Code, Project, ProjectArticle, ProjectMember, User
from backend.app.schemas_work import (
    ActivityOut,
    MemberCreate,
    MemberOut,
    MemberUpdate,
    ProjectArticlesAdd,
    ProjectArticlesAdded,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    UserBrief,
)
from backend.app.services import codebook, exports, library
from backend.app.services.activity import log_activity

router = APIRouter(prefix="/api/projects")


def _count(db: Session, model, project_id: uuid.UUID, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(model).where(model.project_id == project_id, *conditions))


def _project_out(db: Session, project: Project, user: User, role) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        archived=project.archived,
        revision=project.revision,
        role=role,
        can_manage=role == "lead" or user.is_admin,
        can_edit_codebook=role == "lead",
        member_count=_count(db, ProjectMember, project.id),
        code_count=_count(db, Code, project.id, Code.merged_into.is_(None)),
        article_count=_count(db, ProjectArticle, project.id),
        segment_count=_count(db, Annotation, project.id),
    )


def _clean_project_name(db: Session, name: str, ignore: uuid.UUID = None) -> str:
    name = (name or "").strip()
    if not name:
        raise invalid("A project needs a name.")
    existing = db.scalar(select(Project).where(func.lower(Project.name) == name.lower()))
    if existing and existing.id != ignore:
        raise conflict(f"A project named '{name}' already exists.")
    return name


@router.get("", response_model=List[ProjectOut])
def list_projects(user: CurrentUser, db: Db):
    roles = dict(db.execute(select(ProjectMember.project_id, ProjectMember.role).where(ProjectMember.user_id == user.id)).all())
    query = select(Project).order_by(Project.archived, func.lower(Project.name))
    if not user.is_admin:
        query = query.where(Project.id.in_(roles))
    return [_project_out(db, project, user, roles.get(project.id)) for project in db.scalars(query)]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, admin: AdminUser, db: Db):
    name = _clean_project_name(db, body.name)
    lead_id = body.lead_user_id or admin.id
    lead = db.get(User, lead_id)
    if lead is None or not lead.active:
        raise invalid("Choose an active user as the project lead.")
    project = Project(name=name, description=body.description.strip(), created_by=admin.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=lead_id, role="lead"))
    codebook.start_codebook(db, project.id, admin.id, body.codebook.mode, body.codebook.source_project_id)
    log_activity(db, "project.created", name, user_id=admin.id, project_id=project.id, codebook=body.codebook.mode)
    db.commit()
    return _project_out(db, project, admin, "lead" if lead_id == admin.id else None)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(access: ReadAccess, db: Db):
    return _project_out(db, access.project, access.user, access.role)


def _manager_ignoring_archive(access: ProjectAccess) -> None:
    if not (access.is_lead or access.user.is_admin):
        raise forbidden("Only a project lead or an admin can do this.")


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(body: ProjectUpdate, access: ReadAccess, db: Db):
    # Separate from ManagerAccess, because an archived project must still be possible to restore.
    _manager_ignoring_archive(access)
    project = access.project
    if project.revision != body.revision:
        raise stale_revision("This project")
    changes = body.model_dump(exclude_unset=True, exclude={"revision"})
    if project.archived and set(changes) - {"archived"}:
        raise conflict("This project is archived, so it can't be changed.")
    logged = {}
    if "name" in changes:
        new_name = _clean_project_name(db, changes["name"], ignore=project.id)
        if new_name != project.name:
            logged["old_name"], project.name = project.name, new_name
    if "description" in changes and changes["description"].strip() != project.description:
        project.description = changes["description"].strip()
        logged["description"] = "changed"
    if "archived" in changes and changes["archived"] != project.archived:
        project.archived = changes["archived"]
        logged["archived"] = project.archived
    if logged:
        project.revision += 1
        log_activity(db, "project.updated", project.name, user_id=access.user.id, project_id=project.id, **logged)
    db.commit()
    return _project_out(db, project, access.user, access.role)


@router.get("/{project_id}/members", response_model=List[MemberOut])
def list_members(access: ReadAccess, db: Db):
    rows = db.scalars(select(ProjectMember).where(ProjectMember.project_id == access.project.id))
    members = sorted(rows, key=lambda member: member.user.display_name.lower())
    return [MemberOut(user=UserBrief.model_validate(m.user), role=m.role, active=m.user.active) for m in members]


def _lead_count(db: Session, project_id: uuid.UUID) -> int:
    # Locks the rows, so two leads can't remove each other at the same moment.
    leads = db.scalars(
        select(ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id, ProjectMember.role == "lead")
        .with_for_update()
    ).all()
    return len(leads)


@router.post("/{project_id}/members", response_model=MemberOut, status_code=201)
def add_member(body: MemberCreate, access: ManagerAccess, db: Db):
    user = db.get(User, body.user_id)
    if user is None or not user.active:
        raise invalid("Choose an active user.")
    if db.get(ProjectMember, (access.project.id, user.id)):
        raise conflict(f"{user.display_name} is already a member of this project.")
    db.add(ProjectMember(project_id=access.project.id, user_id=user.id, role=body.role))
    log_activity(db, "member.added", user.username, user_id=access.user.id, project_id=access.project.id, role=body.role)
    db.commit()
    return MemberOut(user=UserBrief.model_validate(user), role=body.role, active=user.active)


def _get_member(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember:
    member = db.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise not_found("This member")
    return member


@router.patch("/{project_id}/members/{user_id}", response_model=MemberOut)
def update_member(user_id: uuid.UUID, body: MemberUpdate, access: ManagerAccess, db: Db):
    member = _get_member(db, access.project.id, user_id)
    if member.role == "lead" and body.role != "lead" and _lead_count(db, access.project.id) <= 1:
        raise conflict("A project needs at least one lead. Make someone else a lead first.")
    if member.role != body.role:
        member.role = body.role
        log_activity(db, "member.role_changed", member.user.username, user_id=access.user.id, project_id=access.project.id, role=body.role)
    db.commit()
    return MemberOut(user=UserBrief.model_validate(member.user), role=member.role, active=member.user.active)


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_member(user_id: uuid.UUID, access: ManagerAccess, db: Db) -> None:
    member = _get_member(db, access.project.id, user_id)
    if member.role == "lead" and _lead_count(db, access.project.id) <= 1:
        raise conflict("A project needs at least one lead. Make someone else a lead first.")
    log_activity(db, "member.removed", member.user.username, user_id=access.user.id, project_id=access.project.id)
    db.delete(member)
    db.commit()


@router.post("/{project_id}/articles", response_model=ProjectArticlesAdded)
def add_articles(body: ProjectArticlesAdd, access: ManagerAccess, db: Db):
    requested = sorted(set(body.article_ids))
    missing = set(requested) - set(get_corpus().get_article_metadata(requested))
    if missing:
        raise invalid(f"{len(missing)} of these articles are not in the corpus.")
    added = library.add_articles(db, access.project.id, access.user.id, requested)
    db.commit()
    return ProjectArticlesAdded(added=added, already_present=len(requested) - added)


@router.get("/{project_id}/activity", response_model=List[ActivityOut])
def list_activity(access: ReadAccess, db: Db, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    return db.scalars(
        select(ActivityLog)
        .where(ActivityLog.project_id == access.project.id)
        .order_by(ActivityLog.occurred_at.desc(), ActivityLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()


def _csv_response(content: bytes, filename: str) -> Response:
    return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{project_id}/exports/annotations.csv")
def export_annotations(access: ReadAccess, db: Db) -> Response:
    content = exports.annotations_csv(db, get_corpus(), access.project.id, access.project.name)
    return _csv_response(content, "didi_annotations.csv")


@router.get("/{project_id}/exports/codes.csv")
def export_codes(access: ReadAccess, db: Db) -> Response:
    return _csv_response(exports.codes_csv(db, access.project.id), "didi_codes.csv")


@router.get("/{project_id}/exports/code-measures.csv")
def export_code_measures(access: ReadAccess, db: Db) -> Response:
    content = exports.code_measures_csv(db, access.project)
    return _csv_response(content, f"{access.project.name}_code_measures.csv")


@router.get("/{project_id}/exports/passage-measures.csv")
def export_passage_measures(access: ReadAccess, db: Db) -> Response:
    content = exports.passage_measures_csv(db, get_corpus(), access.project)
    return _csv_response(content, f"{access.project.name}_passage_measures.csv")


@router.get("/{project_id}/exports/comparison-grid.csv")
def export_comparison_grid(
    access: ReadAccess,
    db: Db,
    row_by: str = "language",
    measure: str = "count",
) -> Response:
    content = exports.comparison_grid_csv(db, access.project, row_by=row_by, measure=measure)
    return _csv_response(content, f"{access.project.name}_comparison_grid_{row_by}_{measure}.csv")


@router.get("/{project_id}/exports/manifest.json")
def export_manifest_json(access: ReadAccess, db: Db) -> Response:
    import json
    data = exports.reproducibility_manifest(db, get_corpus(), access.project)
    content = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    return Response(
        content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{access.project.name}_manifest.json"'},
    )


@router.get("/{project_id}/exports/manifest.md")
def export_manifest_markdown(access: ReadAccess, db: Db) -> Response:
    report = exports.reproducibility_report_markdown(db, get_corpus(), access.project)
    return Response(
        report.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{access.project.name}_reproducibility_report.md"'},
    )


@router.get("/{project_id}/comparison-grid")
def project_comparison_grid(
    access: ReadAccess,
    db: Db,
    row_by: str = "language",
    measure: str = "count",
):
    """Retrieve Stage 4 cross-tabulation comparison grid."""
    from backend.app.services.measures import get_project_comparison_grid
    return get_project_comparison_grid(db, access.project, row_by=row_by, measure=measure)


@router.get("/{project_id}/analysis")
def project_analysis(access: ReadAccess, db: Db):
    """Retrieve mixed-methods linguistic measures and stats for all codes in this project."""
    from backend.app.services.measures import get_project_analysis_summary
    return get_project_analysis_summary(db, access.project)


@router.get("/{project_id}/corpus-comparison")
def project_corpus_comparison(access: ReadAccess, db: Db):
    """Retrieve quantitative linguistic comparison between project texts and regional corpus baseline."""
    from backend.app.services.measures import get_project_corpus_comparison
    return get_project_corpus_comparison(db, access.project)
