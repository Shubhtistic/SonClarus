from pydantic import BaseModel
from pydantic import EmailStr


class RegisterUser(BaseModel):
    email: EmailStr
    name: str
    password: str
