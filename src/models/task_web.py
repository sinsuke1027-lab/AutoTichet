import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskVisibility(str, Enum):
    PRIVATE = "private"
    TEAM = "team"
    ALL = "all"


# --- Project ---


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    status: str = "active"
    created_by: str


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Task ---


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    priority: str = "medium"
    assignee_id: str | None = None
    due_date: date | None = None
    start_date: date | None = None
    visibility: str = "team"
    project_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    source_type: str | None = None
    source_id: str | None = None
    confidence_score: float | None = None
    route: str | None = None
    created_by: str
    tags: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: str | None = None
    assignee_id: str | None = None
    due_date: date | None = None
    start_date: date | None = None
    visibility: str | None = None
    project_id: uuid.UUID | None = None
    tags: list[str] | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    status: TaskStatus
    priority: str
    assignee_id: str | None = None
    due_date: date | None = None
    start_date: date | None = None
    visibility: str
    source_type: str | None = None
    confidence_score: float | None = None
    route: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


# --- Comment ---


class CommentCreate(BaseModel):
    content: str
    mentions: list[str] = Field(default_factory=list)
    sharepoint_links: list[str] = Field(default_factory=list)
    author_id: str


class CommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    author_id: str
    content: str
    mentions: list[str]
    sharepoint_links: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- WorkHour ---


class WorkHourCreate(BaseModel):
    user_id: str
    estimated_hours: float | None = None
    actual_hours: float | None = None
    notes: str | None = None


class WorkHourResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: str
    estimated_hours: float | None = None
    actual_hours: float | None = None
    notes: str | None = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


# --- Dashboard ---


class DashboardSummary(BaseModel):
    total_tasks: int
    not_started: int
    in_progress: int
    completed: int
    overdue: int
    completion_rate: float


class WorkloadItem(BaseModel):
    user_id: str
    display_name: str
    estimated_hours: float
    capacity_hours: float
    overload: bool
