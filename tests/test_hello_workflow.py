"""
In-process test for HelloWorkflow.

Uses temporalio.testing.WorkflowEnvironment so no running Temporal server or
containers are required.  Demonstrates that the workflow executes the activity
and returns the expected result.
"""
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from harness.operations.activities.hello import greet_activity
from harness.operations.workflows.hello import HelloWorkflow


@pytest.mark.asyncio
async def test_hello_workflow_completes():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[HelloWorkflow],
            activities=[greet_activity],
        ):
            result = await env.client.execute_workflow(
                HelloWorkflow.run,
                "world",
                id="test-hello-world",
                task_queue="test-queue",
            )
    assert result == "Hello, world! (durable)"


@pytest.mark.asyncio
async def test_hello_workflow_different_name():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[HelloWorkflow],
            activities=[greet_activity],
        ):
            result = await env.client.execute_workflow(
                HelloWorkflow.run,
                "operator",
                id="test-hello-operator",
                task_queue="test-queue",
            )
    assert result == "Hello, operator! (durable)"
