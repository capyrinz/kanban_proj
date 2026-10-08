from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session
from app.repositories import columns as columns_repo
from app.repositories import projects as projects_repo
from app.repositories import tasks as tasks_repo
from app.repositories import users as users_repo
from app.services.auth import hash_password

DEFAULT_COLUMNS = (
    ("Бэклог", 5, 1),
    ("В работе", 3, 2),
    ("Готово", 10, 3),
)


async def seed_session(db: AsyncSession) -> None:
    """Заполнить пустую БД администратором и стартовой доской."""
    if await users_repo.get_by_username(db, settings.admin_username) is None:
        await users_repo.create(
            db,
            settings.admin_username,
            hash_password(settings.admin_password),
            "administrator",
        )
    if await projects_repo.first(db) is not None:
        return
    project = await projects_repo.create(
        db,
        "Основной проект Kanban",
        "Курсовой проект по программной инженерии",
    )
    columns = [
        await columns_repo.create(db, project.id, title, wip_limit, order)
        for title, wip_limit, order in DEFAULT_COLUMNS
    ]
    task = await tasks_repo.create(
        db,
        project_id=project.id,
        column_id=columns[1].id,
        title="Разработать REST API",
        description="FastAPI + Pydantic v2",
        assignee="Валерия",
        priority="high",
        deadline="2026-10-01",
        tags="backend, api",
        attachment_url="https://fastapi.tiangolo.com",
    )
    await tasks_repo.add_event(db, task.id, "Задача создана")


async def seed_initial_data() -> None:
    async with async_session() as db:
        await seed_session(db)
