"""Long-poll ElasticMQ/SQS and execute document-ingestion jobs."""

from __future__ import annotations

import logging
import os
import threading

from botocore.exceptions import BotoCoreError, ClientError

from .backend import DEMO_DOCUMENTS, IngestionDemoAgent
from .job_queue import ElasticJobQueue, ReceivedJob
from .run_store import DurableRun, RunStore, TERMINAL_STATUSES


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger(__name__)


def _heartbeat(queue: ElasticJobQueue, job: ReceivedJob, stop: threading.Event) -> None:
    interval = max(30, int(os.getenv("SQS_VISIBILITY_TIMEOUT", "900")) // 3)
    while not stop.wait(interval):
        try:
            queue.extend_visibility(job)
        except (BotoCoreError, ClientError):
            LOGGER.exception("Could not extend visibility for run %s", job.payload.get("run_id"))


def main() -> None:
    store = RunStore()
    queue = ElasticJobQueue()
    LOGGER.info("Waiting for ingestion jobs on %s", queue.queue_url)

    while True:
        job = queue.receive()
        if job is None:
            continue

        run_id = str(job.payload.get("run_id", ""))
        document = str(job.payload.get("document", ""))
        delay = float(job.payload.get("delay_seconds", 0))
        provider = str(job.payload.get("provider", "anthropic"))
        run_record = store.get(run_id)

        if run_record is None:
            LOGGER.error("Discarding job for unknown run %s", run_id)
            queue.acknowledge(job)
            continue
        if run_record["status"] in TERMINAL_STATUSES:
            LOGGER.info("Acknowledging duplicate terminal run %s", run_id)
            queue.acknowledge(job)
            continue
        if document not in DEMO_DOCUMENTS:
            store.finish(run_id, "failed", {"message": "Unknown demo document"})
            queue.acknowledge(job)
            continue

        stop = threading.Event()
        heartbeat = threading.Thread(
            target=_heartbeat,
            args=(queue, job, stop),
            name=f"visibility-{run_id}",
            daemon=True,
        )
        heartbeat.start()
        try:
            LOGGER.info("Starting run %s for %s", run_id, document)
            IngestionDemoAgent(DurableRun(store, run_id), document, delay, provider).execute()
            queue.acknowledge(job)
            LOGGER.info("Finished run %s", run_id)
        except Exception as exc:
            LOGGER.exception("Worker failed run %s", run_id)
            store.finish(run_id, "failed", {"message": str(exc), "exception": type(exc).__name__})
        finally:
            stop.set()
            heartbeat.join(timeout=2)


if __name__ == "__main__":
    main()
