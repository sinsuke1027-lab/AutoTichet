import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import CurrentUser
from src.db.engine import get_db
from src.db.models import Project, Section, Task, TaskAssignee, TaskTag, UserProfile
from src.models.task_web import ImportPreviewResponse, ImportResult
from src.services.asana_importer import AsanaRow, parse_asana_xlsx

router = APIRouter(prefix="/api/v1/import", tags=["import"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


async def _get_email_to_user_id(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(UserProfile).where(UserProfile.email.isnot(None)))
    return {u.email: u.user_id for u in result.scalars().all() if u.email}


async def _parse_and_validate(
    file: UploadFile, db: AsyncSession
) -> tuple[list[AsanaRow], dict[str, str], list[str]]:
    contents = await file.read()
    rows = parse_asana_xlsx(contents)
    email_map = await _get_email_to_user_id(db)
    warnings: list[str] = []
    all_emails: set[str] = {r.assignee_email for r in rows if r.assignee_email}
    all_emails |= {e for r in rows for e in r.sub_assignee_emails}
    for email in sorted(all_emails):
        if email and email not in email_map:
            warnings.append(f"{email} はシステムに未登録のため担当者は空になります")
    return rows, email_map, warnings


@router.post("/asana/preview", response_model=ImportPreviewResponse)
async def preview_asana(
    file: UploadFile, db: DbDep, current_user: CurrentUser
) -> ImportPreviewResponse:
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=422, detail=".xlsx ファイルをアップロードしてください")
    rows, email_map, warnings = await _parse_and_validate(file, db)
    project_name = file.filename.replace(".xlsx", "")
    sections: dict[str, int] = {}
    for r in rows:
        if r.section:
            sections[r.section] = sections.get(r.section, 0) + 1
    completed = sum(1 for r in rows if r.is_completed)
    with_subtasks = sum(1 for r in rows if r.parent_task_name)
    with_deps = sum(1 for r in rows if r.blocked_by)
    return ImportPreviewResponse(
        file_name=file.filename,
        projects=[{"name": project_name, "will_create": True}],
        sections=[
            {"project": project_name, "name": s, "task_count": c} for s, c in sections.items()
        ],
        tasks={
            "total": len(rows),
            "completed": completed,
            "with_subtasks": with_subtasks,
            "with_dependencies": with_deps,
        },
        warnings=warnings,
    )


@router.post("/asana/confirm", response_model=ImportResult)
async def confirm_asana(file: UploadFile, db: DbDep, current_user: CurrentUser) -> ImportResult:
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=422, detail=".xlsx ファイルをアップロードしてください")
    rows, email_map, _ = await _parse_and_validate(file, db)
    project_name = file.filename.replace(".xlsx", "")

    project = Project(name=project_name, created_by=current_user.sub)
    db.add(project)
    await db.flush()

    section_map: dict[str, uuid.UUID] = {}
    section_count = 0
    for idx, section_name in enumerate(dict.fromkeys(r.section for r in rows if r.section)):
        sec = Section(project_id=project.id, name=section_name, order_index=idx)
        db.add(sec)
        await db.flush()
        section_map[section_name] = sec.id
        section_count += 1

    ext_ids = [r.task_id for r in rows if r.task_id]
    existing_ext: set[str] = set()
    if ext_ids:
        ext_result = await db.execute(select(Task.external_id).where(Task.external_id.in_(ext_ids)))
        existing_ext = {row[0] for row in ext_result.all() if row[0]}

    name_to_id: dict[str, uuid.UUID] = {}
    created = 0
    skipped = 0
    errors: list[str] = []

    top_level = [r for r in rows if not r.parent_task_name]
    sub_level = [r for r in rows if r.parent_task_name]

    for r in top_level + sub_level:
        if r.task_id and r.task_id in existing_ext:
            skipped += 1
            continue
        assignee_id = email_map.get(r.assignee_email) if r.assignee_email else None
        parent_id = name_to_id.get(r.parent_task_name) if r.parent_task_name else None
        task = Task(
            title=r.name,
            description=r.notes or None,
            status="completed" if r.is_completed else "not_started",
            priority=r.priority,
            assignee_id=assignee_id,
            due_date=r.due_date,
            start_date=r.start_date,
            completed_at=r.completed_at,
            visibility="team",
            project_id=project.id,
            section_id=section_map.get(r.section) if r.section else None,
            parent_task_id=parent_id,
            external_id=r.task_id or None,
            created_by=current_user.sub,
        )
        db.add(task)
        await db.flush()
        name_to_id[r.name] = task.id
        for tag in r.tags:
            db.add(TaskTag(task_id=task.id, tag=tag))
        for sub_email in r.sub_assignee_emails:
            sub_uid = email_map.get(sub_email)
            if sub_uid:
                db.add(TaskAssignee(task_id=task.id, user_id=sub_uid, role="sub"))
        created += 1

    await db.commit()
    return ImportResult(
        created_tasks=created,
        created_sections=section_count,
        skipped_duplicates=skipped,
        errors=errors,
    )
