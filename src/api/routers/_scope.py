"""ログインユーザーが参照できるリソース ID を返すヘルパー。"""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import ROLE_HIERARCHY, CurrentUser
from src.db.models import ProjectMember, UserProfile


async def visible_user_ids(db: AsyncSession, current_user: CurrentUser) -> list[str] | None:
    """参照できるユーザー ID 一覧を返す。None は制限なし（admin）。"""
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if user_role >= ROLE_HIERARCHY["admin"]:
        return None

    ids: set[str] = {current_user.sub}

    if current_user.department_tags:
        dept_result = await db.execute(
            select(UserProfile.user_id).where(
                UserProfile.department_tags.op("?|")(pg_array(current_user.department_tags))
            )
        )
        ids.update(dept_result.scalars().all())

    proj_result = await db.execute(
        select(ProjectMember.user_id).where(
            ProjectMember.project_id.in_(
                select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.sub)
            )
        )
    )
    ids.update(proj_result.scalars().all())

    return list(ids)


async def visible_project_ids(
    db: AsyncSession, current_user: CurrentUser
) -> list[uuid.UUID] | None:
    """参照できるプロジェクト ID 一覧を返す。None は制限なし（admin）。"""
    user_role = max((ROLE_HIERARCHY.get(r, 0) for r in current_user.roles), default=0)
    if user_role >= ROLE_HIERARCHY["admin"]:
        return None

    result = await db.execute(
        select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.sub)
    )
    return list(result.scalars().all())
