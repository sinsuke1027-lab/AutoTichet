from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedTask(BaseModel):
    """Outlook・Teams・チャットから抽出されたタスクモデル"""

    is_task: bool
    title: str = Field(min_length=1, max_length=200)
    assignee_user_id: str | None = None
    assignee_name: str | None = None
    department_id: str | None = None
    deadline: date | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    category: Literal["HR", "IT", "総務", "その他"] = "その他"
    visibility: Literal["private", "team", "all"] = "team"
    confidence_score: float = Field(ge=0.0, le=1.0)
    source_type: Literal["email", "meeting", "chat", "onenote", "teams_bot"]
    source_id: str


class SensitivityResult(BaseModel):
    """機密度分類結果モデル"""

    label: Literal["pattern_a", "pattern_b"]
    reason: str
    detected_keywords: list[str]
