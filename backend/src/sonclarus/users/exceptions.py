class UserAlreadyExistsError(Exception):
    """raise when user already exists on new user creation"""

    def __init__(self, email: str):
        self.email = email


class UserNotFoundError(Exception):
    """when user not found during log in"""

    def __init__(self, identifier: str):
        self.identifier = identifier


class StorageQuotaExceededError(Exception):
    """raise when storage limits exceed"""

    def __init__(self, user_id, current_usage: int, limit: int):
        self.user_id = user_id
        self.current_usage = current_usage
        self.limit = limit
