import gc
import logging
import re
from pathlib import Path

import torch
from faster_whisper import WhisperModel
from sonclarus_ml.shared.exceptions import (
    AudioValidationError,
    InferenceError,
    ModelLoadError,
)
from sonclarus_ml.transcribe.postprocessing import postprocess
from sonclarus_ml.transcribe.preprocessing import (
    ensure_output_dir,
    validate_input_paths,
)
from sonclarus_ml.shared.config import TranscribeSettings, get_settings

logger = logging.getLogger(__name__)

# Module-level cache: model_size -> WhisperModel instance
_model_cache: dict[str, object] = {}


def _load_model(config: TranscribeSettings) -> object:
    """Load (or return cached) the WhisperModel."""
    cache_key = config.model_size
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    device = config.device or ("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(
        "Loading WhisperModel %s on %s with compute_type=%s",
        config.model_size,
        device,
        config.compute_type,
    )
    try:
        model = WhisperModel(
            config.model_size,
            device=device,
            compute_type=config.compute_type,
        )
    except Exception as exc:
        raise ModelLoadError(f"Failed to load WhisperModel: {exc}") from exc

    _model_cache[cache_key] = model
    return model


def _cleanup_cache() -> None:
    global _model_cache
    _model_cache.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def run_transcription(
    input_paths: list[str] | str,
    output_folder: str | Path,
    vad_filter: bool | None = None,
    vad_min_silence_duration_ms: int | None = None,
) -> dict:
    """Transcribe one or more audio files with Faster-Whisper.

    Args:
        input_paths: Single path string or list of paths. Each path is
            treated as a separate speaker track.
        output_folder: Directory where the transcript text file is saved.
        vad_filter: Override the config's VAD setting.
        vad_min_silence_duration_ms: Override the config's VAD silence threshold.

    Returns:
        Dict with keys ``segments``, ``full_text``, ``output_path``.

    Raises:
        AudioValidationError: if any input path is invalid.
        InferenceError: if transcription fails.
        ModelLoadError: if the model cannot be loaded.
    """
    config = get_settings().transcribe
    overrides = {}
    if vad_filter is not None:
        overrides["vad_filter"] = vad_filter
    if vad_min_silence_duration_ms is not None:
        overrides["vad_min_silence_duration_ms"] = vad_min_silence_duration_ms
    if overrides:
        config = config.model_copy(update=overrides)

    # Normalise to list
    if isinstance(input_paths, str):
        paths = [input_paths]
    else:
        paths = input_paths

    # --- Validate ---
    try:
        validated = validate_input_paths(paths)
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        raise AudioValidationError(str(exc)) from exc

    out_dir = ensure_output_dir(str(output_folder))

    # --- Load model ---
    try:
        model = _load_model(config)
    except ModelLoadError:
        raise
    except Exception as exc:
        raise ModelLoadError(str(exc)) from exc

    # Separate-stage jobs pass one audio track for each speaker. Keep their
    # transcripts together and label each track so the source stays clear.
    has_separated_tracks = len(validated) > 1
    if has_separated_tracks:
        logger.info(
            "Transcribing %d separated tracks into one transcript", len(validated)
        )
    else:
        logger.info("Transcribing one audio file without speaker labels")

    # --- Transcribe each file ---
    all_segments: list[dict] = []
    try:
        for idx, audio_path in enumerate(validated):
            speaker_label = f"Speaker {idx + 1}"
            if has_separated_tracks:
                logger.info(
                    "Transcribing track %d/%d (%s) as %s",
                    idx + 1,
                    len(validated),
                    audio_path.name,
                    speaker_label,
                )
            else:
                logger.info("Transcribing audio file: %s", audio_path.name)

            vad_params = None
            if config.vad_filter:
                vad_params = {
                    "min_silence_duration_ms": config.vad_min_silence_duration_ms,
                }

            try:
                segments_gen, info = model.transcribe(
                    str(audio_path),
                    beam_size=config.beam_size,
                    vad_filter=config.vad_filter,
                    vad_parameters=vad_params,
                )
                # Materialise the generator so we can iterate safely
                segments = list(segments_gen)
                logger.info(
                    "Detected language: %s (prob %.2f), %d segments",
                    info.language,
                    info.language_probability,
                    len(segments),
                )
            except Exception as exc:
                raise InferenceError(
                    f"Transcription failed for {audio_path}: {exc}"
                ) from exc

            for seg in segments:
                text = seg.text.strip()
                if text:
                    all_segments.append(
                        {
                            "speaker": speaker_label,
                            "start": seg.start,
                            "end": seg.end,
                            "text": text,
                        }
                    )
    finally:
        # Only clean up cache if we're done (caller decides when to call _cleanup_cache)
        pass

    if not all_segments:
        logger.warning("Transcription produced no non-empty segments")

    # --- Post-process ---
    try:
        base_name = validated[0].stem
        if has_separated_tracks:
            base_name = re.sub(r"_speaker_\d+$", "", base_name, flags=re.IGNORECASE)
        transcript_path = out_dir / f"{base_name}_full_script.txt"
    except Exception:
        transcript_path = out_dir / "transcript_full.txt"

    try:
        segments, full_text = postprocess(
            all_segments,
            str(transcript_path),
            include_speaker_labels=has_separated_tracks,
        )
    except Exception as exc:
        raise InferenceError(f"Post-processing failed: {exc}") from exc

    return {
        "segments": segments,
        "full_text": full_text,
        "output_path": str(transcript_path),
    }
