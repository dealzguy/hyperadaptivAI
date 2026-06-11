"""
Temporal worker entry point.

Reads TEMPORAL_ADDRESS and TEMPORAL_TASK_QUEUE from the environment (delivered
through the secrets-contract seam: deploy/.env.example → actual .env).
Registers all workflows and activities for Phase A.

Connection retries cover the compose startup race: the harness container may
come up before Temporal finishes auto-setup, and short-form depends_on does
not wait for readiness.
"""
import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from harness.operations.activities.hello import greet_activity
from harness.operations.workflows.hello import HelloWorkflow

CONNECT_ATTEMPTS = 30
CONNECT_DELAY_SECONDS = 2.0


async def connect_with_retry(address: str, namespace: str) -> Client:
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            return await Client.connect(address, namespace=namespace)
        except Exception as exc:
            if attempt == CONNECT_ATTEMPTS:
                raise
            print(
                f"Temporal not ready at {address!r} ({type(exc).__name__}); "
                f"retry {attempt}/{CONNECT_ATTEMPTS} in {CONNECT_DELAY_SECONDS}s"
            )
            await asyncio.sleep(CONNECT_DELAY_SECONDS)
    raise RuntimeError("unreachable")


async def main() -> None:
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "harness-main")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")

    client = await connect_with_retry(address, namespace)

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
