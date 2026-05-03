from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from src.agents.graph import AgentState, build_graph
from src.api.routers import health, tasks
from src.connectors.graph_api import GraphAPIClient
from src.connectors.planner import PlannerConnector
from src.connectors.todo import TodoConnector
from src.models.config import get_settings
from src.providers.factory import create_llm_provider
from src.services.routing import route_task
from src.services.state import init_db, is_processed, mark_processed

scheduler = AsyncIOScheduler()


async def polling_job() -> None:
    """Outlook メールをポーリングしてタスクを自動起票する"""
    settings = get_settings()
    if not settings.azure_tenant_id:
        return  # Graph API 未設定はスキップ

    graph_client = GraphAPIClient(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )
    planner = PlannerConnector(graph_client)
    todo = TodoConnector(graph_client)

    users = await graph_client.get_users()

    # LLM・graph は未読メールが存在する場合のみ遅延初期化
    graph: Any = None

    for user in users:
        uid = str(user["id"])
        emails = await graph_client.get_unread_emails(uid)

        for email in emails:
            msg_id = str(email["id"])
            if await is_processed(msg_id):
                continue

            # 初回未処理メール到達時に LangGraph を初期化
            if graph is None:
                llm = create_llm_provider(settings)
                graph = build_graph(
                    llm, settings.auto_create_threshold, settings.manual_review_threshold
                )

            subject = str(email.get("subject", ""))
            body = str(email.get("body", {}).get("content", ""))
            text = f"件名: {subject}\n\n{body}"

            state: AgentState = {
                "source_text": text,
                "source_type": "email",
                "source_id": msg_id,
                "sensitivity": None,
                "extracted_tasks": [],
                "actions": [],
                "errors": [],
            }
            result = await graph.ainvoke(state)

            action_map = dict(result["actions"])
            for task in result["extracted_tasks"]:
                action = action_map.get(task.title, "log_only")
                if action in ("auto_create", "request_approval"):
                    await route_task(
                        task=task,
                        todo_connector=todo,
                        planner_connector=planner,
                        company_plan_id=settings.company_wide_plan_id,
                        dept_plan_map=settings.get_dept_plan_map(),
                    )

            await mark_processed(msg_id, "email")
            await graph_client.mark_email_read(uid, msg_id)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    settings = get_settings()
    scheduler.add_job(
        polling_job,
        "interval",
        seconds=settings.polling_interval_seconds,
        id="polling",
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="AutoTicket API", lifespan=lifespan)
app.include_router(health.router)
app.include_router(tasks.router)
