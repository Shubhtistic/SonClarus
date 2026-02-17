from datetime import datetime, timedelta, timezone
from uuid import uuid4
import hashlib


def create_refresh_token() -> str:
    """creates a raw valued uuid refresh token,
    this is sent to user"""

    return str(uuid4())


def get_refresh_token_expiry(num_days: int = 7):
    """token expiry, 7 days by default"""

    return datetime.now(timezone.utc) + timedelta(days=num_days)


def hash_refresh_token(token: str) -> str:
    """hash the token to store in our db"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
