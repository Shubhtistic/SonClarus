import time
from uuid import uuid7

import jwt as pyjwt

from src.sonclarus.shared.config import get_settings
from .exceptions import ExpiredSignatureError, InvalidTokenError, UnexpectedJwtError


def create_access_token(user_id: str) -> str:
    """Create an access token carrying user_id claim."""

    settings = get_settings()
    jti = str(uuid7())
    expiry = int(time.time()) + settings.jwt.access_token_expire_minutes * 60

    payload = {
        "user_id": str(user_id),
        "exp": expiry,
        "jti": jti,
    }

    access_token = pyjwt.encode(
        payload,
        settings.jwt.secret_key,
        algorithm=settings.jwt.algorithm,
    )
    return access_token


def decode_and_verify_token(token: str) -> dict:
    """Decode and verify a JWT. Raises on invalid/expired/malformed tokens."""
    settings = get_settings()
    try:
        return pyjwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm],
        )
    except pyjwt.ExpiredSignatureError:
        raise ExpiredSignatureError
    except pyjwt.InvalidTokenError:
        raise InvalidTokenError
    except pyjwt.PyJWTError:
        raise UnexpectedJwtError
