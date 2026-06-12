"""Temporal worker entry point — Phase B capability layer.

Registers the Phase A walking skeleton AND all Phase B verb activities
and the LeadIntakeWorkflow. Pool is built inside async main() on the
running event loop (never at import time; never bridged from a sync thread).
Schema bootstrap is a separate one-shot (python -m harness.shared.persistence.bootstrap)
— NOT run here, to avoid multi-worker DDL races.

Run via: python -m harness.worker
Or inside compose: CMD in Dockerfile.harness
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from harness.workflows.skeleton.activity import hello_activity
from harness.workflows.skeleton.workflow import HelloWorkflow

# Phase B: import verb activities to trigger block registration in the registry.
from harness.shared.crm.verbs import (
    assign_task,
    create_entity,
    record_event,
    relate,
    transition_state,
)
from harness.operations.workflows.lead_intake import LeadIntakeWorkflow
from harness.shared.persistence.dsn import build_dsn
from harness.shared.persistence.pool import close_pool, create_pool

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def main() -> None:
    temporal_host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "skeleton-queue")

    logger.info("Connecting to Temporal at %s", temporal_host)
    client = await Client.connect(temporal_host)

    # Build the asyncpg pool on the running event loop.
    # Thin retry/backoff (N attempts then fatal) — see pool.py.
    logger.info("Building asyncpg pool")
    dsn = build_dsn()
    await create_pool(dsn)

    logger.info("Starting worker on task queue %r", task_queue)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as activity_executor:
            worker = Worker(
                client,
                task_queue=task_queue,
                workflows=[HelloWorkflow, LeadIntakeWorkflow],
                activities=[
                    hello_activity,
                    create_entity,
                    relate,
                    record_event,
                    transition_state,
                    assign_task,
                ],
                activity_executor=activity_executor,
            )
            await worker.run()
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
