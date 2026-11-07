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


class ArticleProject(BaseModel):
    id: uuid.UUID
    name: str
    archived: bool
    role: Literal["lead", "coder"]
    in_project: bool


class ProjectArticlesAdd(BaseModel):
    article_ids: List[str] = Field(min_length=1, max_length=5000)


class ProjectArticlesAdded(BaseModel):
    added: int
    already_present: int


class ProjectArticlesFromSearch(BaseModel):
    q: str = ""
    source: Optional[List[str]] = None
    language: Optional[List[str]] = None


class LibraryCoder(BaseModel):
    user: UserBrief
    status: Optional[Literal["in_progress", "done"]] = None
    segments: int = 0
    stale_segments: int = 0


class LibraryArticle(BaseModel):
    id: str
    in_corpus: bool
    title: str
    source: Optional[str] = None
    source_label: Optional[str] = None
    language: Optional[str] = None
    language_label: Optional[str] = None
    publish_date: Optional[str] = None
    author: Optional[str] = None
    word_count: Optional[int] = None
    my_status: Literal["not_started", "in_progress", "done"]
    coders: List[LibraryCoder]


class LibraryFacet(BaseModel):
    id: str
    label: str
    count: int


class LibraryResponse(BaseModel):
    project_total: int
    total: int
    page: int
    page_size: int
    results: List[LibraryArticle]
    languages: List[LibraryFacet]
    sources: List[LibraryFacet]


class ProjectSearchResult(BaseModel):
    id: str
    title: str
    source_label: str
    language_label: str
    publish_date: str
    word_count: int
    snippet: List[Dict[str, Any]]
    in_project: bool


class ProjectSearchResponse(BaseModel):
    total: int
    in_project_total: int
    page: int
    page_size: int
    results: List[ProjectSearchResult]


class ProgressUpdate(BaseModel):
    status: Literal["in_progress", "done"]


class ProgressOut(BaseModel):
    status: Literal["not_started", "in_progress", "done"]


class PresenceOut(BaseModel):
    others: List[UserBrief]


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
