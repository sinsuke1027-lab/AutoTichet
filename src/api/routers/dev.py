"""開発モード専用エンドポイント（DEV_MODE=true のときのみ有効）"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db
from src.db.models import UserProfile
from src.models.config import get_settings
from src.models.task_web import AdminUserResponse

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


def _require_dev_mode() -> None:
    if not get_settings().dev_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get(
    "/users", response_model=list[AdminUserResponse], dependencies=[Depends(_require_dev_mode)]
)
async def list_dev_users(db: DbDep) -> list[AdminUserResponse]:
    """開発ログイン画面用: 認証不要でユーザー一覧を返す（DEV_MODE=true のみ）"""
    result = await db.execute(select(UserProfile).order_by(UserProfile.display_name))
    return [AdminUserResponse.model_validate(u) for u in result.scalars().all()]
