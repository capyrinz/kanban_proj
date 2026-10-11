from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kanban import Project


async def list_all(db: AsyncSession) -> list[Project]:
    result = await db.scalars(select(Project).order_by(Project.id))
    return list(result)


async def get(db: AsyncSession, project_id: int) -> Project | None:
    return await db.get(Project, project_id)


async def first(db: AsyncSession) -> Project | None:
    return await db.scalar(select(Project).order_by(Project.id))


async def create(db: AsyncSession, title: str, description: str | None) -> Project:
    project = Project(title=title, description=description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def update(db: AsyncSession, project: Project, title: str, description: str | None) -> Project:
    project.title = title
    project.description = description
    await db.commit()
    await db.refresh(project)
    return project


async def delete(db: AsyncSession, project: Project) -> None:
    await db.delete(project)
    await db.commit()
