from pydantic import BaseModel, EmailStr, Field, field_validator

from src.sonclarus.shared.utilities import reject_blank_text


class SignupRequest(BaseModel):
    email: EmailStr = Field(min_length=3, max_length=100)
    password: str = Field(min_length=7, max_length=72)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)

    _validate_text = field_validator("password", "first_name", "last_name")(
        reject_blank_text
    )


class LoginRequest(BaseModel):
    email: EmailStr = Field(min_length=3, max_length=100)
    password: str = Field(min_length=7, max_length=72)

    _validate_text = field_validator("password")(reject_blank_text)
