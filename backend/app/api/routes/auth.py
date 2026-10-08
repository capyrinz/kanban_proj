from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.kanban import TokenResponse, UserLogin, UserRegister
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register_user(
        db, payload.username, payload.password, payload.role
    )
    return {"message": f"Пользователь {user.username} успешно зарегистрирован"}


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate(db, payload.username, payload.password)
    token = auth_service.create_access_token(user.username, user.role)
    return TokenResponse(access_token=token, role=user.role, username=user.username)
