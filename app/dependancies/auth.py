from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.dependancies.db_dependancy import DbSessionDep

from jose import jwt, JWTError
from sqlalchemy.future import select

from app.config import settings
from app.db.db_models import User

# OAUTH2PasswordBearer -> inbuilt fastapi to check if header contains the jwt token if not the 401 error

# tokenUrl="login"
# This is for the Docs (/docs page).
# It tells Swagger UI: "If the user isn't logged in, send them to the /login endpoint to get a token."
oauth2scheme = OAuth2PasswordBearer(tokenUrl="/login")


async def get_current_user(db: DbSessionDep, token: str = Depends(oauth2scheme)):

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # we dceode the jwt uisnh our  secret_key and save algo

        # lets try to get user email
        email: str = payload.get("sub")

        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    query = select(User).where(User.email == email)
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
