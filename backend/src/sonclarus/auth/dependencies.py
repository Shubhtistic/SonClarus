import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.sonclarus.users.services import UserService

from .exceptions import ExpiredSignatureError, InvalidTokenError, UnexpectedJwtError
from .jwt import decode_and_verify_token
from .repository import JwtRepository

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


async def current_user_dep(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict:
    """Decode + verify JWT signature/expiry only. No DB hit."""
    try:
        claims = decode_and_verify_token(credentials.credentials)
    except ExpiredSignatureError, InvalidTokenError, UnexpectedJwtError:
        logger.warning("Bearer token rejected")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if await JwtRepository.check_jti_blacklist(claims.get("jti", "")):
        logger.warning("Bearer token is blacklisted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    return claims


async def verified_current_user_dep(
    claims: Annotated[dict, Depends(current_user_dep)],
) -> dict:
    """Verify user in DB is active and verified. Returns claims merged with live user fields."""
    raw_user_id = claims.get("user_id")
    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
        )

    try:
        user_id = UUID(raw_user_id)
    except TypeError, ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
        )

    user = await UserService.get_active_verified_user(user_id)

    if not user or not user.is_active or not user.is_verified:
        logger.warning("Verified user check failed for user_id: %s", raw_user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or not verified",
        )
    claims["storage_used"] = user.storage_used
    claims["storage_limit"] = user.storage_limit

    return claims


async def optional_current_user_dep(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(optional_bearer_scheme)
    ],
) -> dict:
    """Currently only for logout — returns empty dict if token is missing or invalid."""
    if credentials is None:
        return {}
    try:
        claims = decode_and_verify_token(credentials.credentials)
    except ExpiredSignatureError, InvalidTokenError, UnexpectedJwtError:
        logger.debug("Optional bearer token rejected")
        return {}
    return claims


CurrentUserDep = Annotated[dict, Depends(current_user_dep)]
VerifiedCurrentUserDep = Annotated[dict, Depends(verified_current_user_dep)]
OptionalUserDep = Annotated[dict, Depends(optional_current_user_dep)]
