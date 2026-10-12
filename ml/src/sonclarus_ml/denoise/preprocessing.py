from pathlib import Path


def validate_input(audio_path: str) -> Path:
    """Validate that *audio_path* exists and is readable.

    Returns:
        Resolved Path object.

    Raises:
        FileNotFoundError: if the path does not exist.
        IsADirectoryError: if the path points to a directory.
    """
    p = Path(audio_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Input audio not found: {p}")
    if p.is_dir():
        raise IsADirectoryError(f"Expected a file, got a directory: {p}")
    if not p.read_bytes():
        raise ValueError(f"Input audio is empty: {p}")
    return p


def ensure_output_dir(output_folder: str) -> Path:
    """Create the output directory if it does not exist.

    Returns:
        Resolved Path object for the output folder.
    """
    p = Path(output_folder).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p
