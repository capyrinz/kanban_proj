from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kanban import User


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    return await db.scalar(select(User).where(User.username == username))


async def create(db: AsyncSession, username: str, hashed_password: str, role: str) -> User:
    user = User(username=username, hashed_password=hashed_password, role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
