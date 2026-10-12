import argparse
import importlib
import logging
import multiprocessing
import os
import signal
import sys
import threading
import time
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ML_DIR / "src"))

from sonclarus_ml.shared.logging_config import setup_logging
from sonclarus_ml.shared.config import get_settings
from sonclarus_ml.shared.consumer import run_stage_consumer

setup_logging(level="INFO")
logger = logging.getLogger("ml_consumers")

RESTART_DELAY_SECONDS = 3
INFERENCE_FUNCTIONS = {
    "denoise": "run_denoise",
    "separate": "run_separation",
    "transcribe": "run_transcription",
    "summarize": "run_summarization",
}


def run_stage_worker(stage: str) -> None:
    """Load only this worker's model package, then consume its topic."""
    settings = get_settings()
    os.environ.setdefault("OMP_NUM_THREADS", str(settings.worker.torch_num_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(settings.worker.torch_num_threads))

    module = importlib.import_module(f"sonclarus_ml.{stage}.inference")
    inference = getattr(module, INFERENCE_FUNCTIONS[stage])
    run_stage_consumer(stage, inference)


def start_worker(
    stage: str, context: multiprocessing.context.BaseContext
) -> multiprocessing.Process:
    """Start one stage consumer in an isolated process."""
    logger.info("Starting %s consumer", stage)
    process = context.Process(
        target=run_stage_worker,
        args=(stage,),
        name=f"sonclarus-ml-{stage}",
    )
    process.start()
    return process


def stop_workers(workers: dict[str, multiprocessing.Process]) -> None:
    """Stop all running consumers and wait for their processes to exit."""
    for stage, process in workers.items():
        if process.is_alive():
            logger.info("Stopping %s consumer (pid=%s)", stage, process.pid)
            process.terminate()

    for stage, process in workers.items():
        process.join(timeout=15)
        if process.is_alive():
            logger.warning("%s consumer did not stop; killing it", stage)
            process.kill()
            process.join()
        process.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start and supervise SonClarus ML Kafka consumers."
    )
    for stage in INFERENCE_FUNCTIONS:
        parser.add_argument(
            f"--{stage}",
            action="store_true",
            help=f"Run only the {stage} consumer. If omitted, run all stages.",
        )
    args = parser.parse_args()

    try:
        get_settings()
    except Exception:
        logger.error("Missing or invalid settings ")
        raise SystemExit(2)

    selected = [stage for stage in INFERENCE_FUNCTIONS if getattr(args, stage)]
    if not selected:
        selected = list(INFERENCE_FUNCTIONS)

    context = multiprocessing.get_context("spawn")
    workers = {stage: start_worker(stage, context) for stage in selected}
    stop_event = threading.Event()

    def request_stop(_signal: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    restart_at: dict[str, float | None] = {stage: None for stage in selected}
    try:
        while not stop_event.wait(timeout=1):
            now = time.monotonic()
            for stage, process in list(workers.items()):
                if process.is_alive():
                    continue
                process.join()
                if restart_at[stage] is None:
                    logger.error(
                        "%s consumer exited with code %s; retrying in %d seconds",
                        stage,
                        process.exitcode,
                        RESTART_DELAY_SECONDS,
                    )
                    restart_at[stage] = now + RESTART_DELAY_SECONDS
                    continue
                if now < restart_at[stage]:
                    continue
                process.close()
                workers[stage] = start_worker(stage, context)
                restart_at[stage] = None
    finally:
        stop_workers(workers)
        logger.info("All ML consumers stopped")


if __name__ == "__main__":
    main()
