"""situate_activity — read context (episodic + directive) for the current agent step.

Consequence class: REVERSIBLE (pure read, no side effects).
Idempotent: True (pure read — safe to retry).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.contracts.memory import ReadDirectiveInput, ReadEpisodicInput
from harness.shared.memory.postgres_memory import PostgresMemoryProvider
from harness.shared.persistence.constants import SYSTEM_ENTITY_ID
from harness.shared.persistence.pool import get_pool

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@dataclass
class SituateInput:
    agent_id: str
    run_id: str
    entity_id: str
    step_number: int
    idempotency_key: str
    flow_id: str = ""  # W5: flow-class pause check; empty = skip


@dataclass
class SituateResult:
    context_dict: dict
    tokens_used: int
    flow_paused: bool = False  # W5: True when flow-class is in 'paused' state


@activity.defn
async def situate_activity(inp: SituateInput) -> SituateResult:
    """Read recent episodic history and the active directive for this agent.

    Returns a context_dict suitable for passing into decide_activity and
    ultimately into build_messages (loop_support).
    """
    pool = await get_pool()
    mem = PostgresMemoryProvider(pool)

    episodic_out = await mem.read_episodic(
        ReadEpisodicInput(
            agent_id=inp.agent_id,
            entity_key=inp.entity_id,
            limit=5,
        )
    )
    directive_out = await mem.read_directive(
        ReadDirectiveInput(agent_id=inp.agent_id)
    )

    recent_history = [
        {
            "step": r.step,
            "action_type": r.action_type,
            "action_payload": r.action_payload,
            "outcome_payload": r.outcome_payload,
            "created_at": r.created_at,
        }
        for r in episodic_out.records
    ]

    context_dict = {
        "entity_id": inp.entity_id,
        "step": inp.step_number,
        "recent_history": recent_history,
        "directive": directive_out.priority_text,
        "knowledge": [],  # Phase D: query_knowledge will populate this
    }

    # W5: Check flow-class pause state. Uses the pool directly (mem has no state query).
    flow_paused = False
    if inp.flow_id:
        machine = f"flow_pause:{inp.flow_id}"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT position FROM state WHERE entity_id = $1::uuid AND machine = $2 ORDER BY seq DESC LIMIT 1",
                SYSTEM_ENTITY_ID,
                machine,
            )
        flow_paused = row is not None and row["position"] == "paused"

    logger.info(
        "situate_activity agent=%s step=%d entity=%s history_rows=%d directive_found=%s flow_paused=%s",
        inp.agent_id, inp.step_number, inp.entity_id,
        len(recent_history), directive_out.found, flow_paused,
    )

    return SituateResult(context_dict=context_dict, tokens_used=0, flow_paused=flow_paused)


register(Block(
    name="situate",
    input_type="harness.operations.activities.situate.SituateInput",
    output_type="harness.operations.activities.situate.SituateResult",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
