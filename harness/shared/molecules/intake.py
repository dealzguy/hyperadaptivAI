"""Intake molecule — composition of five verified blocks (Doc 12 §3).

Choreography:
  1. create_entity     — match-or-create the entity from identity candidates
  2. record_event      — record the source intake event as an immutable fact
  3. transition_state  — open the lifecycle state (enter Engage stage)
  4. assign_task       — open the first follow-up task (Doc 12 §9 Operations loop)

This function is pure orchestration: no I/O, no asyncpg, no timestamps generated
here. It derives all four idempotency keys deterministically from the normalized
event, then delegates to verified blocks via workflow.execute_activity by name.

Import chain is sandbox-safe: only primitives (JSON-native dataclasses) and
contracts (pure Protocol definitions) are imported. asyncpg never enters here.

Closure check (written for docs/BLOCKS.md):
  Intake = create_entity + record_event + transition_state + assign_task (no remainder).
  Each verb traces to the Engage-entry shell process (Doc 12 §9):
    - create_entity  → match-or-create the entity
    - record_event   → record source event (immutable fact)
    - transition_state → open lifecycle state (position = "engage_open")
    - assign_task    → open first follow-up task (lead-intake to first-follow-up, §9)
  The fourth act (assign_task) is justified by the Operations loop "lead-intake to
  first-follow-up" (Doc 12 §9) which requires opening a follow-up task; it is
  in-scope, not a remainder vs. the three-act base definition in §3.

TODO(liquid: richer identity resolution — first real corpus, Phase E).
Current implementation: exact-match on canonicalized identity_candidates dict.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from temporalio import workflow

from harness.shared.contracts.intake import NormalizedIntakeEvent
from harness.shared.crm.primitives import (
    AssignTaskInput,
    AssignTaskOutput,
    CreateEntityInput,
    CreateEntityOutput,
    RecordEventInput,
    RecordEventOutput,
    TransitionStateInput,
    TransitionStateOutput,
)

_ACTIVITY_TIMEOUT = timedelta(seconds=30)
_LIFECYCLE_MACHINE = "lead"
_LIFECYCLE_OPEN_POSITION = "engage_open"
_FIRST_TASK_TYPE = "first_follow_up"


def _key(*parts: str) -> str:
    """Derive a deterministic idempotency key from one or more string parts."""
    payload = ":".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _canonical(d: dict) -> str:
    """Stable JSON serialization of a dict (sorted keys, no spaces)."""
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def derive_entity_key(identity_candidates: dict) -> str:
    """Derive the stable entity idempotency key from identity candidates.

    TODO(liquid: richer identity resolution) — Phase B ships exact-match only.
    """
    return _key(_canonical(identity_candidates))


async def intake_molecule(event: NormalizedIntakeEvent) -> tuple[CreateEntityOutput, AssignTaskOutput]:
    """Execute the Intake molecule for a normalized intake event.

    Derives all four idempotency keys from the event, then dispatches to
    verified blocks by registered activity name. All keys are deterministic
    so re-running with the same event is exactly-once across all four tables.

    Returns (entity_output, task_output).
    """
    # Derive all keys from stable event fields — never from workflow.now() or uuid4().
    entity_key = derive_entity_key(event.identity_candidates)
    event_key = _key(entity_key, event.source_channel, event.raw_payload_ref)
    state_key = _key(entity_key, _LIFECYCLE_MACHINE, _LIFECYCLE_OPEN_POSITION)
    task_key = _key(entity_key, _FIRST_TASK_TYPE, event_key)

    # Step 1: match-or-create entity (atomic via unique index — no TOCTOU race).
    entity_out: CreateEntityOutput = await workflow.execute_activity(
        "create_entity",
        CreateEntityInput(
            entity_type="lead",
            attributes={**event.captured_attributes, **event.identity_candidates},
            idempotency_key=entity_key,
        ),
        result_type=CreateEntityOutput,
        start_to_close_timeout=_ACTIVITY_TIMEOUT,
    )

    # Downstream blocks use entity_key (str) to reference the entity,
    # NOT the returned uuid — removes cross-boundary UUID serialization dependency.
    entity_id = entity_out.id

    # Step 2: record the source event as an immutable fact.
    event_out: RecordEventOutput = await workflow.execute_activity(
        "record_event",
        RecordEventInput(
            event_type="intake_received",
            entity_id=entity_id,
            payload={"source_channel": event.source_channel, "raw_payload_ref": event.raw_payload_ref},
            occurred_at=event.source_timestamp,
            idempotency_key=event_key,
            actor="intake_adapter",
        ),
        result_type=RecordEventOutput,
        start_to_close_timeout=_ACTIVITY_TIMEOUT,
    )

    # Step 3: open the lifecycle state (append-only — no UPDATE-in-place).
    await workflow.execute_activity(
        "transition_state",
        TransitionStateInput(
            entity_id=entity_id,
            machine=_LIFECYCLE_MACHINE,
            position=_LIFECYCLE_OPEN_POSITION,
            attributes={"opened_by": event.source_channel},
            idempotency_key=state_key,
        ),
        result_type=TransitionStateOutput,
        start_to_close_timeout=_ACTIVITY_TIMEOUT,
    )

    # Step 4: assign the first follow-up task (Doc 12 §9 lead-intake to first-follow-up).
    task_out: AssignTaskOutput = await workflow.execute_activity(
        "assign_task",
        AssignTaskInput(
            task_type=_FIRST_TASK_TYPE,
            entity_id=entity_id,
            attributes={"source_event_key": event_key},
            idempotency_key=task_key,
        ),
        result_type=AssignTaskOutput,
        start_to_close_timeout=_ACTIVITY_TIMEOUT,
    )

    return entity_out, task_out
