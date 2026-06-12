"""record_activity — write an episodic row for the completed agent step.

Consequence class: REVERSIBLE (append-only internal DB write, no external actuation).
Idempotent: True — ON CONFLICT (idempotency_key) DO NOTHING ensures exactly-once storage.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.contracts.memory import WriteEpisodicInput
from harness.shared.memory.postgres_memory import PostgresMemoryProvider
from harness.shared.persistence.pool import get_pool

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@dataclass
class RecordInput:
    agent_id: str
    run_id: str
    step: int
    action_type: str
    action_payload: dict
    outcome_payload: dict
    model_id: str
    token_count: int
    entity_key: str
    idempotency_key: str


@dataclass
class RecordResult:
    episodic_id: str
    created: bool


@activity.defn
async def record_activity(inp: RecordInput) -> RecordResult:
    """Persist one episodic row for the current step (idempotent via idempotency_key)."""
    pool = await get_pool()
    mem = PostgresMemoryProvider(pool)

    out = await mem.write_episodic(
        WriteEpisodicInput(
            agent_id=inp.agent_id,
            run_id=inp.run_id,
            step=inp.step,
            action_type=inp.action_type,
            action_payload=inp.action_payload,
            outcome_payload=inp.outcome_payload,
            model_id=inp.model_id,
            token_count=inp.token_count,
            entity_key=inp.entity_key,
            idempotency_key=inp.idempotency_key,
        )
    )

    logger.info(
        "record_activity agent=%s step=%d key=%s id=%s created=%s",
        inp.agent_id, inp.step, inp.idempotency_key, out.id, out.created,
    )
    return RecordResult(episodic_id=out.id, created=out.created)


register(Block(
    name="record",
    input_type="harness.operations.activities.record.RecordInput",
    output_type="harness.operations.activities.record.RecordResult",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
