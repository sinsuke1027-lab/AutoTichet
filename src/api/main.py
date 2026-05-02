from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from src.api.routers import health, tasks
from src.models.config import get_settings
from src.services.state import init_db

scheduler = AsyncIOScheduler()


async def polling_job() -> None:
    """Graph API申請後に実装（Part B Task 17で接続）"""
    pass


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
