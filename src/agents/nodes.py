from typing import Any

from src.models.task import ExtractedTask
from src.providers.base import LLMProvider
from src.services.approval import decide_action
from src.services.classifier import classify_sensitivity
from src.services.routing import _save_tasks_to_postgres


async def node_classify(state: dict[str, Any]) -> dict[str, Any]:
    result = classify_sensitivity(state["source_text"])
    return {"sensitivity": result}


async def node_extract(state: dict[str, Any], llm_provider: LLMProvider) -> dict[str, Any]:
    if state["sensitivity"].label == "pattern_b":
        return {"extracted_tasks": []}
    tasks = await llm_provider.extract_tasks(state["source_text"], state["source_type"])
    for t in tasks:
        t.source_id = state["source_id"]
    return {"extracted_tasks": tasks}


async def node_route(
    state: dict[str, Any],
    auto_threshold: float,
    review_threshold: float,
) -> dict[str, Any]:
    actions = [
        (t.title, decide_action(t, auto_threshold, review_threshold))
        for t in state["extracted_tasks"]
    ]
    return {"actions": actions}


async def node_auto_create(state: dict[str, Any]) -> dict[str, Any]:
    """信頼スコアが閾値以上のタスクを PostgreSQL へ自動起票する

    ``route`` ノードが生成した ``actions`` リストから ``auto_create`` に分類された
    タスクのみを抽出し、:func:`src.services.routing._save_tasks_to_postgres` で
    保存する。

    Args:
        state: エージェント状態辞書

    Returns:
        ``ticket_ids`` キーに保存された UUID 文字列のリストを追加した差分辞書
    """
    actions: list[tuple[str, str]] = state.get("actions", [])
    auto_titles: set[str] = {title for title, action in actions if action == "auto_create"}

    extracted_tasks: list[ExtractedTask] = state.get("extracted_tasks", [])
    tasks_to_save: list[dict[str, Any]] = [
        {
            "title": t.title,
            "description": None,
            "assignee_id": t.assignee_user_id,
            "due_date": t.deadline,
            "visibility": t.visibility,
        }
        for t in extracted_tasks
        if t.title in auto_titles
    ]

    if not tasks_to_save:
        return {"ticket_ids": []}

    # タスクごとに confidence_score が異なる可能性があるため、平均値を記録する
    auto_tasks = [t for t in extracted_tasks if t.title in auto_titles]
    avg_confidence = (
        sum(t.confidence_score for t in auto_tasks) / len(auto_tasks) if auto_tasks else 0.0
    )

    saved_ids = await _save_tasks_to_postgres(
        tasks=tasks_to_save,
        source_type=state.get("source_type", "unknown"),
        source_id=state.get("source_id", ""),
        confidence_score=avg_confidence,
        route="auto_create",
    )
    return {"ticket_ids": saved_ids}
