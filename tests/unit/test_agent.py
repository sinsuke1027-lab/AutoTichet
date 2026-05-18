from unittest.mock import AsyncMock, patch

import pytest

from src.agents.graph import AgentState, build_graph
from src.models.task import ExtractedTask


@pytest.mark.asyncio
async def test_pattern_b_text_skips_external_llm() -> None:
    mock_provider = AsyncMock()
    graph = build_graph(
        llm_provider=mock_provider,
        auto_threshold=0.8,
        review_threshold=0.5,
    )
    with patch(
        "src.agents.nodes._save_tasks_to_postgres",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await graph.ainvoke(
            AgentState(
                source_text="今月の給与について確認してください",
                source_type="email",
                source_id="msg-001",
                sensitivity=None,
                extracted_tasks=[],
                actions=[],
                ticket_ids=[],
                errors=[],
            )
        )
    mock_provider.extract_tasks.assert_not_awaited()
    assert result["sensitivity"].label == "pattern_b"


@pytest.mark.asyncio
async def test_low_confidence_task_is_log_only() -> None:
    low_conf_task = ExtractedTask(
        is_task=True,
        title="何かしてください",
        confidence_score=0.3,
        source_type="email",
        source_id="msg-001",
    )
    mock_provider = AsyncMock()
    mock_provider.extract_tasks = AsyncMock(return_value=[low_conf_task])
    graph = build_graph(
        llm_provider=mock_provider,
        auto_threshold=0.8,
        review_threshold=0.5,
    )
    with patch(
        "src.agents.nodes._save_tasks_to_postgres",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await graph.ainvoke(
            AgentState(
                source_text="何かしてください",
                source_type="email",
                source_id="msg-001",
                sensitivity=None,
                extracted_tasks=[],
                actions=[],
                ticket_ids=[],
                errors=[],
            )
        )
    assert result["actions"] == [("何かしてください", "log_only")]
