class PipelineError(Exception):
    """Base exception for all pipeline-stage errors."""


class ModelLoadError(PipelineError):
    """Raised when a model fails to load."""


class AudioValidationError(PipelineError):
    """Raised when input audio fails validation."""


class InferenceError(PipelineError):
    """Raised when an inference stage fails during execution."""


class ExternalAPICallError(PipelineError):
    """Raised when an external API call (e.g. Gemini) fails."""


class KafkaNotStartedError(RuntimeError):
    """send_job() was called before start() (or after stop())."""


class KafkaPublishError(RuntimeError):
    """A message could not be delivered to Kafka."""
