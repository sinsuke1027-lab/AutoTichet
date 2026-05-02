from typing import Any

from src.providers.base import LLMProvider
from src.services.approval import decide_action
from src.services.classifier import classify_sensitivity


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
