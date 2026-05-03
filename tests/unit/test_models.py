import pytest

from src.models.config import Settings
from src.models.task import ExtractedTask, SensitivityResult


def test_extracted_task_defaults() -> None:
    task = ExtractedTask(
        is_task=True,
        title="資料を作成する",
        confidence_score=0.9,
        source_type="email",
        source_id="msg-001",
    )
    assert task.visibility == "team"
    assert task.priority == "medium"
    assert task.category == "その他"
    assert task.assignee_user_id is None


def test_extracted_task_rejects_invalid_score() -> None:
    with pytest.raises(ValueError):
        ExtractedTask(
            is_task=True,
            title="test",
            confidence_score=1.5,
            source_type="email",
            source_id="msg-001",
        )


def test_sensitivity_result_pattern_a() -> None:
    result = SensitivityResult(
        label="pattern_a",
        reason="一般業務連絡",
        detected_keywords=[],
    )
    assert result.label == "pattern_a"


def test_sensitivity_result_pattern_b() -> None:
    result = SensitivityResult(
        label="pattern_b",
        reason="給与情報を含む",
        detected_keywords=["給与"],
    )
    assert result.detected_keywords == ["給与"]


def test_dept_plan_map_defaults_to_empty() -> None:
    s = Settings()
    assert s.get_dept_plan_map() == {}


def test_dept_plan_map_parsed_from_json() -> None:
    s = Settings(dept_plan_map='{"g1": "p1", "g2": "p2"}')
    assert s.get_dept_plan_map() == {"g1": "p1", "g2": "p2"}
