from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_user
from app.db.session import get_db
from app.schemas.kanban import (
    CommentCreate,
    CommentResponse,
    TaskCreate,
    TaskHistoryResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services import board as board_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    project_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await board_service.list_tasks(db, project_id, search, assignee, priority, tag)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_user)],
)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    return await board_service.create_task(db, payload)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_user)],
)
async def update_task(
    task_id: int, payload: TaskUpdate, db: AsyncSession = Depends(get_db)
):
    return await board_service.update_task(db, task_id, payload)


@router.put(
    "/{task_id}/move",
    response_model=TaskResponse,
    dependencies=[Depends(require_user)],
)
async def move_task(
    task_id: int,
    target_column_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await board_service.move_task(db, task_id, target_column_id)


@router.delete(
    "/{task_id}",
    dependencies=[Depends(require_user)],
)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    await board_service.delete_task(db, task_id)
    return {"status": "deleted"}


@router.get("/{task_id}/history", response_model=list[TaskHistoryResponse], tags=["Task Details"])
async def task_history(task_id: int, db: AsyncSession = Depends(get_db)):
    events = await board_service.task_history(db, task_id)
    return [
        TaskHistoryResponse(timestamp=board_service.format_timestamp(e.created_at), action=e.action)
        for e in events
    ]


@router.get("/{task_id}/comments", response_model=list[CommentResponse], tags=["Task Details"])
async def task_comments(task_id: int, db: AsyncSession = Depends(get_db)):
    comments = await board_service.task_comments(db, task_id)
    return [
        CommentResponse(
            author=c.author,
            text=c.text,
            timestamp=board_service.format_timestamp(c.created_at),
        )
        for c in comments
    ]


@router.post(
    "/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_user)],
    tags=["Task Details"],
)
async def add_comment(task_id: int, payload: CommentCreate, db: AsyncSession = Depends(get_db)):
    comment = await board_service.add_comment(db, task_id, payload.author, payload.text)
    return CommentResponse(
        author=comment.author,
        text=comment.text,
        timestamp=board_service.format_timestamp(comment.created_at),
    )
