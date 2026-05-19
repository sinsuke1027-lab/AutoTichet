import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Section
from src.models.task_web import SectionCreate, SectionReorderItem, SectionResponse, SectionUpdate

router = APIRouter(prefix="/api/v1/projects/{project_id}/sections", tags=["sections"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _get_section_or_404(
    project_id: uuid.UUID, section_id: uuid.UUID, db: AsyncSession
) -> Section:
    result = await db.execute(
        select(Section).where(Section.id == section_id, Section.project_id == project_id)
    )
    section = result.scalar_one_or_none()
    if section is None:
        raise HTTPException(status_code=404, detail="セクションが見つかりません")
    return section


@router.get("", response_model=list[SectionResponse])
async def list_sections(
    project_id: uuid.UUID, db: DbDep, current_user: CurrentUser
) -> list[SectionResponse]:
    result = await db.execute(
        select(Section).where(Section.project_id == project_id).order_by(Section.order_index.asc())
    )
    return [SectionResponse.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def create_section(
    project_id: uuid.UUID, body: SectionCreate, db: DbDep, current_user: CurrentUser
) -> SectionResponse:
    section = Section(project_id=project_id, name=body.name, order_index=body.order_index)
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return SectionResponse.model_validate(section)


@router.put("/{section_id}", response_model=SectionResponse)
async def update_section(
    project_id: uuid.UUID,
    section_id: uuid.UUID,
    body: SectionUpdate,
    db: DbDep,
    current_user: CurrentUser,
) -> SectionResponse:
    section = await _get_section_or_404(project_id, section_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(section, field, value)
    await db.commit()
    await db.refresh(section)
    return SectionResponse.model_validate(section)


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    project_id: uuid.UUID,
    section_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    section = await _get_section_or_404(project_id, section_id, db)
    await db.delete(section)
    await db.commit()


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_sections(
    project_id: uuid.UUID,
    body: list[SectionReorderItem],
    db: DbDep,
    current_user: CurrentUser,
) -> None:
    for item in body:
        result = await db.execute(
            select(Section).where(Section.id == item.id, Section.project_id == project_id)
        )
        section = result.scalar_one_or_none()
        if section is not None:
            section.order_index = item.order_index
    await db.commit()
