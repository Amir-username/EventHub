from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import AdminUserCreate, AdminUserUpdate


def _parse_user_role(value: str) -> UserRole:
    """Parse user role with a clear error on invalid values."""
    try:
        return UserRole(value)
    except ValueError:
        valid = [r.value for r in UserRole]
        raise ValueError(f"Invalid role '{value}'. Must be one of: {', '.join(valid)}")


class AdminUserService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def list_users(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        role: UserRole | None = None,
        search: str | None = None,
    ) -> tuple[list, int]:
        return await self.repo.list_all(
            offset=offset, limit=limit, role=role, search=search
        )

    async def get_user(self, user_id: int):
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        return user

    async def create_user(self, data: AdminUserCreate):
        existing = await self.repo.get_by_email(data.email)
        if existing:
            raise ValueError("Email already exists")

        role = _parse_user_role(data.role)
        hashed = hash_password(data.password)
        return await self.repo.create(
            email=data.email,
            hashed_password=hashed,
            full_name=data.full_name,
            role=role,
        )

    async def update_user(self, user_id: int, data: AdminUserUpdate):
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        fields: dict = {}
        if data.email is not None:
            duplicate = await self.repo.get_by_email(data.email)
            if duplicate and duplicate.id != user_id:
                raise ValueError("Email already exists")
            fields["email"] = data.email
        if data.password is not None:
            fields["hashed_password"] = hash_password(data.password)
        if data.full_name is not None:
            fields["full_name"] = data.full_name
        if data.role is not None:
            fields["role"] = _parse_user_role(data.role)

        return await self.repo.update(user, **fields)

    async def delete_user(self, user_id: int, current_user_id: int):
        if user_id == current_user_id:
            raise ValueError("Cannot delete your own account")

        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        await self.repo.delete(user)
