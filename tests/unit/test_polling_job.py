# tests/unit/test_polling_job.py
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.task import ExtractedTask, SensitivityResult


def _make_task(title: str, visibility: str = "team") -> ExtractedTask:
    return ExtractedTask(
        is_task=True,
        title=title,
        visibility=visibility,  # type: ignore[arg-type]
        confidence_score=0.9,
        source_type="email",
        source_id="msg-1",
    )


async def test_polling_job_skips_when_no_azure_config() -> None:
    """Azure 認証情報が未設定の場合はスキップする"""
    with patch("src.api.main.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(azure_tenant_id="")
        from src.api.main import polling_job
        await polling_job()  # エラーなく終了すればOK


async def test_polling_job_skips_processed_email() -> None:
    """処理済みメールはスキップする"""
    with (
        patch("src.api.main.get_settings") as mock_settings,
        patch("src.api.main.GraphAPIClient") as mock_graph_cls,
        patch("src.api.main.is_processed", return_value=True) as mock_is_processed,
        patch("src.api.main.mark_processed") as mock_mark,
    ):
        settings = MagicMock(
            azure_tenant_id="t",
            azure_client_id="c",
            azure_client_secret="s",
        )
        mock_settings.return_value = settings
        graph_client = AsyncMock()
        graph_client.get_users.return_value = [{"id": "user-1"}]
        graph_client.get_unread_emails.return_value = [{"id": "msg-already"}]
        mock_graph_cls.return_value = graph_client

        from src.api.main import polling_job
        await polling_job()

        mock_is_processed.assert_called_once_with("msg-already")
        mock_mark.assert_not_called()


async def test_polling_job_routes_high_confidence_task() -> None:
    """信頼スコア高タスクは auto_create で起票される"""
    task = _make_task("MTG議事録タスク", visibility="team")
    agent_result = {
        "extracted_tasks": [task],
        "actions": [("MTG議事録タスク", "auto_create")],
        "sensitivity": SensitivityResult(label="pattern_a", reason="ok", detected_keywords=[]),
        "errors": [],
    }

    with (
        patch("src.api.main.get_settings") as mock_settings,
        patch("src.api.main.GraphAPIClient") as mock_graph_cls,
        patch("src.api.main.PlannerConnector") as _,
        patch("src.api.main.TodoConnector"),
        patch("src.api.main.create_llm_provider"),
        patch("src.api.main.build_graph") as mock_build,
        patch("src.api.main.is_processed", return_value=False),
        patch("src.api.main.mark_processed"),
        patch("src.api.main.route_task") as mock_route,
    ):
        settings = MagicMock(
            azure_tenant_id="t",
            azure_client_id="c",
            azure_client_secret="s",
            auto_create_threshold=0.8,
            manual_review_threshold=0.5,
            company_wide_plan_id="plan-all",
        )
        settings.get_dept_plan_map.return_value = {}
        mock_settings.return_value = settings

        graph_client = AsyncMock()
        graph_client.get_users.return_value = [{"id": "user-1"}]
        graph_client.get_unread_emails.return_value = [
            {"id": "msg-1", "subject": "MTG", "body": {"content": "タスクあり"}}
        ]
        mock_graph_cls.return_value = graph_client

        compiled_graph = AsyncMock()
        compiled_graph.ainvoke.return_value = agent_result
        mock_build.return_value = compiled_graph

        from src.api.main import polling_job
        await polling_job()

        mock_route.assert_called_once()
        graph_client.mark_email_read.assert_called_once_with("user-1", "msg-1")
