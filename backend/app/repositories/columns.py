from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kanban import Column


async def list_all(db: AsyncSession, project_id: int | None = None) -> list[Column]:
    query = select(Column)
    if project_id is not None:
        query = query.where(Column.project_id == project_id)
    query = query.order_by(Column.order, Column.id)
    result = await db.scalars(query)
    return list(result)


async def get(db: AsyncSession, column_id: int) -> Column | None:
    return await db.get(Column, column_id)


async def count(db: AsyncSession, project_id: int) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(Column).where(Column.project_id == project_id))
        or 0
    )


async def create(
    db: AsyncSession, project_id: int, title: str, wip_limit: int, order: int
) -> Column:
    column = Column(project_id=project_id, title=title, wip_limit=wip_limit, order=order)
    db.add(column)
    await db.commit()
    await db.refresh(column)
    return column


async def delete(db: AsyncSession, column: Column) -> None:
    await db.delete(column)
    await db.commit()
