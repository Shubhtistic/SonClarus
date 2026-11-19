import gc
import logging
import os
from pathlib import Path

import numpy as np
import torch
import torchaudio
from clearvoice import ClearVoice
from sonclarus_ml.separate.preprocessing import (
    ensure_output_dir,
    preprocess_audio,
    validate_input,
)
from sonclarus_ml.infrastructure.exceptions import (
    AudioValidationError,
    InferenceError,
    ModelLoadError,
)
from sonclarus_ml.infrastructure.config import SeparateSettings, get_settings

logger = logging.getLogger(__name__)

# Module-level cache; ClearVoice keeps MossFormer2 loaded between jobs.
_model_cache: dict[str, object] = {}


def _load_model(config: SeparateSettings) -> ClearVoice:
    """Load (or return cached) the MossFormer2 model."""
    cache_key = f"{config.model_name}:{Path(config.savedir).resolve()}"
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    model_dir = Path(config.savedir).expanduser().resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Loading MossFormer2 model %s", config.model_name)
    try:
        # ClearVoice resolves its checkpoint path relative to the process CWD.
        # Use the persistent model directory during construction, then restore it.
        previous_cwd = Path.cwd()
        try:
            os.chdir(model_dir)
            model = ClearVoice(
                task="speech_separation", model_names=[config.model_name]
            )
        finally:
            os.chdir(previous_cwd)
    except Exception as exc:
        raise ModelLoadError(f"Failed to load MossFormer2 model: {exc}") from exc

    loaded_device = getattr(model.models[0], "device", "unknown")
    logger.info("MossFormer2 loaded on %s", loaded_device)

    _model_cache[cache_key] = model
    return model


def _cleanup_cache() -> None:
    global _model_cache
    _model_cache.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@torch.no_grad()
def run_separation(
    input_path: str,
    output_folder: str | Path,
) -> dict:
    """Run MossFormer2 source separation on *input_path*.

    Args:
        input_path: Path to the input audio file.
        output_folder: Directory where separated WAVs are saved.

    Returns:
        Dict with keys ``output_paths``, ``input_path``, ``sample_rate``.

    Raises:
        AudioValidationError: if the input audio is invalid.
        InferenceError: if separation fails.
        ModelLoadError: if the model cannot be loaded.
    """
    config = get_settings().separate

    # --- Validate ---
    try:
        audio_path = validate_input(input_path)
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        raise AudioValidationError(str(exc)) from exc

    out_dir = ensure_output_dir(str(output_folder))

    # --- Preprocess ---
    try:
        audio, sr = preprocess_audio(audio_path, config)
    except AudioValidationError:
        raise
    except Exception as exc:
        raise AudioValidationError(f"Failed to preprocess audio: {exc}") from exc

    # --- Load model ---
    try:
        model = _load_model(config)
    except ModelLoadError:
        raise
    except Exception as exc:
        raise ModelLoadError(str(exc)) from exc

    # ClearVoice expects [batch, samples] float32 data and returns
    # [speakers, batch, samples]. It performs its own windowed decoding.
    try:
        input_array = audio.squeeze(0).numpy().astype(np.float32, copy=False)[None, :]
        sources = np.asarray(model(input_array))
    except Exception as exc:
        raise InferenceError(f"MossFormer2 separation failed: {exc}") from exc

    if sources.ndim != 3 or sources.shape[0] != 2 or sources.shape[1] != 1:
        raise InferenceError(
            f"Unexpected MossFormer2 output shape {sources.shape}; expected [2, 1, samples]"
        )

    # --- Stitch & save ---
    try:
        file_name = audio_path.stem
        out_path_1 = out_dir / f"{file_name}_speaker_1.wav"
        out_path_2 = out_dir / f"{file_name}_speaker_2.wav"

        output_1 = torch.from_numpy(
            sources[0, 0].astype(np.float32, copy=False)
        )[None, :]
        output_2 = torch.from_numpy(
            sources[1, 0].astype(np.float32, copy=False)
        )[None, :]
        torchaudio.save(str(out_path_1), output_1, sample_rate=config.sample_rate)
        torchaudio.save(str(out_path_2), output_2, sample_rate=config.sample_rate)

        out_paths = [str(out_path_1), str(out_path_2)]
    except Exception as exc:
        raise InferenceError(f"Failed to save separated audio: {exc}") from exc
    finally:
        del audio
        if "sources" in locals():
            del sources
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # --- Result ---
    return {
        "output_paths": out_paths,
        "input_path": str(audio_path),
        "sample_rate": config.sample_rate,
    }
