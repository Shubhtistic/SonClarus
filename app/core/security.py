from datetime import timedelta, datetime, timezone
from uuid import uuid4
from passlib.context import CryptContext
from jose import jwt, JWTError
from app.config import settings
from fastapi import HTTPException, status

pass_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # hashes the password

    return pass_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pass_context.verify(password, hashed_password)


def create_token(data: dict, expires_in: timedelta):
    to_encode = data.copy()

    if expires_in:
        expire = datetime.now(timezone.utc) + expires_in
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})  # exp is a special keyword that browsers look at
    to_encode["jti"] = str(uuid4())
    # jwt.encode does three things:
    #   turns the json data into a string
    # signs it using the secret_key
    #   stamps it with the algo hs256
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
