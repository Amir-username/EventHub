from pydantic import BaseModel, EmailStr


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    email: str | None = None
    role: str | None = None
    type: str | None = None


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str

    model_config = {"from_attributes": True}
