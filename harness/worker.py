"""Temporal worker entry point — Phase A walking skeleton.

Registers HelloWorkflow and hello_activity on the skeleton-queue task queue.
Run via: python -m harness.worker
Or inside compose: CMD in Dockerfile.harness
"""
import asyncio
import concurrent.futures
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from harness.workflows.skeleton.activity import hello_activity
from harness.workflows.skeleton.workflow import HelloWorkflow

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def main() -> None:
    temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "skeleton-queue")

    logger.info("Connecting to Temporal at %s", temporal_host)
    client = await Client.connect(temporal_host)

    logger.info("Starting worker on task queue %r", task_queue)
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as activity_executor:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[HelloWorkflow],
            activities=[hello_activity],
            activity_executor=activity_executor,
        )
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
