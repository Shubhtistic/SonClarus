from passlib.context import CryptContext

pass_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # hashes the password

    return pass_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pass_context.verify(password, hashed_password)
