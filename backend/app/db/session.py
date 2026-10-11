import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import BACKEND_DIR, settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _lower_uni(value):
    return value.lower() if isinstance(value, str) else value


def setup_connection(dbapi_connection, _connection_record=None) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
    dbapi_connection.create_function("lower_uni", 1, _lower_uni)


event.listen(engine.sync_engine, "connect", setup_connection)


async def get_db():
    async with async_session() as session:
        yield session


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


async def init_db() -> None:
    """Привести схему БД к состоянию из миграций Alembic."""
    config = _alembic_config()
    await asyncio.to_thread(command.upgrade, config, "head")
