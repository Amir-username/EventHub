from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token, UserLogin


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def register(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ):
        """Register a new customer."""
        hashed = hash_password(password)
        return await self.repo.create(
            email=email,
            hashed_password=hashed,
            full_name=full_name,
        )

    async def login(self, credentials: UserLogin) -> Token:
        """Authenticate and issue JWT."""
        user = await self.repo.get_by_email(credentials.email)
        if not user or not verify_password(credentials.password, user.hashed_password):
            raise ValueError("Invalid credentials")

        # Rehash if Argon2 params upgraded
        if needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(credentials.password)
            await self.repo.save(user)

        token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
            }
        )
        return Token(access_token=token)
