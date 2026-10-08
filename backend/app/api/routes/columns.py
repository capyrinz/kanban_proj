from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, require_user
from app.db.session import get_db
from app.schemas.kanban import ColumnCreate, ColumnResponse, ColumnUpdate
from app.services import board as board_service

router = APIRouter(prefix="/columns", tags=["Columns"])


@router.get("", response_model=list[ColumnResponse])
async def list_columns(
    project_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await board_service.list_columns(db, project_id)


@router.post(
    "",
    response_model=ColumnResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_user)],
)
async def create_column(payload: ColumnCreate, db: AsyncSession = Depends(get_db)):
    return await board_service.create_column(db, payload)


@router.put(
    "/{column_id}",
    response_model=ColumnResponse,
    dependencies=[Depends(require_user)],
)
async def update_column(
    column_id: int, payload: ColumnUpdate, db: AsyncSession = Depends(get_db)
):
    return await board_service.update_column(db, column_id, payload)


@router.delete(
    "/{column_id}",
    dependencies=[Depends(require_roles("administrator", "manager"))],
)
async def delete_column(column_id: int, db: AsyncSession = Depends(get_db)):
    await board_service.delete_column(db, column_id)
    return {"status": "deleted"}
