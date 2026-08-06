"""Create an admin user in the database.

Usage:
    python scripts/create_admin.py
"""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal
from app.models.user import User


async def create_admin() -> None:
    email = "eventhubadmin@gmail.com"
    plain_password = "AdminPassword"
    full_name = "Admin"

    hashed = hash_password(plain_password)
    print(f"Generated Argon2 hash: {hashed}")

    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(
                f"User '{email}' already exists (id={existing.id}, role={existing.role})."
            )
            return

        # Insert the admin user
        user = User(
            email=email,
            hashed_password=hashed,
            full_name=full_name,
            role="ADMIN",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print("Admin user created successfully!")
        print(f"  ID:        {user.id}")
        print(f"  Email:     {user.email}")
        print(f"  Full Name: {user.full_name}")
        print(f"  Role:      {user.role}")


if __name__ == "__main__":
    asyncio.run(create_admin())
