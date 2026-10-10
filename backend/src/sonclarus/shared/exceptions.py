class KafkaNotStartedError(RuntimeError):
    """send_job() was called before start() (or after stop())."""


class KafkaPublishError(RuntimeError):
    """A message could not be delivered to Kafka."""
