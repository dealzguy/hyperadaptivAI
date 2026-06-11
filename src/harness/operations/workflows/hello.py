"""
Hello-world workflow — Phase A walking skeleton.

Workflow code must be deterministic: no I/O, no model calls, no clocks, no
randomness.  All nondeterminism lives in activities.  The workflow.patched()
call establishes the Temporal versioning pattern before real business workflows
are added in Phase B.
"""
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from harness.operations.activities.hello import greet_activity


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        # workflow.patched() establishes the versioning pattern.
        # Phase B will use this to safely ship changes to in-flight executions.
        if workflow.patched("hello-v1"):
            pass  # current code path

        # 10s: 5× the activity's sleep, and short enough that the retry after
        # a worker kill fires quickly in the durability demonstration.
        result = await workflow.execute_activity(
            greet_activity,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )
        return result
