import gc
import logging
from pathlib import Path

import torch
import torchaudio
from speechbrain.inference.separation import SepformerSeparation
from sonclarus_ml.separate.preprocessing import (
    ensure_output_dir,
    preprocess_audio,
    validate_input,
)
from sonclarus_ml.shared.exceptions import (
    AudioValidationError,
    InferenceError,
    ModelLoadError,
)
from sonclarus_ml.shared.config import SeparateSettings, get_settings

logger = logging.getLogger(__name__)

# Module-level cache
_model_cache: dict[str, object] = {}


def _load_model(config: SeparateSettings) -> object:
    """Load (or return cached) the SepFormer model."""
    cache_key = config.source
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    device = config.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    logger.info("Loading SepFormer model from %s on %s", config.source, device)
    try:
        model = SepformerSeparation.from_hparams(
            source=config.source,
            savedir=config.savedir,
            run_opts={"device": device},
        )
    except Exception as exc:
        raise ModelLoadError(f"Failed to load SepFormer model: {exc}") from exc

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
    """Run SepFormer source separation on *input_path*.

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

    device = torch.device(
        config.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    )

    # --- Load model ---
    try:
        model = _load_model(config)
    except ModelLoadError:
        raise
    except Exception as exc:
        raise ModelLoadError(str(exc)) from exc

    # --- Chunk & separate ---
    chunk_size = config.chunk_samples
    chunks = torch.split(audio, chunk_size, dim=1)
    speaker_1_chunks: list[torch.Tensor] = []
    speaker_2_chunks: list[torch.Tensor] = []

    try:
        for chunk in chunks:
            chunk_t = chunk.to(device)
            sources = None
            try:
                sources = model.separate_batch(chunk_t)
                # sources: [1, T, 2]
                speaker_1_chunks.append(sources[0, :, 0].detach().cpu())
                speaker_2_chunks.append(sources[0, :, 1].detach().cpu())
            finally:
                del chunk_t
                if sources is not None:
                    del sources
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
    except Exception as exc:
        raise InferenceError(f"Separation failed: {exc}") from exc

    if not speaker_1_chunks:
        raise InferenceError("No audio chunks were processed")

    # --- Stitch & save ---
    speaker_1_full = None
    speaker_2_full = None
    try:
        speaker_1_full = torch.cat(speaker_1_chunks, dim=0).unsqueeze(0)
        speaker_2_full = torch.cat(speaker_2_chunks, dim=0).unsqueeze(0)

        file_name = audio_path.stem
        out_path_1 = out_dir / f"{file_name}_speaker_1.wav"
        out_path_2 = out_dir / f"{file_name}_speaker_2.wav"

        torchaudio.save(str(out_path_1), speaker_1_full, sample_rate=config.sample_rate)
        torchaudio.save(str(out_path_2), speaker_2_full, sample_rate=config.sample_rate)

        out_paths = [str(out_path_1), str(out_path_2)]
    except Exception as exc:
        raise InferenceError(f"Failed to save separated audio: {exc}") from exc
    finally:
        del audio
        if speaker_1_full is not None:
            del speaker_1_full
        if speaker_2_full is not None:
            del speaker_2_full
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # --- Result ---
    return {
        "output_paths": out_paths,
        "input_path": str(audio_path),
        "sample_rate": config.sample_rate,
    }
