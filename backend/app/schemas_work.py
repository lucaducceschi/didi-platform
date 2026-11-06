"""API models for accounts, projects, codebooks and annotations."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserOut(OrmModel):
    id: uuid.UUID
    username: str
    display_name: str
    is_admin: bool
    active: bool


class UserBrief(OrmModel):
    id: uuid.UUID
    username: str
    display_name: str


class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str
    is_admin: bool = False


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    active: Optional[bool] = None
    is_admin: Optional[bool] = None


class CodebookStart(BaseModel):
    mode: Literal["empty", "starter", "copy"] = "empty"
    source_project_id: Optional[uuid.UUID] = None


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    lead_user_id: Optional[uuid.UUID] = None
    codebook: CodebookStart = CodebookStart()


class ProjectUpdate(BaseModel):
    revision: int
    name: Optional[str] = None
    description: Optional[str] = None
    archived: Optional[bool] = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    archived: bool
    revision: int
    role: Optional[str]
    can_manage: bool
    can_edit_codebook: bool
    member_count: int
    code_count: int
    article_count: int
    segment_count: int


class MemberCreate(BaseModel):
    user_id: uuid.UUID
    role: Literal["lead", "coder"] = "coder"


class MemberUpdate(BaseModel):
    role: Literal["lead", "coder"]


class MemberOut(BaseModel):
    user: UserBrief
    role: str
    active: bool


class CodeCreate(BaseModel):
    name: str
    parent_id: Optional[uuid.UUID] = None
    definition: str = ""
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class CodeUpdate(BaseModel):
    revision: int
    name: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    definition: Optional[str] = None
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: Optional[int] = None


class CodeOut(OrmModel):
    id: uuid.UUID
    name: str
    parent_id: Optional[uuid.UUID]
    definition: str
    color: str
    sort_order: int
    revision: int
    segment_count: int = 0
    coder_count: int = 0


class MergeRequest(BaseModel):
    target_id: uuid.UUID
    source_revision: int
    target_revision: int


class MergePreview(BaseModel):
    segments: int
    duplicates: int
    coders: int
    name_conflicts: List[str]


class ProjectArticlesAdd(BaseModel):
    article_ids: List[str] = Field(min_length=1, max_length=5000)


class ProjectArticlesAdded(BaseModel):
    added: int
    already_present: int


class AnnotationCreate(BaseModel):
    start: int
    end: int
    code_id: uuid.UUID
    memo: str = ""


class AnnotationUpdate(BaseModel):
    revision: int
    code_id: Optional[uuid.UUID] = None
    memo: Optional[str] = None


class AnnotationOut(OrmModel):
    id: uuid.UUID
    article_id: str
    code_id: uuid.UUID
    user: UserBrief
    start_pos: int
    end_pos: int
    quote: str
    memo: str
    status: str
    revision: int
    created_at: datetime
    updated_at: datetime
    created: Optional[bool] = None
    merged_from: Optional[str] = None


class ActivityOut(OrmModel):
    id: int
    occurred_at: datetime
    user: Optional[UserBrief]
    action: str
    target: str
    details: Dict[str, Any]
