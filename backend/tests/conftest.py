import asyncio
import os
import tempfile
from pathlib import Path

_TMP_DIR = Path(tempfile.mkdtemp(prefix="kanban-tests-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DIR}/app.db"
os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-bytes-long")

_PW_LIBS = "/home/semen/.cache/pwlibs/usr/lib/x86_64-linux-gnu"
if os.path.isdir(_PW_LIBS) and _PW_LIBS not in os.environ.get("LD_LIBRARY_PATH", ""):
    os.environ["LD_LIBRARY_PATH"] = (
        _PW_LIBS + ":" + os.environ.get("LD_LIBRARY_PATH", "")
    ).rstrip(":")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.seed import seed_session
from app.db.session import Base, get_db, setup_connection
from app.main import app

TEST_DB_URL = f"sqlite+aiosqlite:///{_TMP_DIR}/test.db"
test_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
event.listen(test_engine.sync_engine, "connect", setup_connection)
TestSessionFactory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def reset_db() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionFactory() as session:
        await seed_session(session)


def run_async(coro):
    return asyncio.run(coro)


async def override_get_db():
    async with TestSessionFactory() as session:
        yield session


@pytest.fixture(autouse=True)
def _clear_stale_event_loop(request):
    """Playwright (sync API) оставляет «running» event loop в главном потоке,
    из-за чего asyncio.run/pytest-asyncio падают в тестах после E2E.
    Временно снимаем его на период обычного теста и возвращаем обратно,
    чтобы корректно работал финальный teardown Playwright."""
    playwright_fixtures = {"page", "context", "browser", "browser_type", "playwright"}
    stale_loop = None
    if playwright_fixtures.isdisjoint(request.fixturenames):
        stale_loop = asyncio.events._get_running_loop()
        if stale_loop is not None:
            asyncio.events._set_running_loop(None)
    yield
    if stale_loop is not None:
        asyncio.events._set_running_loop(stale_loop)


@pytest.fixture
async def db_session():
    await reset_db()
    async with TestSessionFactory() as session:
        yield session


@pytest.fixture
def client():
    run_async(reset_db())
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def manager_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "manager1", "password": "secret", "role": "manager"},
    )
    response = client.post(
        "/api/v1/auth/login", json={"username": "manager1", "password": "secret"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def developer_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"username": "dev1", "password": "secret", "role": "developer"},
    )
    response = client.post(
        "/api/v1/auth/login", json={"username": "dev1", "password": "secret"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
