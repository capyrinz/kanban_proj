from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.kanban import User
from app.repositories import users as users_repo

REGISTER_ROLES = ("developer", "manager")


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(_password_bytes(password), salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(password), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=settings.access_token_ttl_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


async def register_user(
    db: AsyncSession, username: str, password: str, role: str
) -> User:
    if role not in REGISTER_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Регистрация с ролью администратора запрещена",
        )
    if await users_repo.get_by_username(db, username) is not None:
        raise HTTPException(status_code=409, detail="Пользователь уже существует")
    return await users_repo.create(db, username, hash_password(password), role)


async def authenticate(db: AsyncSession, username: str, password: str) -> User:
    user = await users_repo.get_by_username(db, username)
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
