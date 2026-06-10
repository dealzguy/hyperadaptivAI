"""
Temporal worker entry point.

Reads TEMPORAL_ADDRESS and TEMPORAL_TASK_QUEUE from the environment (delivered
through the secrets-contract seam: deploy/.env.example → actual .env).
Registers all workflows and activities for Phase A.
"""
import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from harness.operations.activities.hello import greet_activity
from harness.operations.workflows.hello import HelloWorkflow


async def main() -> None:
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "harness-main")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")

    client = await Client.connect(address, namespace=namespace)

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[HelloWorkflow],
        activities=[greet_activity],
    )

    print(f"Worker started — address={address!r} task_queue={task_queue!r}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
