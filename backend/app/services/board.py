from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kanban import Column, Comment, Task, TaskEvent
from app.repositories import columns as columns_repo
from app.repositories import projects as projects_repo
from app.repositories import tasks as tasks_repo
from app.schemas.kanban import ColumnCreate, ColumnUpdate, TaskCreate, TaskUpdate


def format_timestamp(value) -> str:
    return str(value)[:19]


async def _resolve_project_id(db: AsyncSession, project_id: int | None) -> int:
    if project_id is not None:
        if await projects_repo.get(db, project_id) is None:
            raise HTTPException(status_code=404, detail="Проект не найден")
        return project_id
    project = await projects_repo.first(db)
    if project is None:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project.id


async def list_columns(db: AsyncSession, project_id: int | None) -> list[Column]:
    return await columns_repo.list_all(db, project_id)


async def create_column(db: AsyncSession, data: ColumnCreate) -> Column:
    project_id = await _resolve_project_id(db, data.project_id)
    order = data.order if data.order is not None else await columns_repo.count(db, project_id) + 1
    return await columns_repo.create(
        db, project_id=project_id, title=data.title, wip_limit=data.wip_limit, order=order
    )


async def get_column_or_404(db: AsyncSession, column_id: int) -> Column:
    column = await columns_repo.get(db, column_id)
    if column is None:
        raise HTTPException(status_code=404, detail="Колонка не найдена")
    return column


async def update_column(
    db: AsyncSession, column_id: int, data: ColumnUpdate
) -> Column:
    column = await get_column_or_404(db, column_id)
    if data.title is not None:
        column.title = data.title
    if data.wip_limit is not None:
        column.wip_limit = data.wip_limit
    if data.order is not None:
        column.order = data.order
    await db.commit()
    await db.refresh(column)
    return column


async def delete_column(db: AsyncSession, column_id: int) -> None:
    column = await get_column_or_404(db, column_id)
    await columns_repo.delete(db, column)


async def list_tasks(
    db: AsyncSession,
    project_id: int | None,
    search: str | None,
    assignee: str | None,
    priority: str | None,
    tag: str | None,
) -> list[Task]:
    return await tasks_repo.list_tasks(db, project_id, search, assignee, priority, tag)


async def create_task(db: AsyncSession, data: TaskCreate) -> Task:
    column = await get_column_or_404(db, data.column_id)
    project_id = await _resolve_project_id(db, data.project_id)
    await _ensure_wip_not_exceeded(db, column)
    task = await tasks_repo.create(
        db,
        project_id=project_id,
        column_id=column.id,
        title=data.title,
        description=data.description,
        assignee=data.assignee or "Не назначен",
        priority=data.priority,
        deadline=data.deadline or "",
        tags=data.tags or "",
        attachment_url=data.attachment_url or "",
    )
    await tasks_repo.add_event(db, task.id, "Задача создана")
    return task


async def _ensure_wip_not_exceeded(db: AsyncSession, column: Column) -> None:
    count = await tasks_repo.count_in_column(db, column.id)
    if count >= column.wip_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Превышен WIP-лимит колонки ({column.wip_limit})!",
        )


async def get_task_or_404(db: AsyncSession, task_id: int) -> Task:
    task = await tasks_repo.get(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task


async def update_task(db: AsyncSession, task_id: int, data: TaskUpdate) -> Task:
    task = await get_task_or_404(db, task_id)
    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.assignee is not None:
        task.assignee = data.assignee
    if data.priority is not None:
        task.priority = data.priority
    if data.deadline is not None:
        task.deadline = data.deadline
    if data.tags is not None:
        task.tags = data.tags
    if data.attachment_url is not None:
        task.attachment_url = data.attachment_url
    await db.commit()
    await db.refresh(task)
    await tasks_repo.add_event(db, task.id, "Карточка отредактирована")
    return task


async def move_task(db: AsyncSession, task_id: int, target_column_id: int) -> Task:
    task = await get_task_or_404(db, task_id)
    if task.column_id == target_column_id:
        return task
    target = await get_column_or_404(db, target_column_id)
    await _ensure_wip_not_exceeded(db, target)
    old_column = await columns_repo.get(db, task.column_id)
    old_title = old_column.title if old_column else "удалённая колонка"
    task.column_id = target.id
    await db.commit()
    await db.refresh(task)
    await tasks_repo.add_event(
        db, task.id, f"Перемещена из '{old_title}' в '{target.title}'"
    )
    return task


async def delete_task(db: AsyncSession, task_id: int) -> None:
    task = await get_task_or_404(db, task_id)
    await tasks_repo.delete(db, task)


async def task_history(db: AsyncSession, task_id: int) -> list[TaskEvent]:
    return await tasks_repo.list_events(db, task_id)


async def add_comment(
    db: AsyncSession, task_id: int, author: str, text: str
) -> Comment:
    await get_task_or_404(db, task_id)
    return await tasks_repo.add_comment(db, task_id, author, text)


async def task_comments(db: AsyncSession, task_id: int) -> list[Comment]:
    return await tasks_repo.list_comments(db, task_id)
