"""Request dependencies: the current user and their access to a project."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from backend.app.database import get_db
from backend.app.errors import conflict, forbidden, not_found
from backend.app.models import Project, ProjectMember, Session, User
from backend.app.security import hash_token

SESSION_COOKIE = "didi_session"
Db = Annotated[DbSession, Depends(get_db)]


def get_current_user(db: Db, didi_session: Annotated[Optional[str], Cookie()] = None) -> User:
    """The one place that decides who is making a request. Other login methods would plug in here."""
    unauthenticated = HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in.")
    if not didi_session:
        raise unauthenticated
    session = db.get(Session, hash_token(didi_session))
    if session is None or session.expires_at <= datetime.now(timezone.utc):
        raise unauthenticated
    user = db.get(User, session.user_id)
    if user is None or not user.active:
        raise unauthenticated
    return user


def get_optional_user(db: Db, didi_session: Annotated[Optional[str], Cookie()] = None) -> Optional[User]:
    if not didi_session:
        return None
    session = db.get(Session, hash_token(didi_session))
    if session is None or session.expires_at <= datetime.now(timezone.utc):
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.active:
        return None
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise forbidden()
    return user


AdminUser = Annotated[User, Depends(require_admin)]


@dataclass
class ProjectAccess:
    project: Project
    user: User
    role: Optional[str]  # None for an admin who isn't a member

    @property
    def is_member(self) -> bool:
        return self.role is not None

    @property
    def is_lead(self) -> bool:
        return self.role == "lead"


def get_project_access(project_id: uuid.UUID, user: CurrentUser, db: Db) -> ProjectAccess:
    """Load a project the user may see. Others get 404, which doesn't reveal that it exists."""
    project = db.get(Project, project_id)
    if project is None:
        raise not_found("This project")
    membership = db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
    )
    if membership is None and not user.is_admin:
        raise not_found("This project")
    return ProjectAccess(project=project, user=user, role=membership.role if membership else None)


ReadAccess = Annotated[ProjectAccess, Depends(get_project_access)]


def _writable(access: ProjectAccess) -> ProjectAccess:
    if access.project.archived:
        raise conflict("This project is archived, so it can't be changed.")
    return access


def require_member(access: ReadAccess) -> ProjectAccess:
    """Coding work: only members, including admins, who must join a project to code in it."""
    if not access.is_member:
        raise forbidden("Only project members can do this.")
    return _writable(access)


def require_codebook_lead(access: ReadAccess) -> ProjectAccess:
    """Editing a codebook is research work, so being an admin isn't enough."""
    if not access.is_lead:
        raise forbidden("Only a project lead can change existing codes.")
    return _writable(access)


def require_project_manager(access: ReadAccess) -> ProjectAccess:
    if not (access.is_lead or access.user.is_admin):
        raise forbidden("Only a project lead or an admin can do this.")
    return _writable(access)


MemberAccess = Annotated[ProjectAccess, Depends(require_member)]
CodebookLeadAccess = Annotated[ProjectAccess, Depends(require_codebook_lead)]
ManagerAccess = Annotated[ProjectAccess, Depends(require_project_manager)]
