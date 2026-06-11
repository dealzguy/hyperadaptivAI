from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from harness.workflows.skeleton.activity import hello_activity


@workflow.defn
class HelloWorkflow:
    """Phase A walking skeleton — proves durable execution and exact resume.

    One activity call; no business logic; no model calls.
    Determinism boundary: this class is pure Temporal SDK calls only.
    """

    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            hello_activity,
            name,
            start_to_close_timeout=timedelta(seconds=30),
        )
