"""LeadIntakeWorkflow — scripted (non-agentic) lead intake (Phase B).

Deterministic orchestration that runs the Intake molecule end-to-end:
  NormalizedIntakeEvent → entity + event + state + task (all idempotent).

No inference, no agent, no model calls — the deterministic spine only.
Phase C will build the agent loop that acts through these blocks.

Workflow ID convention: "lead-intake-{entity_key}"
  entity_key is derived from identity_candidates at start time so
  re-submitting the same lead reuses the durable history
  (belt-and-suspenders with DB-level idempotency).

Sandbox safety: the only imports reachable from this module are:
  - temporalio.workflow (Temporal internals — safe)
  - harness.shared.contracts.intake (pure Python dataclasses)
  - harness.shared.molecules.intake (pure orchestration — no asyncpg)
asyncpg never enters the sandbox.
"""
from __future__ import annotations

import logging

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    # The molecule and contracts are asyncpg-free and sandbox-safe.
    # imports_passed_through() is kept here as an explicit, visible seam
    # — any future addition to this block that imports asyncpg would be
    # caught in review rather than silently contaminating the sandbox.
    from harness.shared.contracts.intake import NormalizedIntakeEvent
    from harness.shared.molecules.intake import derive_entity_key, intake_molecule


logger = logging.getLogger(__name__)


@workflow.defn
class LeadIntakeWorkflow:
    """Scripted lead intake workflow — one durable execution per unique lead identity."""

    @workflow.run
    async def run(self, event: NormalizedIntakeEvent) -> dict:
        """Run the Intake molecule and return a JSON-native result summary."""
        logger.info(
            "LeadIntakeWorkflow started: source_channel=%s key=%s",
            event.source_channel,
            derive_entity_key(event.identity_candidates),
        )

        entity_out, task_out = await intake_molecule(event)

        return {
            "entity_id": entity_out.id,
            "entity_key": entity_out.idempotency_key,
            "entity_created": entity_out.created,
            "task_id": task_out.id,
            "task_key": task_out.idempotency_key,
            "task_created": task_out.created,
        }
