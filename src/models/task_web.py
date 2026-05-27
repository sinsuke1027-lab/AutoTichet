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
    section_id: uuid.UUID | None = None
    source_type: str | None = None
    source_id: str | None = None
    confidence_score: float | None = None
    route: str | None = None
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
    section_id: uuid.UUID | None = None
    tags: list[str] | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None = None
    parent_task_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
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
    completed_at: datetime | None = None
    order_index: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    sub_assignees: list[str] = Field(default_factory=list)
    subtask_count: int = 0
    subtask_done_count: int = 0

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


# --- Comment ---


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    mentions: list[str] = Field(default_factory=list)
    sharepoint_links: list[str] = Field(default_factory=list)


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


# --- Dependency ---


class DependencyCreate(BaseModel):
    depends_on_task_id: uuid.UUID


class DependencyResponse(BaseModel):
    id: uuid.UUID
    depends_on_task_id: uuid.UUID

    model_config = {"from_attributes": True}


# --- Section ---


class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    order_index: int = 0


class SectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    order_index: int | None = None


class SectionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SectionReorderItem(BaseModel):
    id: uuid.UUID
    order_index: int


# --- TaskAssignee ---


class TaskAssigneeCreate(BaseModel):
    user_id: str
    role: str = "sub"


class TaskAssigneeResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: str
    role: str

    model_config = {"from_attributes": True}


# --- Import ---


class ImportPreviewResponse(BaseModel):
    file_name: str
    projects: list[dict]
    sections: list[dict]
    tasks: dict
    warnings: list[str]


class ImportResult(BaseModel):
    created_tasks: int
    created_sections: int
    skipped_duplicates: int
    errors: list[str]


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


class TodayTaskItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    priority: str
    assignee_id: str | None = None


class OverdueTaskItem(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    due_date: str | None = None
    assignee_id: str | None = None


class TrendPoint(BaseModel):
    date: str
    completed: int


# --- User ---


class MeResponse(BaseModel):
    user_id: str
    name: str
    email: str
    roles: list[str]


class UserResponse(BaseModel):
    user_id: str
    display_name: str
    email: str | None = None
    role: str
    capacity_hours_per_day: float

    model_config = {"from_attributes": True}


# --- Reschedule ---


class RescheduleRequest(BaseModel):
    new_start_date: date | None = None
    new_due_date: date


class RescheduleResponse(BaseModel):
    updated_tasks: list[TaskResponse]


# --- Admin Tag ---


class TagRenameRequest(BaseModel):
    new_name: str = Field(min_length=1, max_length=50)


# --- Admin User ---


class AdminUserCreate(BaseModel):
    user_id: str
    display_name: str
    email: str | None = None
    role: str = "member"
    department_tags: list[str] = Field(default_factory=list)
    capacity_hours_per_day: float = 8.0


class AdminUserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    department_tags: list[str] | None = None
    capacity_hours_per_day: float | None = None


class AdminUserResponse(BaseModel):
    model_config = {"from_attributes": True}

    user_id: str
    display_name: str
    email: str | None = None
    role: str
    department_tags: list[str]
    capacity_hours_per_day: float


# --- Similar Task ---


class SimilarTaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    score: float


# --- Daily Workload ---


class DailyWorkloadItem(BaseModel):
    date: str  # "YYYY-MM-DD"
    total_hours: float  # due_date がその日のタスクの estimated_hours 合計
    capacity_hours: (
        float  # ロール別 capacity（member=個人、leader=部署平均、manager/admin=全体平均）
    )
    overload: bool  # total_hours > capacity_hours
    task_count: int


# --- AI サブタスク生成 ---


class GenerateSubtasksResponse(BaseModel):
    suggested_titles: list[str]


# --- テンプレート機能 (F-15) ---


class TemplateSubtask(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"
    due_date_offset_days: int = 0


class TemplateData(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"
    visibility: str = "team"
    tags: list[str] = Field(default_factory=list)
    estimated_hours: float | None = None
    due_date_offset_days: int = 0
    subtasks: list[TemplateSubtask] = Field(default_factory=list)


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    template_data: TemplateData


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    template_data: TemplateData | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    template_data: TemplateData
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateApplyRequest(BaseModel):
    base_date: date | None = None
    project_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    assignee_id: str | None = None


class TemplateApplyResponse(BaseModel):
    task_id: uuid.UUID
    subtask_ids: list[uuid.UUID]


# --- 過去実績参照 (F-27) ---


class PastPerformanceSimilarTask(BaseModel):
    id: uuid.UUID
    title: str
    actual_hours: float


class PastPerformanceResponse(BaseModel):
    avg_actual_hours: float | None  # None = 実績データなし
    min_actual_hours: float | None
    max_actual_hours: float | None
    task_count: int
    similar_tasks: list[PastPerformanceSimilarTask]
