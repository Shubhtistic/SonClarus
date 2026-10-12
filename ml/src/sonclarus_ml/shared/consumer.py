import asyncio
import logging
import mimetypes
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
from aiokafka.helpers import create_ssl_context
from aiokafka.structs import TopicPartition
from pydantic import BaseModel, ConfigDict

from sonclarus_ml.shared.config import get_settings
from sonclarus_ml.shared.file_hash import compute_file_hash
from sonclarus_ml.shared.kafka_client import KafkaProducer
from sonclarus_ml.shared.s3_client import S3Client

logger = logging.getLogger(__name__)

STAGE_TOPICS = {
    "denoise": "denoise_topic",
    "separate": "separate_topic",
    "transcribe": "transcribe_topic",
    "summarize": "summarize_topic",
}


class StageMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    user_id: UUID
    s3_bucket: str
    s3_key: str
    requested_stage: str
    is_initial: bool
    is_seperated: bool = False
    input_filename: str | None = None
    input_filename1: str | None = None
    input_filename2: str | None = None


def _s3_client() -> S3Client:
    return S3Client()


def _object_key(prefix_or_key: str, filename: str) -> str:
    prefix = prefix_or_key.rstrip("/")
    if prefix.endswith("/" + filename) or prefix == filename:
        return prefix
    return str(PurePosixPath(prefix) / filename)


def _artifact_paths(
    stage: str,
    input_path: Path,
    output_dir: Path,
    message: StageMessage,
    inference: Callable[..., dict[str, Any]],
) -> list[Path]:
    if stage == "denoise":
        result = inference(str(input_path), output_dir)
        return [Path(result["output_path"])]
    if stage == "separate":
        result = inference(str(input_path), output_dir / input_path.stem)
        return [Path(path) for path in result["output_paths"]]
    if stage == "transcribe":
        paths = [input_path]
        if message.is_seperated:
            if not message.input_filename1 or not message.input_filename2:
                raise ValueError(
                    "Separated transcription requires both input filenames"
                )
            paths = [
                input_path.parent / message.input_filename1,
                input_path.parent / message.input_filename2,
            ]
        result = inference([str(path) for path in paths], output_dir)
        return [Path(result["output_path"])]
    if stage == "summarize":
        transcript = input_path.read_text(encoding="utf-8")
        result = inference(transcript)
        output_path = output_dir / f"{input_path.stem}_summary.txt"
        output_path.write_text(result["summary"], encoding="utf-8")
        return [output_path]
    raise ValueError(f"Unsupported stage: {stage}")


def _stage_metadata(stage: str, artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "status": "done",
        "s3_bucket": artifacts[0]["s3_bucket"],
        "s3_key": (
            str(PurePosixPath(artifacts[0]["s3_key"]).parent)
            if stage == "separate"
            else artifacts[0]["s3_key"]
        ),
        "size_bytes": sum(item["size_bytes"] for item in artifacts),
        "content_type": artifacts[0]["content_type"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if stage in {"denoise", "transcribe", "summarize"}:
        metadata["filename"] = artifacts[0]["filename"]
    elif stage == "separate":
        metadata["first_filename"] = artifacts[0]["filename"]
        metadata["second_filename"] = artifacts[1]["filename"]
    return metadata


async def process_message(
    stage: str,
    raw_value: bytes,
    inference: Callable[..., dict[str, Any]],
) -> None:
    message = StageMessage.model_validate_json(raw_value)
    if message.requested_stage != stage:
        raise ValueError(
            f"Topic stage {stage!r} does not match requested stage "
            f"{message.requested_stage!r}"
        )
    if stage == "transcribe" and message.is_seperated:
        filenames = [message.input_filename1, message.input_filename2]
    else:
        filenames = [message.input_filename]
    if any(not filename for filename in filenames):
        raise ValueError(f"{stage} message is missing its input filename")

    settings = get_settings()
    job_id = str(message.job_id)
    user_id = str(message.user_id)
    bucket = message.s3_bucket
    s3 = _s3_client()

    Path(settings.worker.work_dir).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"{stage}-{job_id}-", dir=settings.worker.work_dir
    ) as temp_dir:
        work_dir = Path(temp_dir)
        input_dir = work_dir / "input"
        output_dir = work_dir / "output"
        input_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        local_inputs: list[Path] = []
        for filename in filenames:
            input_path = input_dir / Path(filename).name
            await s3.download_file(
                _object_key(message.s3_key, filename),
                str(input_path),
                bucket_name=bucket,
            )
            local_inputs.append(input_path)

        file_hash = compute_file_hash(local_inputs[0]) if message.is_initial else None
        primary_input = local_inputs[0]
        artifact_paths = await asyncio.to_thread(
            _artifact_paths, stage, primary_input, output_dir, message, inference
        )
        if not artifact_paths or any(not path.is_file() for path in artifact_paths):
            raise RuntimeError(f"{stage} did not produce all expected output files")

        prefix = f"{user_id}/{job_id}/{stage}"
        artifacts: list[dict[str, Any]] = []
        for path in artifact_paths:
            filename = path.name
            key = str(PurePosixPath(prefix) / filename)
            await s3.upload_file(str(path), key, bucket_name=bucket)
            artifacts.append(
                {
                    "filename": filename,
                    "s3_key": key,
                    "size_bytes": path.stat().st_size,
                    "content_type": mimetypes.guess_type(filename)[0]
                    or "application/octet-stream",
                    "s3_bucket": bucket,
                }
            )

        result_event = {
            "job_id": job_id,
            "user_id": user_id,
            "completed_stage": stage,
            "is_initial": message.is_initial,
            "file_hash": file_hash,
            "stage_data": _stage_metadata(stage, artifacts),
            "outputs": artifacts,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        await KafkaProducer.send_job(result_event, settings.kafka.result_topic)
        logger.info(
            "Stage completed (stage=%s job_id=%s artifacts=%d)",
            stage,
            job_id,
            len(artifacts),
        )


async def run_consumer(stage: str, inference: Callable[..., dict[str, Any]]) -> None:
    if stage not in STAGE_TOPICS:
        raise ValueError(f"Unknown stage: {stage}")

    settings = get_settings()
    topic = getattr(settings.kafka, STAGE_TOPICS[stage])
    consumer_config: dict[str, Any] = {
        "bootstrap_servers": settings.kafka.bootstrap_servers,
        "client_id": f"{settings.kafka.client_id}-{stage}",
        "group_id": f"{settings.kafka.group_id_prefix}-{stage}",
        "enable_auto_commit": False,
        "auto_offset_reset": "earliest",
        # One prefetched message per model worker avoids holding a large backlog
        # in each memory-heavy process while the four stages run independently.
        "max_poll_records": 1,
        "max_poll_interval_ms": settings.kafka.max_poll_interval_ms,
        "request_timeout_ms": settings.kafka.request_timeout_ms,
        "security_protocol": settings.kafka.security_protocol,
    }
    if settings.kafka.security_protocol == "SASL_SSL":
        consumer_config.update(
            ssl_context=create_ssl_context(),
            sasl_mechanism=settings.kafka.sasl_mechanism,
            sasl_plain_username=settings.kafka.sasl_username,
            sasl_plain_password=settings.kafka.sasl_password.get_secret_value(),
        )

    consumer = AIOKafkaConsumer(topic, **consumer_config)
    try:
        await KafkaProducer.start()
        await consumer.start()
        logger.info("ML consumer started (stage=%s topic=%s)", stage, topic)
        while True:
            record = await consumer.getone()
            try:
                await process_message(stage, record.value, inference)
                await consumer.commit()
            except Exception:
                logger.exception(
                    "Message processing failed; leaving it uncommitted "
                    "(stage=%s partition=%d offset=%d)",
                    stage,
                    record.partition,
                    record.offset,
                )
                consumer.seek(
                    TopicPartition(record.topic, record.partition), record.offset
                )
                await asyncio.sleep(5)
    except (KafkaError, OSError):
        logger.exception("Kafka consumer stopped unexpectedly (stage=%s)", stage)
        raise
    finally:
        await consumer.stop()
        await KafkaProducer.stop()


def run_stage_consumer(stage: str, inference: Callable[..., dict[str, Any]]) -> None:
    settings = get_settings()
    os.environ.setdefault("OMP_NUM_THREADS", str(settings.worker.torch_num_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(settings.worker.torch_num_threads))
    if stage != "summarize":
        # Summarization does not need Torch; import it here to keep that worker
        # process lighter while limiting CPU threads in the model workers.
        import torch

        torch.set_num_threads(settings.worker.torch_num_threads)
    asyncio.run(run_consumer(stage, inference))
