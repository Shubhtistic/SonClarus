from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, status, HTTPException, Depends
from app.schemas.user_schema import RegisterUser, UserRead

from app.dependancies.db_dependancy import DbSessionDep  # async db session
from app.schemas.user_auth import RefreshRequest, LogoutRequest
from app.db.db_models import User, RefreshToken  # user table defn


from app.core.security import hash_password, verify_password, create_token
from sqlalchemy.future import select
from app.config import settings
from app.schemas.token_schema import Token
from fastapi.security import OAuth2PasswordRequestForm

from app.core.refresh_token import (
    create_refresh_token,
    get_refresh_token_expiry,
    hash_refresh_token,
)
from app.dependancies.auth import CurrentUserDep

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def users_me(current_user: CurrentUserDep):
    return current_user


@router.post("/register", response_model=UserRead)
async def register_user(user_data: RegisterUser, db: DbSessionDep):
    # lets first run a query to see if the email already exists
    normalized_email = user_data.email.lower()
    query = select(User).where(User.email == normalized_email)

    result = await db.execute(query)

    existing_user = result.scalar_one_or_none()

    if existing_user:  # if present
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The User With Email Already Exists.",
        )

    ## we reached here -> email does not exist
    hashed_pwd = hash_password(user_data.password)

    new_user = User(
        email=user_data.email, hashed_password=hashed_pwd, full_name=user_data.full_name
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
async def login(db: DbSessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    takes form data -> username and password
    verifies and then returns assigned jwt

    """
    # Note: form_data.username holds our email because of OAuth2 standards form data should have username and password by default
    normalized_email = form_data.username.lower()
    query = select(User).where(User.email == normalized_email)
    res = await db.execute(query)

    user = res.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User Or Password is wrong",
        )

    # Why we verifed Password and User at same time
    ## Security: merge checks to prevent user enumeration attacks
    # by returning the same error for both "user Not found" and "wrong password",
    # we hide valid emails from attackers, forcing them to guess blindly

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 'sub' (Subject) is the standard field for the user ID/Email in a token
    token = create_token(data={"sub": user.email}, expires_in=access_token_expires)

    raw_refresh_token = create_refresh_token()
    hashed_refresh_token = hash_refresh_token(raw_refresh_token)
    refresh_token_expiry = get_refresh_token_expiry()

    new_token = RefreshToken(
        user_id=user.id,
        hashed_token=hashed_refresh_token,
        expires_at=refresh_token_expiry,
    )
    db.add(new_token)
    await db.commit()
    await db.refresh(new_token)
    return {
        "access_token": token,
        "refresh_token": raw_refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh_token(
    db: DbSessionDep,
    request: RefreshRequest,
):
    hashed_token = hash_refresh_token(request.refresh_token)

    # lets try to find the token
    query = select(RefreshToken).where(RefreshToken.hashed_token == hashed_token)
    token_obj = (await db.execute(query)).scalar_one_or_none()

    # token is not found, possible reuse atack
    if token_obj is None:
        # we simply reject
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # check if expired
    if token_obj.expires_at < datetime.now(timezone.utc):

        await db.delete(token_obj)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Load user
    user_query = select(User).where(User.id == token_obj.user_id)
    user = (await db.execute(user_query)).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    await db.delete(token_obj)

    # Generate new tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_token(
        data={"sub": user.email}, expires_in=access_token_expires
    )

    raw_refresh_token = create_refresh_token()
    hashed_refresh = hash_refresh_token(raw_refresh_token)
    expiry = get_refresh_token_expiry()

    new_refresh_obj = RefreshToken(
        user_id=user.id,
        hashed_token=hashed_refresh,
        expires_at=expiry,
    )

    db.add(new_refresh_obj)
    await db.commit()
    # await db.refresh(new_refresh_obj) .. not needed, only needed if we want to return back db-generated values

    return {
        "access_token": new_access_token,
        "refresh_token": raw_refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    db: DbSessionDep,
    request: LogoutRequest,
):
    hashed_token = hash_refresh_token(request.refresh_token)

    query = select(RefreshToken).where(RefreshToken.hashed_token == hashed_token)
    result = await db.execute(query)
    token_obj = result.scalar_one_or_none()

    if token_obj:
        await db.delete(token_obj)
        await db.commit()

    return {"message": "Logged out successfully"}
