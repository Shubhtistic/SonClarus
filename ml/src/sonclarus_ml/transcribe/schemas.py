from pydantic import BaseModel, field_validator

from sonclarus_ml.shared.utilities import reject_blank_text


class TranscribeSegment(BaseModel):
    """A single transcription segment with timing."""

    speaker: str
    start: float
    end: float
    text: str

    _validate_text = field_validator("speaker", "text", mode="before")(
        reject_blank_text
    )
