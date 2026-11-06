"""Database models. The schema itself is defined by the Alembic migrations; see docs/coding/SCHEMA.md."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(default=False)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    failures: Mapped[int] = mapped_column(Integer)
    first_failure_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ProjectMember(Base):
    __tablename__ = "project_members"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)
    user: Mapped[User] = relationship(lazy="selectin")


class ProjectArticle(Base):
    __tablename__ = "project_articles"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    article_id: Mapped[str] = mapped_column(Text, primary_key=True)
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)


class ArticleProgress(Base):
    __tablename__ = "article_progress"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    article_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    status: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)


class Code(Base):
    __tablename__ = "codes"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("codes.id"))
    definition: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    merged_into: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("codes.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)


class Annotation(Base):
    __tablename__ = "annotations"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    article_id: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    code_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("codes.id"))
    start_pos: Mapped[int] = mapped_column(Integer)
    end_pos: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)
    text_sha256: Mapped[str] = mapped_column(Text)
    memo: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="active")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)
    user: Mapped[User] = relationship(lazy="selectin")


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utcnow)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id"))
    action: Mapped[str] = mapped_column(Text)
    target: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    user: Mapped[Optional[User]] = relationship(lazy="selectin")
