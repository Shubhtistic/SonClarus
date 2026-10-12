import logging
from google import genai
from google.genai import types

from sonclarus_ml.shared.config import GeminiSettings, get_settings
from sonclarus_ml.shared.exceptions import ExternalAPICallError, PipelineError

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _ensure_configured(config: GeminiSettings) -> None:
    """Create the Gemini client once so requests can reuse its connection."""
    global _client
    if _client is not None:
        return
    if not config.api_key.get_secret_value():
        raise PipelineError(
            "Environment variable GEMINI_API_KEY is not set. "
            "Set it before calling run_summarization."
        )
    try:
        _client = genai.Client(
            api_key=config.api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=config.timeout_seconds * 1000),
        )
        logger.info("Google Generative AI configured with model: %s", config.model_name)
    except Exception as exc:
        raise PipelineError(f"Failed to configure Gemini SDK: {exc}") from exc


_PROMPT_TEMPLATE = """\
Below is a transcript of an audio conversation.
Please provide a professional, single-paragraph synopsis (approx. 100-150 words).
Identify the main participants, the primary topics discussed, and the final
resolution or conclusion of the talk.

Write it in a clean, descriptive style. Do not use bullet points.

TRANSCRIPT:
{transcript}
"""


def run_summarization(full_transcript_text: str) -> dict:
    """Summarise *full_transcript_text* using the Gemini API.

    Args:
        full_transcript_text: The complete transcript to summarise.

    Returns:
        Dict with keys ``summary`` and ``model``.

    Raises:
        PipelineError: if the API key is missing or the request fails.
        ExternalAPICallError: if the Gemini API returns an error response.
    """
    config = get_settings().gemini

    if not full_transcript_text.strip():
        raise PipelineError("No transcript content available to summarize.")

    _ensure_configured(config)
    client = _client
    if client is None:
        raise PipelineError("Gemini client was not initialized.")

    prompt = _PROMPT_TEMPLATE.format(transcript=full_transcript_text)
    logger.info("Sending summarization request to %s", config.model_name)

    try:
        response = client.models.generate_content(
            model=config.model_name,
            contents=prompt,
        )
    except Exception as exc:
        raise ExternalAPICallError(f"Summarization API call failed: {exc}") from exc

    if response is None or not response.text:
        # Check for error details in the response
        error_detail = getattr(response, "error", None) or getattr(
            response, "prompt_feedback", None
        )
        msg = "Summarization returned an empty response."
        if error_detail:
            msg += f" Error detail: {error_detail}"
        raise ExternalAPICallError(msg)

    summary = response.text.strip()
    logger.info("Summarization complete (%d chars)", len(summary))
    return {
        "summary": summary,
        "model": config.model_name,
    }
