import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.graph import AgentState, build_graph
from src.api.routers import dashboard, health, projects, task_details, tasks, tasks_crud, users
from src.connectors.forms import FormsConnector
from src.connectors.graph_api import GraphAPIClient
from src.connectors.onenote import OneNoteConnector
from src.connectors.planner import PlannerConnector
from src.connectors.teams_chat import TeamsChatConnector
from src.connectors.todo import TodoConnector
from src.models.config import get_settings
from src.providers.factory import create_llm_provider
from src.services.routing import route_task
from src.services.state import init_db, is_processed, mark_processed

scheduler = AsyncIOScheduler()


async def _run_agent_and_route(
    text: str,
    source_type: str,
    source_id: str,
    graph: Any,
    planner: PlannerConnector,
    todo: TodoConnector,
    company_plan_id: str,
    dept_plan_map: dict[str, str],
) -> None:
    """テキストを LangGraph で処理してタスクを起票する"""
    state: AgentState = {
        "source_text": text,
        "source_type": source_type,
        "source_id": source_id,
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
                company_plan_id=company_plan_id,
                dept_plan_map=dept_plan_map,
            )


async def polling_job() -> None:
    """Outlook メール・Teams チャット・OneNote ページをポーリングしてタスクを自動起票する"""
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
    teams = TeamsChatConnector(graph_client)
    onenote = OneNoteConnector(graph_client)
    forms = FormsConnector(graph_client)

    # ALLOWED_USER_IDS 設定時は get_users() を呼ばず直接使用（最小権限）
    allowed_ids = settings.get_allowed_user_ids()
    if allowed_ids:
        target_users: list[dict[str, Any]] = [{"id": uid} for uid in allowed_ids]
    else:
        target_users = await graph_client.get_users()

    # LLM・graph は最初の未処理アイテム到達時に遅延初期化
    graph: Any = None

    def _ensure_graph() -> Any:
        nonlocal graph
        if graph is None:
            llm = create_llm_provider(settings)
            graph = build_graph(
                llm, settings.auto_create_threshold, settings.manual_review_threshold
            )
        return graph

    # ── Outlook メール処理 ──────────────────────────────────────────────
    for user in target_users:
        uid = str(user.get("id", ""))
        if not uid:
            continue
        emails = await graph_client.get_unread_emails(uid)
        for email in emails:
            msg_id = str(email["id"])
            if await is_processed(msg_id):
                continue
            subject = str(email.get("subject", ""))
            body = str(email.get("body", {}).get("content", ""))
            await _run_agent_and_route(
                text=f"件名: {subject}\n\n{body}",
                source_type="email",
                source_id=msg_id,
                graph=_ensure_graph(),
                planner=planner,
                todo=todo,
                company_plan_id=settings.company_wide_plan_id,
                dept_plan_map=settings.get_dept_plan_map(),
            )
            await mark_processed(msg_id, "email")
            await graph_client.mark_email_read(uid, msg_id)

    # ── Teams チャンネルメッセージ処理 ─────────────────────────────────
    team_list = await teams.get_teams()
    for team in team_list:
        channels = await teams.get_channels(str(team["id"]))
        for channel in channels:
            messages = await teams.get_channel_messages(str(team["id"]), str(channel["id"]))
            for msg in messages:
                msg_id = str(msg["id"])
                if await is_processed(msg_id):
                    continue
                text = str(msg.get("body", {}).get("content", ""))
                await _run_agent_and_route(
                    text=text,
                    source_type="chat",
                    source_id=msg_id,
                    graph=_ensure_graph(),
                    planner=planner,
                    todo=todo,
                    company_plan_id=settings.company_wide_plan_id,
                    dept_plan_map=settings.get_dept_plan_map(),
                )
                await mark_processed(msg_id, "chat")

    # ── OneNote ページ処理 ──────────────────────────────────────────────
    pages = await onenote.get_recent_pages()
    for page in pages:
        page_id = str(page["id"])
        if await is_processed(page_id):
            continue
        content = await onenote.get_page_content(page_id)
        await _run_agent_and_route(
            text=content,
            source_type="onenote",
            source_id=page_id,
            graph=_ensure_graph(),
            planner=planner,
            todo=todo,
            company_plan_id=settings.company_wide_plan_id,
            dept_plan_map=settings.get_dept_plan_map(),
        )
        await mark_processed(page_id, "onenote")

    # ── Microsoft Forms（SharePoint 経由）─────────────────────────────────
    if settings.sharepoint_site_id and settings.forms_list_id:
        try:
            form_responses = await forms.get_form_responses()
            for form_item in form_responses:
                item_id = str(form_item.get("id", ""))
                if not item_id:
                    continue
                if await is_processed(item_id):
                    continue
                fields = form_item.get("fields", {})
                text = "\n".join(f"{k}: {v}" for k, v in fields.items() if isinstance(v, str))
                if text.strip():
                    await _run_agent_and_route(
                        text=text,
                        source_type="form",
                        source_id=item_id,
                        graph=_ensure_graph(),
                        planner=planner,
                        todo=todo,
                        company_plan_id=settings.company_wide_plan_id,
                        dept_plan_map=settings.get_dept_plan_map(),
                    )
                    await mark_processed(item_id, "form")
        except Exception as e:
            logging.getLogger(__name__).warning("Forms ポーリングエラー: %s", e)


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

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(tasks_crud.router)
app.include_router(task_details.router)
app.include_router(dashboard.router)
app.include_router(users.router)
