"""
Hello-world activity — Phase A walking skeleton.

Activities are the only place nondeterminism is permitted (I/O, sleeps, model
calls).  The 2-second sleep makes this activity long enough to kill the worker
mid-execution and demonstrate exact resume.
"""
import asyncio

from temporalio import activity


@activity.defn
async def greet_activity(name: str) -> str:
    activity.logger.info("greet_activity started for %s", name)
    # Long enough to allow the kill-the-worker durability demonstration.
    await asyncio.sleep(2)
    result = f"Hello, {name}! (durable)"
    activity.logger.info("greet_activity completing: %s", result)
    return result
