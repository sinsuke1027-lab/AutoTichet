from typing import Literal

from src.models.task import ExtractedTask

Action = Literal["auto_create", "request_approval", "log_only"]


def decide_action(
    task: ExtractedTask,
    auto_threshold: float,
    review_threshold: float,
) -> Action:
    if task.confidence_score >= auto_threshold:
        return "auto_create"
    if task.confidence_score >= review_threshold:
        return "request_approval"
    return "log_only"
