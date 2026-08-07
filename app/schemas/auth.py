from typing import Self

from pydantic import BaseModel, EmailStr, Field, model_validator


class UserRegister(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
    confirm_pass: str

    @model_validator(mode="after")
    def passwords_match(self) -> Self:
        if self.password != self.confirm_pass:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    email: str | None = None
    role: str | None = None
    type: str | None = None
