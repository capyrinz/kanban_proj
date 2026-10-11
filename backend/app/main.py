from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.core.config import BACKEND_DIR
from app.db.seed import seed_initial_data
from app.db.session import init_db

STATIC_DIR = BACKEND_DIR / "app" / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    await seed_initial_data()
    yield


app = FastAPI(
    title="Kanban Board API",
    version="1.0.0",
    description="REST API Kanban-доски: проекты, колонки, задачи, роли, JWT.",
    lifespan=lifespan,
)

app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(STATIC_DIR / "index.html")
