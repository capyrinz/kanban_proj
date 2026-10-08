from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.kanban import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import projects as project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    return await project_service.list_projects(db)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("administrator", "manager"))],
)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    return await project_service.create_project(db, payload.title, payload.description)


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_roles("administrator", "manager"))],
)
async def update_project(
    project_id: int, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    return await project_service.update_project(
        db, project_id, payload.title, payload.description
    )


@router.delete(
    "/{project_id}",
    dependencies=[Depends(require_roles("administrator"))],
)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    await project_service.delete_project(db, project_id)
    return {"status": "deleted"}
