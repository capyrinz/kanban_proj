from fastapi import APIRouter

from app.api.routes import auth, columns, projects, tasks

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(projects.router)
router.include_router(columns.router)
router.include_router(tasks.router)
