from pydantic import BaseModel, EmailStr

from uuid import UUID


class BaseUser(BaseModel):
    email: EmailStr
    full_name: str | None = None


class RegisterUser(BaseUser):
    password: str
    # when creating the user needs to give email and password


class UserRead(BaseUser):
    id: UUID
    storage_limit: int
    storage_used: int
    is_active: bool

    # the imp config
    # This tells Pydantic: "It's okay to read data from a Database Object"
    class Config:
        from_attributes = True
