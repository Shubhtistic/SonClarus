from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Response

from src.sonclarus.shared.database import DbSessionDep
from src.sonclarus.shared.responses import ApiResponse
from src.sonclarus.users.exceptions import UserAlreadyExistsError

from .dependencies import OptionalUserDep
from .services import AuthService
from .schemas import SignupRequest, LoginRequest
from .exceptions import (
    InvalidCredentialsError,
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenRevokedError,
    SessionWindowExceededError,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_PATH = "/auth"


@router.post("/signup")
async def signup(payload: SignupRequest, db_session: DbSessionDep):
    try:
        access_token, raw_refresh_token = await AuthService.signup(
            db_session=db_session, signup_data=payload.model_dump()
        )
    except UserAlreadyExistsError:
        return ApiResponse.error(message="Email already registered", code=409)

    response = ApiResponse.success(
        message="Signup successful",
        data={"access_token": access_token},
        code=201,
    )
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        max_age=90 * 24 * 60 * 60,
    )
    return response


@router.post("/login")
async def login(payload: LoginRequest, db_session: DbSessionDep):
    try:
        access_token, raw_refresh_token = await AuthService.login(
            db_session=db_session,
            email=payload.email,
            plain_password=payload.password,
        )
    except InvalidCredentialsError:
        return ApiResponse.error(message="Invalid email or password", code=401)

    response = ApiResponse.success(
        message="Login successful", data={"access_token": access_token}
    )
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        max_age=90 * 24 * 60 * 60,
    )
    return response


@router.post("/refresh")
async def refresh(
    response: Response,
    db_session: DbSessionDep,
    refresh_token: Optional[str] = Cookie(default=None, alias="refresh_token"),
):
    if refresh_token is None:
        return ApiResponse.error(message="No refresh token provided", code=401)

    try:
        access_token, new_raw_refresh_token, max_window_limit = (
            await AuthService.refresh(
                db_session=db_session, raw_refresh_token=refresh_token
            )
        )
    except (
        RefreshTokenNotFoundError,
        RefreshTokenRevokedError,
        SessionWindowExceededError,
        RefreshTokenExpiredError,
    ):
        response = ApiResponse.error(
            message="Session expired, please log in again", code=401
        )
        response.delete_cookie(key="refresh_token", path=REFRESH_COOKIE_PATH)
        return response

    remaining_seconds = int(
        (max_window_limit - datetime.now(timezone.utc)).total_seconds()
    )

    remaining_seconds = max(remaining_seconds, 0)

    response = ApiResponse.success(
        message="Token refreshed", data={"access_token": access_token}
    )
    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        max_age=remaining_seconds,
    )
    return response


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    db_session: DbSessionDep,
    optional_user_data: OptionalUserDep,
    refresh_token: Optional[str] = Cookie(default=None, alias="refresh_token"),
):
    if refresh_token:
        response.delete_cookie(key="refresh_token", path=REFRESH_COOKIE_PATH)

    jti = optional_user_data.get("jti")
    exp = optional_user_data.get("exp")
    ttl_seconds = exp - int(datetime.now(timezone.utc).timestamp()) if exp else None

    await AuthService.logout(
        db_session=db_session,
        raw_refresh_token=refresh_token,
        jti=jti,
        ttl_seconds=ttl_seconds,
    )
    return Response(status_code=204, headers=response.headers)
