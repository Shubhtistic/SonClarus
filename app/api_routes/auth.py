from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, status, HTTPException, Depends
from app.dependancies.redis_blacklist import add_jti_to_blacklist
from app.schemas.user_schema import RegisterUser, UserRead

from app.dependancies.db_dependancy import DbSessionDep  # async db session
from app.schemas.user_auth import RefreshRequest, LogoutRequest
from app.db.db_models import User, RefreshToken  # user table defn

from app.core.security import decode_token, hash_password, verify_password, create_token
from sqlalchemy import select, delete, join
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
    query = select(1).where(User.email == normalized_email)
    # existence check -> returns 1 if email exists

    existing_user = (await db.execute(query)).scalar_one_or_none()

    if existing_user:  # if present
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The User With this Email Already Exists.",
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
    query = select(User.hashed_password, User.id, User.is_active).where(
        User.email == normalized_email
    )

    user = (await db.execute(query)).one_or_none()

    # either user will have rows or entire user oobject will be None

    # if user object itself is None -> one_or_none() function
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User Or Password is wrong",
        )

    # check if banned
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are Banned :)"
        )

    # check if password is correct
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User Or Password is wrong",
        )

    # why we gave same 401 message for both invalid user and wrong password
    # prevents enumeration attack -> prevents attackers from knowing if specific account exists
    # because if they know that a account exists then their only work remaining is to figure out password
    # but by returning either user/password is wrong prevents enumeration attack
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 'sub' (Subject) is the standard field for the user ID/Email in a token
    token = create_token(data={"sub": str(user.id)}, expires_in=access_token_expires)

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
async def refresh(
    db: DbSessionDep,
    request: RefreshRequest,
):
    hashed_token = hash_refresh_token(request.refresh_token)

    # lets try to find the token and related user also in a single query
    # lets use join
    # join refresh token with user table if any info is there we can say refresh token is related to user
    qry = (
        select(
            User.is_active,
            RefreshToken.user_id,
            RefreshToken.revoked,
            RefreshToken.expires_at,
        )
        .join(User, User.id == RefreshToken.user_id)
        .where(RefreshToken.hashed_token == hashed_token)
    )

    res = (await db.execute(qry)).one_or_none()

    # what if there was no such refresh token -> possible reuse attack
    if res is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your Login credentials are invalid, Please Login Again",
        )
    # check if user is banned or refresh token is banned or refresh token is expired
    if (
        (res.revoked)
        or (not res.is_active)
        or (res.expires_at < datetime.now(timezone.utc))
    ):
        # remove this suspicious token
        del_qry = delete(RefreshToken).where(RefreshToken.hashed_token == hashed_token)
        await db.execute(del_qry)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Banned/Expired token or banned user",
        )

    # the token was valid lets delete it to issue new tokens

    del_qry = delete(RefreshToken).where(RefreshToken.hashed_token == hashed_token)
    await db.execute(del_qry)
    await db.commit()

    # Generate new tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_token(
        data={"sub": str(res.user_id)}, expires_in=access_token_expires
    )

    raw_refresh_token = create_refresh_token()
    hashed_refresh = hash_refresh_token(raw_refresh_token)
    expiry = get_refresh_token_expiry()

    new_refresh_obj = RefreshToken(
        user_id=res.user_id,
        hashed_token=hashed_refresh,
        expires_at=expiry,
    )

    db.add(new_refresh_obj)
    await db.commit()

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
    refresh_token = request.refresh_token
    access_token = request.access_token

    # big bug fix -> what if access token was expired, so we never reach to deleting the refresh token

    try:
        payload = decode_token(access_token)
        # if any error internally raises 401
        exp = payload.get("exp")  # unix timestamp
        jti = payload.get("jti")
        await add_jti_to_blacklist(jti=jti, exp=exp)
    except HTTPException:
        pass
        # proceed to delete the refresh token

    # use a single query to delete the refresh token, if it exists gets deleted

    hashed_refresh_token = hash_refresh_token(refresh_token)

    del_qry = delete(RefreshToken).where(
        RefreshToken.hashed_token == hashed_refresh_token
    )
    await db.execute(del_qry)
    await db.commit()
    return {"message": "You are logged out Successfully"}
