import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Task, TaskTag, TaskTemplate
from src.models.task_web import (
    TemplateApplyRequest,
    TemplateApplyResponse,
    TemplateCreate,
    TemplateData,
    TemplateResponse,
    TemplateUpdate,
)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


def _template_to_response(template: TaskTemplate) -> TemplateResponse:
    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        template_data=TemplateData.model_validate(template.template_data),
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


async def _get_or_404(db: AsyncSession, template_id: uuid.UUID) -> TaskTemplate:
    result = await db.execute(select(TaskTemplate).where(TaskTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    return template


@router.get("", response_model=list[TemplateResponse])
async def list_templates(db: DbDep, current_user: CurrentUser) -> list[TemplateResponse]:
    result = await db.execute(select(TaskTemplate).order_by(TaskTemplate.created_at.desc()))
    return [_template_to_response(t) for t in result.scalars().all()]


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate, db: DbDep, current_user: CurrentUser
) -> TemplateResponse:
    template = TaskTemplate(
        name=body.name,
        description=body.description,
        template_data=body.template_data.model_dump(),
        created_by=current_user.sub,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return _template_to_response(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> TemplateResponse:
    return _template_to_response(await _get_or_404(db, template_id))


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID, body: TemplateUpdate, db: DbDep, current_user: CurrentUser
) -> TemplateResponse:
    template = await _get_or_404(db, template_id)
    if template.created_by != current_user.sub and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="更新権限がありません")
    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.template_data is not None:
        template.template_data = body.template_data.model_dump()
    await db.commit()
    await db.refresh(template)
    return _template_to_response(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: uuid.UUID, db: DbDep, current_user: CurrentUser) -> None:
    template = await _get_or_404(db, template_id)
    if template.created_by != current_user.sub and "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="削除権限がありません")
    await db.delete(template)
    await db.commit()


@router.post("/{template_id}/apply", response_model=TemplateApplyResponse)
async def apply_template(
    template_id: uuid.UUID,
    body: TemplateApplyRequest,
    db: DbDep,
    current_user: CurrentUser,
) -> TemplateApplyResponse:
    template = await _get_or_404(db, template_id)
    data = TemplateData.model_validate(template.template_data)
    base = body.base_date or date.today()

    main_task = Task(
        title=data.title,
        description=data.description,
        priority=data.priority,
        visibility=data.visibility,
        assignee_id=body.assignee_id,
        project_id=body.project_id,
        section_id=body.section_id,
        due_date=base + timedelta(days=data.due_date_offset_days),
        created_by=current_user.sub,
        source_type="template",
    )
    db.add(main_task)
    await db.flush()

    for tag in data.tags:
        db.add(TaskTag(task_id=main_task.id, tag=tag))

    subtask_ids: list[uuid.UUID] = []
    for sub in data.subtasks:
        subtask = Task(
            title=sub.title,
            description=sub.description,
            priority=sub.priority,
            visibility=data.visibility,
            parent_task_id=main_task.id,
            project_id=body.project_id,
            section_id=body.section_id,
            assignee_id=body.assignee_id,
            due_date=base + timedelta(days=sub.due_date_offset_days),
            created_by=current_user.sub,
            source_type="template",
        )
        db.add(subtask)
        await db.flush()
        subtask_ids.append(subtask.id)

    await db.commit()
    return TemplateApplyResponse(task_id=main_task.id, subtask_ids=subtask_ids)
