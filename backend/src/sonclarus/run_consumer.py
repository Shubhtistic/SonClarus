import asyncio
import logging
from contextlib import suppress

from aiokafka import AIOKafkaConsumer
from aiokafka.helpers import create_ssl_context
from aiokafka.structs import TopicPartition

from src.sonclarus.jobs.schemas import MlStageResultEvent
from src.sonclarus.jobs.services import JobService
from src.sonclarus.shared.config import get_settings
from src.sonclarus.shared.database import SessionFactory
from src.sonclarus.shared.kafka_client import KafkaProducer

logger = logging.getLogger(__name__)


async def _consume_results() -> None:
    settings = get_settings()
    kafka_settings = settings.kafka
    consumer_config = {
        "bootstrap_servers": kafka_settings.bootstrap_servers,
        "client_id": f"{kafka_settings.client_id}-ml-results",
        "group_id": kafka_settings.ml_result_group_id,
        "enable_auto_commit": False,
        "auto_offset_reset": "earliest",
        "max_poll_records": 1,
        "request_timeout_ms": kafka_settings.request_timeout_ms,
        "max_poll_interval_ms": 3_600_000,
        "security_protocol": kafka_settings.security_protocol,
    }
    if kafka_settings.security_protocol == "SASL_SSL":
        consumer_config.update(
            ssl_context=create_ssl_context(),
            sasl_mechanism=kafka_settings.sasl_mechanism,
            sasl_plain_username=kafka_settings.sasl_username,
            sasl_plain_password=kafka_settings.sasl_password.get_secret_value(),
        )

    consumer = AIOKafkaConsumer(kafka_settings.ml_result_topic, **consumer_config)
    try:
        await consumer.start()
        logger.info(
            "ML result consumer started (topic=%s group=%s)",
            kafka_settings.ml_result_topic,
            kafka_settings.ml_result_group_id,
        )

        while True:
            record = await consumer.getone()
            event = None
            try:
                event = MlStageResultEvent.model_validate_json(record.value)
                logger.info(
                    "Received ML result event (job_id=%s user_id=%s stage=%s "
                    "is_initial=%s outputs=%d partition=%d offset=%d payload=%s)",
                    event.job_id,
                    event.user_id,
                    event.completed_stage.value,
                    event.is_initial,
                    len(event.outputs),
                    record.partition,
                    record.offset,
                    event.model_dump_json(),
                )
                logger.info(
                    "Processing ML result event (job_id=%s stage=%s)",
                    event.job_id,
                    event.completed_stage.value,
                )
                async with SessionFactory() as db_session:
                    async with db_session.begin():
                        applied = await JobService.process_ml_result(db_session, event)

                await consumer.commit()
                logger.info(
                    "ML result event committed (job_id=%s stage=%s applied=%s "
                    "partition=%d offset=%d)",
                    event.job_id,
                    event.completed_stage.value,
                    applied,
                    record.partition,
                    record.offset,
                )
            except Exception:
                logger.exception(
                    "Failed to process ML result event (job_id=%s stage=%s); "
                    "leaving it uncommitted (partition=%d offset=%d)",
                    event.job_id if event else None,
                    event.completed_stage.value if event else None,
                    record.partition,
                    record.offset,
                )
                consumer.seek(
                    TopicPartition(record.topic, record.partition), record.offset
                )
                await asyncio.sleep(5)
    finally:
        with suppress(Exception):
            await consumer.stop()
        logger.info("ML result consumer stopped")


async def run_consumer() -> None:
    """Keep the backend result consumer alive across Kafka interruptions."""
    while True:
        try:
            await _consume_results()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ML result consumer disconnected; retrying shortly")
            await asyncio.sleep(5)


async def _run_standalone() -> None:
    await KafkaProducer.start()
    try:
        await run_consumer()
    finally:
        await KafkaProducer.stop()


if __name__ == "__main__":
    asyncio.run(_run_standalone())
