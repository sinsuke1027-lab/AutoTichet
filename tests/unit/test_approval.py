from src.models.task import ExtractedTask
from src.services.approval import decide_action


def _make_task(score: float) -> ExtractedTask:
    return ExtractedTask(
        is_task=True,
        title="テストタスク",
        confidence_score=score,
        source_type="email",
        source_id="msg-001",
    )


def test_high_score_is_auto_create() -> None:
    assert decide_action(_make_task(0.9), auto_threshold=0.8, review_threshold=0.5) == "auto_create"


def test_boundary_auto_create() -> None:
    assert decide_action(_make_task(0.8), auto_threshold=0.8, review_threshold=0.5) == "auto_create"


def test_mid_score_is_request_approval() -> None:
    assert decide_action(_make_task(0.65), auto_threshold=0.8, review_threshold=0.5) == "request_approval"


def test_boundary_review() -> None:
    assert decide_action(_make_task(0.5), auto_threshold=0.8, review_threshold=0.5) == "request_approval"


def test_low_score_is_log_only() -> None:
    assert decide_action(_make_task(0.3), auto_threshold=0.8, review_threshold=0.5) == "log_only"
