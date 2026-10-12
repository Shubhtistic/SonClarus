import logging
import sys
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
) -> None:
    """Configure the root logger with console (and optional file) handlers.

    Args:
        level: Logging verbosity – one of DEBUG, INFO, WARNING, ERROR.
        log_file: If given, also write logs to this path.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        handlers=handlers,
    )
    # Quiet noisy third-party loggers
    for quiet_name in (
        "httpx",
        "urllib3",
        "botocore",
        "boto3",
        "fsspec",
        "huggingface_hub",
        "transformers",
    ):
        logging.getLogger(quiet_name).setLevel(logging.WARNING)
