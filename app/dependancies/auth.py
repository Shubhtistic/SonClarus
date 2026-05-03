from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.dependancies.db_dependancy import DbSessionDep

from sqlalchemy.future import select

from app.db.db_models import User
from app.core.security import decode_token
from app.dependancies.redis_blacklist import check_blacklisted_jti

# OAUTH2PasswordBearer -> inbuilt fastapi to check if header contains the jwt token if not the 401 error

# tokenUrl="login"
# This is for the Docs (/docs page).
# It tells Swagger UI: "If the user isn't logged in, send them to the /login endpoint to get a token."
oauth2scheme = OAuth2PasswordBearer(tokenUrl="/login")


async def get_current_user(token: str = Depends(oauth2scheme)) -> str:
    """Verifies the jwt and checks jti blacklist, Does not hit db"""

    # lets try to decode the jwt
    data = decode_token(token)
    # if jwt has any issues like expired and all -> raises 401 internally
    user_id = data.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=" Invalid credentials"
        )

    # lets check the jti blacklist
    blacklisted = await check_blacklisted_jti(jti=data.get("jti"))

    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This jwt is invalid / banned"
        )

    return user_id


async def get_current_verified_user(
    db: DbSessionDep, user_id: str = Depends(get_current_user)
) -> str:

    query = select(User.id, User.is_active).where(User.id == user_id)
    user = (await db.execute(query)).one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User Does not exit"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User not Allowed"
        )

    return user


CurrentUserDep = Annotated[str, Depends(get_current_user)]
CurrentVerifiedUserDep = Annotated[str, Depends(get_current_verified_user)]
