from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        role: UserRole | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        """Return (users, total_count) with optional role filter and email/name search."""
        base = select(User)
        count_q = select(func.count()).select_from(User)

        if role is not None:
            base = base.where(User.role == role)
            count_q = count_q.where(User.role == role)
        if search:
            pattern = f"%{search}%"
            cond = User.email.ilike(pattern) | User.full_name.ilike(pattern)
            base = base.where(cond)
            count_q = count_q.where(cond)

        total = (await self.db.execute(count_q)).scalar_one()
        stmt = base.order_by(User.id.desc()).offset(offset).limit(limit)
        users = list((await self.db.execute(stmt)).scalars().all())
        return users, total

    async def create(
        self,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
        role: UserRole = UserRole.CUSTOMER,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: User, **fields) -> User:
        for key, value in fields.items():
            if value is not None:
                setattr(user, key, value)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.commit()

    async def save(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
