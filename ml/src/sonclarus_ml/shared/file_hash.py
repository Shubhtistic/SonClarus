import hashlib
from pathlib import Path

# how much of the file is read into memory at a time
HASH_CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MiB


def compute_file_hash(file_path: str | Path) -> str:
    """SHA-256 hash of a file, read chunk by chunk so it stays out of memory.

    Returns the digest as 64 lowercase hex characters.
    """
    hasher = hashlib.sha256()

    with open(file_path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE_BYTES):
            hasher.update(chunk)

    return hasher.hexdigest()
