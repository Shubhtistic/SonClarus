import logging
from pathlib import Path

from sonclarus_ml.transcribe.schemas import TranscribeSegment

logger = logging.getLogger(__name__)


def postprocess(
    raw_segments: list[dict],
    output_path: str,
    include_speaker_labels: bool = True,
) -> tuple[list[TranscribeSegment], str]:
    """Clean up raw transcription segments and write the transcript file.

    Args:
        raw_segments: List of dicts with keys ``speaker``, ``start``,
            ``end``, ``text`` (as returned by the Whisper model).
        output_path: Path to write the full transcript text.
        include_speaker_labels: Include track labels when combining separated
            speaker transcripts. A single audio file is written without labels.

    Returns:
        (sorted_segments, full_text)
    """
    # Filter out empty / whitespace-only segments
    segments = [
        TranscribeSegment(**s) for s in raw_segments if s.get("text", "").strip()
    ]
    # Sort by start time
    segments.sort(key=lambda s: s.start)

    # Build human-readable transcript
    lines = []
    for segment in segments:
        speaker = f"{segment.speaker}: " if include_speaker_labels else ""
        lines.append(
            f"[{segment.start:.2f} -> {segment.end:.2f}] " f"{speaker}{segment.text}"
        )
    full_text = "\n".join(lines)

    Path(output_path).write_text(full_text, encoding="utf-8")
    logger.info(
        "Transcript saved: %s (%d segments, %d chars)",
        output_path,
        len(segments),
        len(full_text),
    )
    return segments, full_text
