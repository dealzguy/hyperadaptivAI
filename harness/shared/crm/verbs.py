"""Five CRM verb activities — the deterministic block layer (Doc 12 §8).

Each verb is an async Temporal activity that writes to the business Postgres
via asyncpg. All five are consequence_class=reversible in Phase B: they are
side-effect-free internal DB appends with no external actuation (email, payment,
irreversible outside effect) — nothing in the world has consumed the write, so
each effect is cleanly undoable (Doc 12 §8: consequence class = reversibility
of the effect, distinct from storage auditability).

Write pattern (retry-safe, idempotent by construction):
    INSERT ... ON CONFLICT (idempotency_key) DO NOTHING RETURNING id
    → if RETURNING is empty (conflict suppressed it), SELECT id WHERE key = $1

asyncpg is imported ONLY in this module and in pool.py.
Never imported from molecules, workflows, or the registry — sandbox safety.

Each activity registers its Block metadata into the registry at module import.
register() is idempotent + reentrant so Temporal sandbox reload is harmless.

TODO(liquid: compensation_handler field on Block + reversing-transition blocks)
— Phase C, arriving with the first compensable block (send-message, charge).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.crm.primitives import (
    AssignTaskInput,
    AssignTaskOutput,
    CreateEntityInput,
    CreateEntityOutput,
    RecordEventInput,
    RecordEventOutput,
    RelateInput,
    RelateOutput,
    TransitionStateInput,
    TransitionStateOutput,
)
from harness.shared.persistence.pool import get_pool

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _insert_or_get(conn, table: str, insert_sql: str, insert_args: list, key: str) -> tuple[str, bool]:
    """Execute INSERT … ON CONFLICT DO NOTHING RETURNING id.

    Returns (id_str, created_bool).
    On conflict (row already exists), re-SELECTs by idempotency_key.
    """
    row = await conn.fetchrow(insert_sql, *insert_args)
    if row is not None:
        return str(row["id"]), True
    # Conflict suppressed the RETURNING — the row exists; re-SELECT.
    existing = await conn.fetchrow(
        f"SELECT id FROM {table} WHERE idempotency_key = $1", key
    )
    if existing is None:
        raise RuntimeError(
            f"INSERT on {table} returned nothing and SELECT found nothing "
            f"for idempotency_key={key!r}. This should not happen."
        )
    return str(existing["id"]), False


# ── create_entity ─────────────────────────────────────────────────────────────

@activity.defn
async def create_entity(payload: CreateEntityInput) -> CreateEntityOutput:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row_id, created = await _insert_or_get(
            conn,
            "entity",
            """
            INSERT INTO entity (type, attributes, idempotency_key)
            VALUES ($1, $2, $3)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """,
            [payload.entity_type, json.dumps(payload.attributes), payload.idempotency_key],
            payload.idempotency_key,
        )
    logger.info("create_entity key=%s id=%s created=%s", payload.idempotency_key, row_id, created)
    return CreateEntityOutput(id=row_id, idempotency_key=payload.idempotency_key, created=created)


register(Block(
    name="create_entity",
    input_type="harness.shared.crm.primitives.CreateEntityInput",
    output_type="harness.shared.crm.primitives.CreateEntityOutput",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))


# ── relate ────────────────────────────────────────────────────────────────────

@activity.defn
async def relate(payload: RelateInput) -> RelateOutput:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row_id, created = await _insert_or_get(
            conn,
            "relationship",
            """
            INSERT INTO relationship (type, from_entity_id, to_entity_id, attributes, idempotency_key)
            VALUES ($1, $2::uuid, $3::uuid, $4, $5)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """,
            [
                payload.relation_type,
                payload.from_entity_id,
                payload.to_entity_id,
                json.dumps(payload.attributes),
                payload.idempotency_key,
            ],
            payload.idempotency_key,
        )
    logger.info("relate key=%s id=%s created=%s", payload.idempotency_key, row_id, created)
    return RelateOutput(id=row_id, idempotency_key=payload.idempotency_key, created=created)


register(Block(
    name="relate",
    input_type="harness.shared.crm.primitives.RelateInput",
    output_type="harness.shared.crm.primitives.RelateOutput",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))


# ── record_event ──────────────────────────────────────────────────────────────

@activity.defn
async def record_event(payload: RecordEventInput) -> RecordEventOutput:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row_id, created = await _insert_or_get(
            conn,
            "event",
            """
            INSERT INTO event (type, actor, entity_id, payload, occurred_at, idempotency_key)
            VALUES ($1, $2, $3::uuid, $4, $5, $6)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """,
            [
                payload.event_type,
                payload.actor,
                payload.entity_id,
                json.dumps(payload.payload),
                datetime.fromisoformat(payload.occurred_at),
                payload.idempotency_key,
            ],
            payload.idempotency_key,
        )
    logger.info("record_event key=%s id=%s created=%s", payload.idempotency_key, row_id, created)
    return RecordEventOutput(id=row_id, idempotency_key=payload.idempotency_key, created=created)


register(Block(
    name="record_event",
    input_type="harness.shared.crm.primitives.RecordEventInput",
    output_type="harness.shared.crm.primitives.RecordEventOutput",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))


# ── transition_state ──────────────────────────────────────────────────────────
# Append-only: each transition INSERTs a new row (no DO UPDATE).
# Current position = latest by seq per (entity_id, machine).
# Consequence class is reversible — same rationale as all Phase B verbs.

@activity.defn
async def transition_state(payload: TransitionStateInput) -> TransitionStateOutput:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row_id, created = await _insert_or_get(
            conn,
            "state",
            """
            INSERT INTO state (entity_id, machine, position, attributes, idempotency_key)
            VALUES ($1::uuid, $2, $3, $4, $5)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """,
            [
                payload.entity_id,
                payload.machine,
                payload.position,
                json.dumps(payload.attributes),
                payload.idempotency_key,
            ],
            payload.idempotency_key,
        )
    logger.info("transition_state key=%s id=%s created=%s", payload.idempotency_key, row_id, created)
    return TransitionStateOutput(id=row_id, idempotency_key=payload.idempotency_key, created=created)


register(Block(
    name="transition_state",
    input_type="harness.shared.crm.primitives.TransitionStateInput",
    output_type="harness.shared.crm.primitives.TransitionStateOutput",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))


# ── assign_task ───────────────────────────────────────────────────────────────

@activity.defn
async def assign_task(payload: AssignTaskInput) -> AssignTaskOutput:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row_id, created = await _insert_or_get(
            conn,
            "task",
            """
            INSERT INTO task (type, assignee, entity_id, status, attributes, idempotency_key)
            VALUES ($1, $2, $3::uuid, $4, $5, $6)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """,
            [
                payload.task_type,
                payload.assignee,
                payload.entity_id,
                payload.status,
                json.dumps(payload.attributes),
                payload.idempotency_key,
            ],
            payload.idempotency_key,
        )
    logger.info("assign_task key=%s id=%s created=%s", payload.idempotency_key, row_id, created)
    return AssignTaskOutput(id=row_id, idempotency_key=payload.idempotency_key, created=created)


register(Block(
    name="assign_task",
    input_type="harness.shared.crm.primitives.AssignTaskInput",
    output_type="harness.shared.crm.primitives.AssignTaskOutput",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
