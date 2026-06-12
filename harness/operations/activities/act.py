"""act_activity — dispatch the chosen action through the capability registry.

Consequence class: determined at runtime by the target block's registry entry.
This activity itself is REVERSIBLE (the routing shell); the effect class of
the dispatched action is what matters for gate placement, which is handled
by gate_mode() in loop_support (workflow-side) before this activity is called.

P0-2 compliance: unknown tool → returns error in ActResult (never raises); the
workflow parks on non-empty ActResult.error rather than retrying forever.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@dataclass
class ActInput:
    action_type: str
    action_payload: dict
    entity_id: str
    idempotency_key: str


@dataclass
class ActResult:
    outcome_payload: dict
    consequence_class: str
    error: str


@activity.defn
async def act_activity(inp: ActInput) -> ActResult:
    """Route an action through the capability registry.

    If action_type is not registered, returns ActResult with a non-empty error
    string — the workflow parks rather than retrying forever (P0-2 fix).
    The action_payload is passed through after injecting idempotency_key and
    entity_id so callers need not repeat them.
    """
    # Late import to avoid circular deps; verbs must be imported before worker starts.
    from harness.shared.capability import registry as reg_module

    try:
        block = reg_module.get(inp.action_type)
    except KeyError:
        err = f"unknown tool {inp.action_type!r} — not in capability registry"
        logger.error("act_activity: %s", err)
        return ActResult(outcome_payload={}, consequence_class="reversible", error=err)

    # Inject cross-cutting fields the model should not supply (P1-2: occurred_at, etc.)
    # so the model-facing payload only carries semantic arguments.
    payload = dict(inp.action_payload)
    payload.setdefault("idempotency_key", inp.idempotency_key)
    payload.setdefault("entity_id", inp.entity_id)

    # record_event: inject occurred_at server-side so the model never fabricates
    # a timestamp (P1-2 fix). Activity is in the nondeterministic layer — clocks OK.
    if inp.action_type == "record_event" and "occurred_at" not in payload:
        from datetime import datetime, timezone
        payload["occurred_at"] = datetime.now(timezone.utc).isoformat()

    # Dispatch to the registered activity by name using the CRM verbs module.
    # Each verb activity is imported at worker startup; we call them directly here.
    try:
        outcome = await _dispatch(inp.action_type, payload)
    except Exception as exc:  # noqa: BLE001
        err = f"act_activity: tool {inp.action_type!r} raised: {exc}"
        logger.error(err)
        # Return error so workflow can park (P0-2): bounded retry is set at the
        # workflow.execute_activity call site; failures here become ActResult.error.
        return ActResult(outcome_payload={}, consequence_class=block.consequence_class, error=err)

    logger.info(
        "act_activity action=%s entity=%s key=%s",
        inp.action_type, inp.entity_id, inp.idempotency_key,
    )
    return ActResult(
        outcome_payload=outcome if isinstance(outcome, dict) else _to_dict(outcome),
        consequence_class=block.consequence_class,
        error="",
    )


def _to_dict(obj) -> dict:
    """Convert a dataclass output to a plain dict (JSON-serializable)."""
    try:
        from dataclasses import asdict
        return asdict(obj)
    except TypeError:
        return {"value": str(obj)}


async def _dispatch(action_type: str, payload: dict):
    """Call the named CRM verb activity function directly (not via Temporal scheduling).

    act_activity is itself a Temporal activity, so calling a verb function directly
    here runs it in the same activity context. The verb handles its own DB pool.
    """
    from harness.shared.crm import verbs
    from harness.shared.crm.primitives import (
        AssignTaskInput,
        CreateEntityInput,
        RecordEventInput,
        RelateInput,
        TransitionStateInput,
    )

    dispatch_map = {
        "create_entity": (verbs.create_entity, CreateEntityInput),
        "relate": (verbs.relate, RelateInput),
        "record_event": (verbs.record_event, RecordEventInput),
        "transition_state": (verbs.transition_state, TransitionStateInput),
        "assign_task": (verbs.assign_task, AssignTaskInput),
    }

    if action_type not in dispatch_map:
        # Fallback: we only know CRM verbs in Phase C.
        raise ValueError(
            f"act_activity._dispatch: no handler for {action_type!r}. "
            "Register it in the dispatch_map."
        )

    fn, input_cls = dispatch_map[action_type]

    # Build the input dataclass from the payload dict.
    # Missing required fields will raise TypeError here — caught by the caller.
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(input_cls)}
    filtered = {k: v for k, v in payload.items() if k in field_names}
    inp_obj = input_cls(**filtered)

    # Call the activity function directly (we are already inside an activity).
    result = await fn(inp_obj)
    return result


register(Block(
    name="act",
    input_type="harness.operations.activities.act.ActInput",
    output_type="harness.operations.activities.act.ActResult",
    idempotent=False,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
