class InvalidCredentialsError(Exception):
    """raise when email/password combination is wrong during login"""

    def __init__(self, email: str):
        self.email = email


class InvalidTokenError(Exception):
    """raise when a token fails signature/expiry verification, or is blacklisted/revoked"""


class UnexpectedJwtError(Exception):
    """catch all error for jwt"""


class ExpiredSignatureError(Exception):
    """expired jwt signature"""


class RefreshTokenNotFoundError(Exception):
    """raise when a refresh token is not found"""


class RefreshTokenRevokedError(Exception):
    """raise when a token is revoked"""


class SessionWindowExceededError(Exception):
    """When session window expired"""


class RefreshTokenExpiredError(Exception):
    """when the token is expired"""
