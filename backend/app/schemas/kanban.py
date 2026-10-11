from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

Priority = Literal["low", "medium", "high"]


class UserRegister(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    role: str = "developer"


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class ProjectCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    description: Optional[str] = None


class ProjectResponse(ProjectCreate):
    id: int


class ColumnCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    wip_limit: int = Field(default=3, ge=1, le=1000)
    order: Optional[int] = Field(default=None, ge=1, le=100000)
    project_id: Optional[int] = None


class ColumnUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]] = None
    wip_limit: Optional[int] = Field(default=None, ge=1, le=1000)
    order: Optional[int] = Field(default=None, ge=1, le=100000)


class ColumnResponse(BaseModel):
    id: int
    project_id: int
    title: str
    wip_limit: int
    order: int


class TaskCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    column_id: int
    project_id: Optional[int] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    priority: Priority = "medium"
    deadline: Optional[str] = None
    tags: Optional[str] = None
    attachment_url: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[Priority] = None
    deadline: Optional[str] = None
    tags: Optional[str] = None
    attachment_url: Optional[str] = None


class TaskResponse(BaseModel):
    id: int
    title: str
    column_id: int
    project_id: int
    description: Optional[str] = ""
    assignee: Optional[str] = "Не назначен"
    priority: Optional[str] = "medium"
    deadline: Optional[str] = ""
    tags: Optional[str] = ""
    attachment_url: Optional[str] = ""


class CommentCreate(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    author: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CommentResponse(BaseModel):
    author: str
    text: str
    timestamp: str


class TaskHistoryResponse(BaseModel):
    timestamp: str
    action: str
