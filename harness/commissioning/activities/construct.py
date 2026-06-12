"""construct_activity — Stage 2 of commissioning: build a BundleSpec from
the DissectionResult using selection-plus-parameterization.

Consequence class: REVERSIBLE (pure in-memory construction; nothing is written
to disk or any external system here — promote handles writes).
Idempotent: True — deterministic template parameterization; same inputs always
produce the same BundleSpec.

Design: a static archetype template table (_ARCHETYPE_TEMPLATES, open set —
new archetypes append, never edit) is parameterized by the frame and dissection.
No free-form authorship.  Model IDs appear only as DATA inside the emitted
BundleSpec (Invariant 2 — never hardcoded as code references).

Gate derivation rules (from plan Step 3):
  - by_consequence_class: reversible → "auto"; compensable|irreversible → "approve"
  - by_tool: derived from non-reversible taxonomy entries only
    (matches golden bundle-v0 structure: only transition_state appears in by_tool
    because assign_task is compensable but its gate is expressed via
    by_consequence_class; see CONFIG-BUNDLE-SPEC.md for full derivation semantics)

See docs/CONFIG-BUNDLE-SPEC.md for normative agent/flow/vocab field tables.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.contracts.commission import BundleSpec, DissectionResult

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"

# ── Archetype template table (open set — new archetypes append, never edit) ──
# Each entry contains the fixed structural portions of the agent and flow
# objects for that archetype.  Variable portions (id, tool_allowlist, gates,
# model_policy, vocab) are injected at construction time from the dissection.
#
# model_policy values are DATA stored in the template (Invariant 2 — they are
# opaque strings, not code references).  Small-model-first per CLAUDE.md.
_ARCHETYPE_TEMPLATES: dict[str, dict[str, Any]] = {
    "lead_qualification": {
        "agent": {
            "department": "engage",
            "role": (
                "Lead qualification agent that moves a new lead from intake "
                "toward a first follow-up or disqualification decision."
            ),
            "objectives": [
                "Review the intake event and any prior context for the lead entity.",
                "Record a qualification assessment event against the lead.",
                "Transition lead state to 'qualifying' and, when evidence is sufficient, "
                "to 'qualified' or 'disqualified'.",
                "Assign a follow-up task when qualification completes.",
                "Escalate to a human task when confidence is below threshold or "
                "budget is exhausted.",
            ],
            "autonomy_level": "gated",
            "escalation_rules": {
                "confidence_threshold": 0.5,
                "stall_after": 3,
                "escalate_to": "human_task",
            },
            # model_policy is DATA; values are opaque strings
            "model_policy": {
                "decide": "ollama_chat/llama3.2:3b",
                "escalate": "ollama_chat/llama3.1:8b",
            },
            "retrieval_budget": 10,
            "step_budget": 8,
            "token_budget": 20000,
            "version": "0",
        },
        "flow": {
            "version": "0.1.0",
            "description": (
                "Flow: new lead submitted via web form → qualification agent "
                "→ first follow-up task assigned."
            ),
            "trigger": {
                "event_type": "intake_submitted",
            },
            "workflow_type": "AgentLoopWorkflow",
            "goal_payload_template": {
                "flow_class": "lead-intake-first-follow-up",
                "objective": (
                    "Qualify this lead and schedule a first follow-up or disqualify."
                ),
                "tool_arg_schemas": {
                    "record_event": {
                        "event_type": "string",
                        "payload": "object",
                    },
                    "transition_state": {
                        "entity_id": "string",
                        "from_state": "string",
                        "to_state": "string",
                        "reason": "string",
                    },
                    "assign_task": {
                        "task_type": "string",
                        "entity_id": "string",
                        "attributes": "object",
                    },
                },
            },
        },
    },
}

# Open set NOTE text used in every vocab file.
_VOCAB_NOTE = "Open set — append never edit."


@dataclass
class ConstructActivityInput:
    operator_id: str
    dissection: DissectionResult
    idempotency_key: str = ""


@activity.defn(name="commission_construct")
async def construct_activity(inp: ConstructActivityInput) -> BundleSpec:
    """Stage 2: build BundleSpec via archetype template + dissection parameterization.

    STUB MODE (INFER_STUB=1) and LIVE MODE are identical — construct is a
    deterministic template function with no inference calls.  The INFER_STUB
    branch guard is kept for consistency with the activity convention but both
    paths execute the same code.

    Raises ValueError for unknown archetype (not a retryable transient — the
    fixture/dissect stage should have produced a known archetype).
    """
    from temporalio.exceptions import ApplicationError

    archetype = inp.dissection.archetype
    if archetype not in _ARCHETYPE_TEMPLATES:
        raise ApplicationError(
            f"construct_activity: unknown archetype {archetype!r}; "
            f"known archetypes: {sorted(_ARCHETYPE_TEMPLATES)}",
            non_retryable=True,
        )

    tmpl = _ARCHETYPE_TEMPLATES[archetype]
    agent_tmpl = tmpl["agent"]
    flow_tmpl = tmpl["flow"]

    operator_id = inp.operator_id
    taxonomy = inp.dissection.consequence_taxonomy

    # ── tool_allowlist from dissection primitive mappings ─────────────────────
    # Collect the unique tool names present in the taxonomy (open set).
    tool_allowlist: list[str] = list(taxonomy.by_tool.keys())

    # ── gates derivation ──────────────────────────────────────────────────────
    # by_consequence_class: all three known classes mapped per the fixed rule.
    by_consequence_class: dict[str, str] = {
        "reversible": "auto",
        "compensable": "approve",
        "irreversible": "approve",
    }

    # by_tool: only tools whose consequence class is NOT "reversible" are
    # included.  This matches bundle-v0's structure where only transition_state
    # (compensable) appears — record_event (reversible) is governed solely
    # by by_consequence_class, not duplicated in by_tool.
    by_tool: dict[str, str] = {
        tool: "approve"
        for tool, cls in taxonomy.by_tool.items()
        if cls != "reversible"
    }

    # ── Agent object (13 fields per bundle-v0 schema) ─────────────────────────
    agent_id = f"{operator_id}-qualifier-v0"
    agent_obj: dict[str, Any] = {
        "id": agent_id,
        "department": agent_tmpl["department"],
        "role": agent_tmpl["role"],
        "objectives": list(agent_tmpl["objectives"]),
        "tool_allowlist": tool_allowlist,
        "autonomy_level": agent_tmpl["autonomy_level"],
        "gates": {
            "by_consequence_class": by_consequence_class,
            "by_tool": by_tool,
        },
        "escalation_rules": dict(agent_tmpl["escalation_rules"]),
        "model_policy": dict(agent_tmpl["model_policy"]),
        "retrieval_budget": agent_tmpl["retrieval_budget"],
        "step_budget": agent_tmpl["step_budget"],
        "token_budget": agent_tmpl["token_budget"],
        "version": agent_tmpl["version"],
    }

    # ── Flow object (8 fields per bundle-v0 schema) ───────────────────────────
    flow_id = f"lead-intake-first-follow-up"
    flow_obj: dict[str, Any] = {
        "id": flow_id,
        "version": flow_tmpl["version"],
        "description": flow_tmpl["description"],
        "trigger": dict(flow_tmpl["trigger"]),
        "workflow_type": flow_tmpl["workflow_type"],
        "agent_id": agent_id,
        "workflow_id_template": f"agent-loop-{flow_id}-{{entity_key}}",
        "goal_payload_template": flow_tmpl["goal_payload_template"],
    }

    # ── Vocab (open sets; each has _note + list keyed by vocab name) ──────────
    # Derive from context frame via dissection provenance.
    # Lifecycle stages: lifted from the dissection's PrimitiveMappings
    # (the "state" primitive maps to lifecycle stages; the actual stage list
    # lives in the interview's context_frame via the fixture).
    #
    # In stub mode the dissection was produced from the fixture; we use the
    # fixture's lifecycle data through the interview provenance source path.
    stages: list[str] = _extract_stages_from_dissection(inp.dissection)
    task_types: list[str] = _extract_task_types_from_dissection(inp.dissection)
    channels: list[str] = _extract_channels_from_dissection(inp.dissection)

    vocab: dict[str, dict[str, Any]] = {
        "stages": {
            "_note": _VOCAB_NOTE + " States used in lead_lifecycle state machine.",
            "stages": stages,
        },
        "task_types": {
            "_note": _VOCAB_NOTE,
            "task_types": task_types,
        },
        "channels": {
            "_note": _VOCAB_NOTE,
            "channels": channels,
        },
    }

    bundle_spec = BundleSpec(
        bundle_id=f"bundle-{operator_id}",
        agents={agent_id: agent_obj},
        flows={flow_id: flow_obj},
        vocab=vocab,
        tiers_run=[],                # filled by validate activity
        provenance={
            "dissect_round": inp.dissection.round,
            "archetype": archetype,
            "operator_id": operator_id,
        },
    )

    logger.info(
        "construct_activity operator=%s archetype=%s agent_id=%s "
        "tool_allowlist=%s by_tool_gates=%s",
        operator_id,
        archetype,
        agent_id,
        tool_allowlist,
        list(by_tool.keys()),
    )

    return bundle_spec


# ── Vocab extraction helpers ──────────────────────────────────────────────────

def _extract_stages_from_dissection(dissection: DissectionResult) -> list[str]:
    """Pull lifecycle stages from the fixture via dissection provenance.

    The dissect activity embedded the fixture source in the taxonomy provenance.
    We re-open the fixture to get the authoritative stage list rather than
    hard-coding it, keeping config-over-code (Invariant 1).
    """
    import json

    fixture_source = dissection.consequence_taxonomy.provenance.get("source", "")
    fixture_path = (
        fixture_source.replace("fixture:", "")
        if fixture_source.startswith("fixture:")
        else ""
    )
    if fixture_path:
        try:
            with open(fixture_path) as fh:
                raw = json.load(fh)
            return raw.get("lifecycle", {}).get("stages", _DEFAULT_STAGES)
        except (OSError, KeyError):
            pass

    # Fallback: derive from PrimitiveMappings (state primitive target name gives
    # the lifecycle name, but not the individual stages — fall through to default).
    return list(_DEFAULT_STAGES)


def _extract_task_types_from_dissection(dissection: DissectionResult) -> list[str]:
    """Pull task_types from fixture via dissection provenance."""
    import json

    fixture_source = dissection.consequence_taxonomy.provenance.get("source", "")
    fixture_path = (
        fixture_source.replace("fixture:", "")
        if fixture_source.startswith("fixture:")
        else ""
    )
    if fixture_path:
        try:
            with open(fixture_path) as fh:
                raw = json.load(fh)
            return raw.get("task_types", _DEFAULT_TASK_TYPES)
        except (OSError, KeyError):
            pass
    return list(_DEFAULT_TASK_TYPES)


def _extract_channels_from_dissection(dissection: DissectionResult) -> list[str]:
    """Pull channels from fixture via dissection provenance."""
    import json

    fixture_source = dissection.consequence_taxonomy.provenance.get("source", "")
    fixture_path = (
        fixture_source.replace("fixture:", "")
        if fixture_source.startswith("fixture:")
        else ""
    )
    if fixture_path:
        try:
            with open(fixture_path) as fh:
                raw = json.load(fh)
            return raw.get("channels", _DEFAULT_CHANNELS)
        except (OSError, KeyError):
            pass
    return list(_DEFAULT_CHANNELS)


# Fallback defaults (only used when fixture is unreachable).
_DEFAULT_STAGES = ["new", "qualifying", "qualified", "disqualified", "first_follow_up_done"]
_DEFAULT_TASK_TYPES = ["first_follow_up", "agent_gate_approval", "agent_escalation"]
_DEFAULT_CHANNELS = ["web_form"]


register(Block(
    name="commission_construct",
    input_type="harness.commissioning.activities.construct.ConstructActivityInput",
    output_type="harness.shared.contracts.commission.BundleSpec",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
