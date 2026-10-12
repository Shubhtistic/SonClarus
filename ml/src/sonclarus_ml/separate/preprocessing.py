import logging
from pathlib import Path

import torch
import torchaudio

from sonclarus_ml.shared.config import SeparateSettings
from sonclarus_ml.shared.exceptions import AudioValidationError

logger = logging.getLogger(__name__)


def validate_input(audio_path: str) -> Path:
    """Validate that *audio_path* exists and is a non-empty audio file."""
    p = Path(audio_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Input audio not found: {p}")
    if p.is_dir():
        raise IsADirectoryError(f"Expected a file, got a directory: {p}")
    if not p.read_bytes():
        raise ValueError(f"Input audio is empty: {p}")
    return p


def preprocess_audio(
    audio_path: Path, config: SeparateSettings
) -> tuple[torch.Tensor, int]:
    """Load, resample to 8 kHz, and downmix to mono.

    SepFormer expects 8 kHz single-channel audio.  This function handles
    all necessary conversions.

    Returns:
        (audio_tensor, original_sample_rate)
        audio_tensor has shape [1, T].
    """
    audio, orig_sr = torchaudio.load(str(audio_path))

    # Resample to 8 kHz if needed
    target_sr = config.sample_rate
    if orig_sr != target_sr:
        logger.info("Resampling from %d Hz to %d Hz", orig_sr, target_sr)
        audio = torchaudio.functional.resample(
            audio, orig_freq=orig_sr, new_freq=target_sr
        )

    # Downmix to mono
    if audio.shape[0] > 1:
        logger.info("Downmixing %d-channel audio to mono", audio.shape[0])
        audio = torch.mean(audio, dim=0, keepdim=True)
    elif audio.shape[0] == 0:
        raise AudioValidationError("Audio tensor has zero channels after processing")

    if audio.numel() == 0:
        raise AudioValidationError("Processed audio tensor is empty")

    return audio, target_sr


def ensure_output_dir(output_folder: str) -> Path:
    p = Path(output_folder).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p
