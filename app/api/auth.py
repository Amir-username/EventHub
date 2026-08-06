from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import TokenPair, UserLogin, UserRead, UserRegister
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(credentials: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    try:
        return await service.login(credentials)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/token", response_model=TokenPair)
async def token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """OAuth2-compatible token endpoint for Swagger Authorize button.

    The 'username' field in the form is treated as email.
    """
    service = AuthService(db)
    credentials = UserLogin(email=form.username, password=form.password)
    try:
        return await service.login(credentials)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/register")
async def register(
    credentials: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]
):
    service = AuthService(db)
    try:
        return await service.register(credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
        )


@router.post("/refresh", response_model=TokenPair)
async def refresh(refresh_token: str, db: Annotated[AsyncSession, Depends(get_db)]):
    service = AuthService(db)
    try:
        return await service.refresh(refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserRead)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
