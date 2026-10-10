import logging
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.sonclarus.shared.database import DbSessionDep
from src.sonclarus.users.repository import UserRepository

from .jwt import decode_and_verify_token
from .repository import JwtRepository
from .exceptions import ExpiredSignatureError, InvalidTokenError, UnexpectedJwtError

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


async def current_user_dep(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict:
    """Decode + verify JWT signature/expiry only. No DB hit."""
    try:
        claims = decode_and_verify_token(credentials.credentials)
    except (ExpiredSignatureError, InvalidTokenError, UnexpectedJwtError):
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
    db_session: DbSessionDep,
) -> dict:
    """Verify user in DB is active and verified. Returns claims merged with live user fields."""
    from uuid import UUID

    raw_user_id = claims.get("user_id")
    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
        )

    try:
        user_id = UUID(raw_user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
        )

    user = await UserRepository.get_user_by_id(user_id, db_session=db_session)

    if not user or not user.is_active or not user.is_verified:
        logger.warning("Verified user check failed for user_id: %s", raw_user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or not verified",
        )

    return claims


async def optional_current_user_dep(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(optional_bearer_scheme)
    ],
) -> dict:
    """Currently only for logout — returns empty dict if token is missing or invalid."""
    if credentials is None:
        return {}
    try:
        claims = decode_and_verify_token(credentials.credentials)
    except (ExpiredSignatureError, InvalidTokenError, UnexpectedJwtError):
        logger.debug("Optional bearer token rejected")
        return {}
    return claims


CurrentUserDep = Annotated[dict, Depends(current_user_dep)]
VerifiedCurrentUserDep = Annotated[dict, Depends(verified_current_user_dep)]
OptionalUserDep = Annotated[dict, Depends(optional_current_user_dep)]
