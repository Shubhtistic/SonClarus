import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.sonclarus.users.services import UserService
from src.sonclarus.users.exceptions import UserNotFoundError

from . import password as auth_password
from .jwt import create_access_token
from .models import RefreshTokens
from .repository import RefreshTokenRepository, JwtRepository
from .exceptions import (
    InvalidCredentialsError,
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenRevokedError,
    SessionWindowExceededError,
)

logger = logging.getLogger(__name__)


class AuthService:
    @staticmethod
    async def signup(db_session: AsyncSession, signup_data: dict) -> tuple[str, str]:
        signup_data["hashed_password"] = auth_password.hash_password(
            signup_data.pop("password")
        )
        new_user = await UserService.create_user(
            db_session=db_session, user_data=signup_data
        )
        access_token, raw_refresh_token = await AuthService._issue_tokens(
            db_session=db_session, user_id=new_user.id
        )
        logger.info("Signup service operation succeeded")
        return access_token, raw_refresh_token

    @staticmethod
    async def login(
        db_session: AsyncSession, email: str, plain_password: str
    ) -> tuple[str, str]:
        try:
            user = await UserService.get_by_email(db_session=db_session, email=email)
        except UserNotFoundError:
            raise InvalidCredentialsError(email=email)

        if not auth_password.verify_password(plain_password, user.hashed_password):
            raise InvalidCredentialsError(email=email)

        access_token, raw_refresh_token = await AuthService._issue_tokens(
            db_session=db_session, user_id=user.id
        )
        logger.info("Login service operation succeeded")
        return access_token, raw_refresh_token

    @staticmethod
    async def refresh(
        db_session: AsyncSession, raw_refresh_token: str
    ) -> tuple[str, str, datetime]:
        """Rotate a refresh token. Returns (access_token, new_raw_refresh_token, max_window_limit)."""

        raw_refresh_token, user_id, max_window_limit = await RefreshTokenService.rotate(
            db_session=db_session, raw_refresh_token=raw_refresh_token
        )

        access_token = create_access_token(user_id=str(user_id))
        logger.info("Refresh service operation succeeded")
        return access_token, raw_refresh_token, max_window_limit

    @staticmethod
    async def logout(
        db_session: AsyncSession,
        raw_refresh_token: Optional[str] = None,
        jti: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:

        if raw_refresh_token:
            await RefreshTokenRepository.revoke(
                db_session=db_session,
                hashed_token=RefreshTokenService.hash_token(raw_refresh_token),
                revoked_at=datetime.now(timezone.utc),
            )

        if jti and ttl_seconds is not None:
            await JwtRepository.add_jti_to_blacklist(jti=jti, ttl_seconds=ttl_seconds)

        logger.info("Logout service operation completed")

    @staticmethod
    async def _issue_tokens(db_session: AsyncSession, user_id: UUID) -> tuple[str, str]:
        """Issue access + refresh token pair and persist the refresh token in DB."""

        access_token = create_access_token(str(user_id))
        raw_refresh_token = await RefreshTokenService.create(
            db_session=db_session, user_id=user_id
        )
        return access_token, raw_refresh_token


class RefreshTokenService:

    SLIDING_WINDOW = timedelta(days=7)
    MAX_SESSION_WINDOW = timedelta(days=90)

    @staticmethod
    def calculate_next_expiry(now: datetime, max_window_limit: datetime) -> datetime:
        """slide the expiry using sliding window, does not exceed max_window limit"""

        return min(now + RefreshTokenService.SLIDING_WINDOW, max_window_limit)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @staticmethod
    def generate_refresh_token() -> tuple[str, str]:
        """return raw and hashed refresh token"""
        raw_token = secrets.token_urlsafe(32)
        return raw_token, RefreshTokenService.hash_token(raw_token)

    @staticmethod
    async def create(
        db_session: AsyncSession,
        user_id: UUID,
    ) -> str:
        """create a refresh token and save in db"""

        now = datetime.now(timezone.utc)
        raw_token, token_hash = RefreshTokenService.generate_refresh_token()

        new_refresh_token = RefreshTokens(
            user_id=user_id,
            hashed_token=token_hash,
            max_window_limit=now + RefreshTokenService.MAX_SESSION_WINDOW,
            expires_at=now + RefreshTokenService.SLIDING_WINDOW,
        )

        await RefreshTokenRepository.create(
            db_session=db_session, instance=new_refresh_token
        )
        logger.debug("Refresh token created")
        return raw_token

    @staticmethod
    async def rotate(
        db_session: AsyncSession,
        raw_refresh_token: str,
    ) -> tuple[str, UUID, datetime]:
        """called when refreshing a token, if under max_session limit -> rotated"""

        now = datetime.now(timezone.utc)

        hashed_token = RefreshTokenService.hash_token(raw_refresh_token)

        existing_token = await RefreshTokenRepository.get_by_hash(
            db_session, hashed_token
        )
        if existing_token is None:
            logger.warning("Refresh token rotation rejected: token not found")
            raise RefreshTokenNotFoundError

        if existing_token.is_revoked:
            logger.warning("Refresh token rotation rejected: token revoked")
            raise RefreshTokenRevokedError

        if now >= existing_token.max_window_limit:
            logger.warning("Refresh token rotation rejected: session window exceeded")
            raise SessionWindowExceededError

        if now >= existing_token.expires_at:
            logger.warning("Refresh token rotation rejected: token expired")
            raise RefreshTokenExpiredError

        new_expires_at = RefreshTokenService.calculate_next_expiry(
            now=now,
            max_window_limit=existing_token.max_window_limit,
        )

        new_raw_token, new_hashed_token = RefreshTokenService.generate_refresh_token()

        await RefreshTokenRepository.update(
            db_session=db_session,
            token_id=existing_token.id,
            hashed_token=new_hashed_token,
            expires_at=new_expires_at,
        )
        logger.info("Refresh token rotated")
        return new_raw_token, existing_token.user_id, existing_token.max_window_limit
