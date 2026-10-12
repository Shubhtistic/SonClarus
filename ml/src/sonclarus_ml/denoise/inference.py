import gc # gc -> cleanup objects no lonfer in us
import logging
from df.enhance import enhance, init_df # enhance -> run noise reduction, init_df -> load the model
from df.io import load_audio, save_audio # read an audio file to tensor and write an audio tensor to file
from pathlib import Path

import torch
from sonclarus_ml.denoise.preprocessing import ensure_output_dir, validate_input
from sonclarus_ml.shared.exceptions import (
    AudioValidationError,
    InferenceError,
    ModelLoadError,
)
from sonclarus_ml.shared.config import DenoiseSettings, get_settings




logger = logging.getLogger(__name__)

# Module-level cache so we don't reload the model on every call.
_model_cache: dict[str, tuple] = {}


def _load_model(config: DenoiseSettings) -> tuple:
    """Load (or return cached) the DeepFilterNet model and state.

    Returns:
        (model, df_state, suffix) as returned by init_df.
    """
    cache_key = config.model_name
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    model_dir = config.model_dir or config.model_name
    logger.info("Loading DeepFilterNet model: %s", model_dir)
    try:
        model, df_state, suffix = init_df(
            model_base_dir=model_dir,
            post_filter=config.post_filter,
            log_level=config.log_level,
            config_allow_defaults=True,
        )
    except Exception as exc:
        raise ModelLoadError(f"Failed to load DeepFilterNet model: {exc}") from exc

    _model_cache[cache_key] = (model, df_state, suffix)
    return model, df_state, suffix


def _cleanup_cache() -> None:
    """Explicitly free the cached model (call at pipeline exit)."""
    global _model_cache
    _model_cache.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# no_grad() -> dont track gradients, useful when training a model
@torch.no_grad()
def run_denoise(
    input_path: str,
    output_folder: str | Path,
    atten_lim_db: float | None = None,
) -> dict:
    """Run DeepFilterNet denoising on *input_path* and save the result.

    Args:
        input_path: Path to the noisy audio file.
        output_folder: Directory where the cleaned WAV is written.
        atten_lim_db: Optional noise attenuation limit in dB.

    Returns:
        Dict with keys ``output_path``, ``model``, ``sample_rate``.

    Raises:
        AudioValidationError: if the input audio is invalid.
        InferenceError: if denoising fails.
        ModelLoadError: if the model cannot be loaded.
    """
    config = get_settings().denoise
    if atten_lim_db is not None:
        config = config.model_copy(update={"atten_lim_db": atten_lim_db})

    # --- Validate ---
    try:
        audio_path = validate_input(input_path)
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        raise AudioValidationError(str(exc)) from exc

    out_dir = ensure_output_dir(str(output_folder))

    # --- Load model ---
    try:
        model, df_state, suffix = _load_model(config)
    except ModelLoadError:
        raise
    except Exception as exc:
        raise ModelLoadError(str(exc)) from exc

    # --- Load audio ---
    try:
        audio, info = load_audio(str(audio_path), sr=df_state.sr())
    except Exception as exc:
        raise AudioValidationError(f"Failed to load audio: {exc}") from exc

    if audio.numel() == 0:
        raise AudioValidationError("Loaded audio tensor is empty")

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    # --- Inference ---
    try:
        enhanced = enhance(
            model=model,
            df_state=df_state,
            audio=audio.to(device),
            pad=True,
            atten_lim_db=config.atten_lim_db,
        )
    except Exception as exc:
        raise InferenceError(f"Enhancement failed: {exc}") from exc

    # --- Save ---
    try:
        out_name = f"{audio_path.stem}_cleaned.wav"
        out_path = out_dir / out_name
        save_audio(str(out_path), enhanced.cpu(), df_state.sr())
    except Exception as exc:
        raise InferenceError(f"Failed to save audio: {exc}") from exc

    # --- Result ---
    return {
        "output_path": str(out_path.resolve()),
        "model": config.model_name,
        "sample_rate": df_state.sr(),
    }
