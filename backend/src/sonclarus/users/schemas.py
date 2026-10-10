from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.sonclarus.shared.utilities import reject_blank_text


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr = Field(min_length=3, max_length=100)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    is_active: bool
    is_verified: bool
    storage_limit: int
    storage_used: int

    _validate_text = field_validator("first_name", "last_name", mode="before")(
        reject_blank_text
    )
