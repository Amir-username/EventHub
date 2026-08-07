from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedUsers(BaseModel):
    items: list[UserRead]
    total: int
    offset: int
    limit: int


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = Field(default=None, min_length=1)
    role: str = "customer"


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = Field(default=None, min_length=1)
    role: str | None = None
