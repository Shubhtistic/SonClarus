import asyncio
import contextlib
import logging
import orjson
from collections.abc import Mapping
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaError
from aiokafka.helpers import create_ssl_context

from sonclarus_ml.shared.config import get_settings
from sonclarus_ml.shared.exceptions import KafkaNotStartedError, KafkaPublishError

# Kafka producer
_producer: AIOKafkaProducer | None = None
_lifecycle_lock = asyncio.Lock()

logger = logging.getLogger(__name__)

# --- settings ---
settings = get_settings()


class KafkaProducer:
    @staticmethod
    async def start() -> None:
        """Start the producer."""

        global _producer

        async with _lifecycle_lock:
            if _producer is not None:
                return

            protocol = settings.kafka.security_protocol

            config: dict[str, Any] = {
                "bootstrap_servers": settings.kafka.bootstrap_servers,
                "client_id": settings.kafka.client_id,
                "acks": "all",
                "enable_idempotence": True,
                "compression_type": "gzip",
                "linger_ms": 5,
                "request_timeout_ms": settings.kafka.request_timeout_ms,
                "security_protocol": protocol,
            }

            if protocol == "PLAINTEXT":
                pass
            elif protocol == "SASL_SSL":
                config["ssl_context"] = create_ssl_context()
                config["sasl_mechanism"] = settings.kafka.sasl_mechanism
                config["sasl_plain_username"] = settings.kafka.sasl_username
                config["sasl_plain_password"] = (
                    settings.kafka.sasl_password.get_secret_value()
                )

            last_error: Exception | None = None
            for attempt in range(1, settings.kafka.start_max_attempts + 1):
                producer = AIOKafkaProducer(**config)
                try:
                    await producer.start()
                except (KafkaConnectionError, KafkaError, OSError) as exc:
                    last_error = exc

                    with contextlib.suppress(Exception):
                        await producer.stop()

                    if attempt == settings.kafka.start_max_attempts:
                        break

                    delay = min(2**attempt, 30)

                    logger.warning(
                        "Kafka start failed (attempt %d/%d): %s. Retrying in %ds",
                        attempt,
                        settings.kafka.start_max_attempts,
                        exc,
                        delay,
                    )

                    await asyncio.sleep(delay)
                    continue

                _producer = producer
                logger.info(
                    "Kafka producer started (servers=%s)",
                    settings.kafka.bootstrap_servers,
                )
                return

            raise KafkaPublishError(
                f"Could not connect to Kafka after "
                f"{settings.kafka.start_max_attempts} attempts"
            ) from last_error

    @staticmethod
    async def stop() -> None:
        """Flush pending messages and close the producer."""
        global _producer

        async with _lifecycle_lock:
            producer, _producer = _producer, None
            if producer is None:
                return
            try:
                await asyncio.wait_for(producer.stop(), timeout=10)
            except Exception as exc:  # shutdown must never raise
                logger.warning("Error while stopping Kafka producer: %s", exc)
            logger.info("Kafka producer stopped")

    @staticmethod
    async def send_job(
        payload: Mapping[str, Any],
        topic: str,
        partition: int | None = None,
    ) -> dict[str, Any]:
        """Serialize and publish a payload; return its Kafka location."""

        producer = _producer
        if producer is None:
            raise KafkaNotStartedError("Kafka producer is not started")

        try:
            value = orjson.dumps(payload, option=orjson.OPT_NON_STR_KEYS)
        except orjson.JSONEncodeError as exc:
            raise KafkaPublishError(f"Payload is not serializable: {exc}") from exc

        job_id = payload.get("job_id")
        key = str(job_id).encode("utf-8")

        try:
            metadata = await asyncio.wait_for(
                producer.send_and_wait(
                    topic=topic,
                    value=value,
                    key=key,
                    partition=partition,
                ),
                timeout=settings.kafka.send_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            logger.error("Kafka send timed out (job_id=%s)", job_id)
            raise KafkaPublishError("Timed out publishing to Kafka") from exc
        except KafkaError as exc:
            logger.error("Kafka send failed (job_id=%s): %s", job_id, exc)
            raise KafkaPublishError(f"Kafka publish failed: {exc}") from exc

        logger.info(
            "Message published (job_id=%s topic=%s partition=%d offset=%d)",
            job_id,
            metadata.topic,
            metadata.partition,
            metadata.offset,
        )
        return {
            "topic": metadata.topic,
            "partition": metadata.partition,
            "offset": metadata.offset,
        }
