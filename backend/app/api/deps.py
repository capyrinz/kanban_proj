from typing import Callable

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.kanban import User
from app.repositories import users as users_repo
from app.services import auth as auth_service

AUTH_REQUIRED = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    payload = auth_service.decode_token(authorization.split(" ", 1)[1])
    if payload is None:
        return None
    return await users_repo.get_by_username(db, payload.get("sub", ""))


async def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация", headers=AUTH_REQUIRED)
    return user


def require_roles(*roles: str) -> Callable:
    async def dependency(user: User = Depends(require_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        return user

    return dependency
