import uuid
from typing import List

from fastapi import APIRouter
from sqlalchemy import func, select

from backend.app.deps import AdminUser, CurrentUser, Db
from backend.app.errors import forbidden, not_found
from backend.app.models import ProjectMember, User
from backend.app.schemas_work import UserBrief, UserCreate, UserOut, UserUpdate
from backend.app.services import accounts

router = APIRouter(prefix="/api/users")


@router.get("", response_model=List[UserOut])
def list_users(_: AdminUser, db: Db):
    return db.scalars(select(User).order_by(func.lower(User.display_name)))


@router.get("/directory", response_model=List[UserBrief])
def user_directory(user: CurrentUser, db: Db):
    """Active users, for project leads choosing members."""
    is_lead = db.scalar(
        select(func.count()).select_from(ProjectMember).where(ProjectMember.user_id == user.id, ProjectMember.role == "lead")
    )
    if not (user.is_admin or is_lead):
        raise forbidden()
    return db.scalars(select(User).where(User.active).order_by(func.lower(User.display_name)))


@router.post("", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, admin: AdminUser, db: Db):
    user = accounts.create_user(db, body.username, body.display_name, body.password, body.is_admin, created_by=admin.id)
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, body: UserUpdate, admin: AdminUser, db: Db):
    target = db.get(User, user_id)
    if target is None:
        raise not_found("This user")
    accounts.update_user(db, target, admin, body.model_dump(exclude_unset=True))
    db.commit()
    return target
