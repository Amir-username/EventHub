# app/services/auth_service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPair, UserLogin, UserRegister


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def register(self, credentials: UserRegister):
        user = await self.repo.get_by_email(credentials.email)
        if user:
            raise ValueError("email already exists")

        hashed = hash_password(credentials.password)
        return await self.repo.create(
            email=credentials.email,
            hashed_password=hashed,
            full_name=credentials.full_name,
        )

    async def login(self, credentials: UserLogin) -> TokenPair:
        user = await self.repo.get_by_email(credentials.email)
        if not user or not verify_password(credentials.password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(credentials.password)
            await self.repo.save(user)

        access = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )
        refresh = create_refresh_token(data={"sub": str(user.id)})
        return TokenPair(access_token=access, refresh_token=refresh)

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("Invalid token type")
            user_id = int(payload.get("sub"))
        except Exception as e:
            raise ValueError("Invalid refresh token") from e

        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        access = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )
        new_refresh = create_refresh_token(data={"sub": str(user.id)})
        return TokenPair(access_token=access, refresh_token=new_refresh)
