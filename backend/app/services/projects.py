from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kanban import Project
from app.repositories import projects as projects_repo


async def list_projects(db: AsyncSession) -> list[Project]:
    return await projects_repo.list_all(db)


async def create_project(
    db: AsyncSession, title: str, description: str | None
) -> Project:
    return await projects_repo.create(db, title, description)


async def get_project_or_404(db: AsyncSession, project_id: int) -> Project:
    project = await projects_repo.get(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project


async def update_project(
    db: AsyncSession, project_id: int, title: str | None, description: str | None
) -> Project:
    project = await get_project_or_404(db, project_id)
    return await projects_repo.update(
        db,
        project,
        title if title is not None else project.title,
        description if description is not None else project.description,
    )


async def delete_project(db: AsyncSession, project_id: int) -> None:
    project = await get_project_or_404(db, project_id)
    await projects_repo.delete(db, project)
