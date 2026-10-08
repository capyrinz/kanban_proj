from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kanban import Comment, Task, TaskEvent


def _filtered_query(
    project_id: int | None,
    search: str | None,
    assignee: str | None,
    priority: str | None,
    tag: str | None,
):
    query = select(Task)
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(
            func.lower_uni(Task.title).like(pattern) | func.lower_uni(Task.description).like(pattern)
        )
    if assignee:
        query = query.where(func.lower_uni(Task.assignee).like(f"%{assignee.lower()}%"))
    if priority:
        query = query.where(Task.priority == priority)
    if tag:
        query = query.where(func.lower_uni(Task.tags).like(f"%{tag.lower()}%"))
    return query.order_by(Task.id)


async def list_tasks(
    db: AsyncSession,
    project_id: int | None = None,
    search: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
) -> list[Task]:
    result = await db.scalars(
        _filtered_query(project_id, search, assignee, priority, tag)
    )
    return list(result)


async def get(db: AsyncSession, task_id: int) -> Task | None:
    return await db.get(Task, task_id)


async def count_in_column(db: AsyncSession, column_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(Task).where(Task.column_id == column_id)
        )
        or 0
    )


async def create(
    db: AsyncSession,
    project_id: int,
    column_id: int,
    title: str,
    description: str | None,
    assignee: str,
    priority: str,
    deadline: str,
    tags: str,
    attachment_url: str,
) -> Task:
    task = Task(
        project_id=project_id,
        column_id=column_id,
        title=title,
        description=description,
        assignee=assignee,
        priority=priority,
        deadline=deadline,
        tags=tags,
        attachment_url=attachment_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def delete(db: AsyncSession, task: Task) -> None:
    await db.delete(task)
    await db.commit()


async def add_event(db: AsyncSession, task_id: int, action: str) -> TaskEvent:
    event = TaskEvent(task_id=task_id, action=action)
    db.add(event)
    await db.commit()
    return event


async def list_events(db: AsyncSession, task_id: int) -> list[TaskEvent]:
    result = await db.scalars(
        select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.id)
    )
    return list(result)


async def add_comment(db: AsyncSession, task_id: int, author: str, text: str) -> Comment:
    comment = Comment(task_id=task_id, author=author, text=text)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


async def list_comments(db: AsyncSession, task_id: int) -> list[Comment]:
    result = await db.scalars(
        select(Comment).where(Comment.task_id == task_id).order_by(Comment.id)
    )
    return list(result)
