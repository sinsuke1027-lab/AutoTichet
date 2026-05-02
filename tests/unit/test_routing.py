from unittest.mock import AsyncMock

import pytest

from src.models.task import ExtractedTask
from src.services.routing import route_task


def _make_task(
    visibility: str, assignee_user_id: str | None = "user-001"
) -> ExtractedTask:
    return ExtractedTask(
        is_task=True,
        title="テストタスク",
        confidence_score=0.9,
        source_type="email",
        source_id="msg-001",
        visibility=visibility,  # type: ignore[arg-type]
        assignee_user_id=assignee_user_id,
        department_id="group-sales",
    )


@pytest.mark.asyncio
async def test_private_task_goes_to_todo() -> None:
    todo_mock = AsyncMock()
    planner_mock = AsyncMock()
    await route_task(
        task=_make_task("private"),
        todo_connector=todo_mock,
        planner_connector=planner_mock,
        company_plan_id="plan-all",
        dept_plan_map={"group-sales": "plan-sales"},
    )
    todo_mock.create_task.assert_awaited_once()
    planner_mock.create_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_team_task_goes_to_dept_planner() -> None:
    todo_mock = AsyncMock()
    planner_mock = AsyncMock()
    await route_task(
        task=_make_task("team"),
        todo_connector=todo_mock,
        planner_connector=planner_mock,
        company_plan_id="plan-all",
        dept_plan_map={"group-sales": "plan-sales"},
    )
    planner_mock.create_task.assert_awaited_once_with(
        task=_make_task("team"), plan_id="plan-sales"
    )


@pytest.mark.asyncio
async def test_all_task_goes_to_company_planner() -> None:
    todo_mock = AsyncMock()
    planner_mock = AsyncMock()
    await route_task(
        task=_make_task("all"),
        todo_connector=todo_mock,
        planner_connector=planner_mock,
        company_plan_id="plan-all",
        dept_plan_map={"group-sales": "plan-sales"},
    )
    planner_mock.create_task.assert_awaited_once_with(
        task=_make_task("all"), plan_id="plan-all"
    )
