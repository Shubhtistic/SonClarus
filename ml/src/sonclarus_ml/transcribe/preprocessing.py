import logging
from pathlib import Path

from sonclarus_ml.shared.exceptions import AudioValidationError

logger = logging.getLogger(__name__)


def validate_input_paths(paths: list[str]) -> list[Path]:
    """Validate that every path in *paths* exists and is a non-empty file."""
    validated: list[Path] = []
    for p in paths:
        path = Path(p).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Input audio not found: {path}")
        if path.is_dir():
            raise IsADirectoryError(f"Expected a file, got a directory: {path}")
        if not path.read_bytes():
            raise ValueError(f"Input audio is empty: {path}")
        validated.append(path)
    return validated


def ensure_output_dir(output_folder: str) -> Path:
    p = Path(output_folder).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p
