import uuid

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False

    class Config:
        from_attributes = True
