"""dissect_activity — Stage 1 of commissioning: map the InterviewResult to CRM
primitives, derive archetype/switches, lift calculation rules from fixture.

Consequence class: REVERSIBLE (analysis only; no external side effects).
Idempotent: False — live inference is nondeterministic.  The idempotency_key
field is accepted for logging/audit tracing only, not for deduplication.
NOTE: INFER_STUB=1 env var enables deterministic fixture-based output for testing.

Discipline-test support:
  - inject_fault=True, round==0, correction==None: emits "reversible" for
    transition_state (correct value is "compensable"). Provenance stamps
    {"fault": {"injected_at": "dissect:round0", "field": "by_tool.transition_state"}}
    so the branch node is locatable in the artifact trail.
  - correction dict: {"target": "consequence_taxonomy.by_tool.<tool>",
                      "value": "<class>", "evidence": "<justification>"}
    Applied to the taxonomy, bumping round. Downstream-of-taxonomy fields
    (gates derivation) re-derive in construct; dissect just emits corrected
    taxonomy + bumped round.

See docs/DISSECTION.md for extraction targets, provenance format, and
vector-lifting rule (vectors must come from real artifacts, never invented).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.contracts.commission import (
    CalculationRule,
    ConsequenceTaxonomy,
    DissectionResult,
    InterviewResult,
    PrimitiveMapping,
)

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"

# ── Archetype template table (open set — new archetypes append, never edit) ───
# Each entry maps an archetype name to its baseline switches.
_ARCHETYPE_SWITCHES: dict[str, dict[str, Any]] = {
    "lead_qualification": {
        "autonomy_level": "gated",
        "escalate_to": "human_task",
        "confidence_threshold": 0.5,
    },
}


@dataclass
class DissectActivityInput:
    interview: InterviewResult
    round: int = 0
    inject_fault: bool = False          # honoured ONLY when round == 0 and correction is None
    correction: dict[str, Any] | None = None   # {"target": "consequence_taxonomy.by_tool.<tool>",
                                               #  "value": "<class>", "evidence": "<text>"}
    idempotency_key: str = ""


@activity.defn(name="commission_dissect")
async def dissect_activity(inp: DissectActivityInput) -> DissectionResult:
    """Stage 1: extract primitive mappings, archetype, switches, and calc rules.

    STUB MODE (INFER_STUB=1): derives all outputs deterministically from the
    InterviewResult that was itself derived from the fixture in stub mode.

    LIVE MODE: calls infer() per docs/DISSECTION.md prompt templates.
    Not yet implemented for Phase D (Phase E).
    """
    if os.environ.get("INFER_STUB") == "1":
        frame = inp.interview.context_frame

        # ── Primitive mappings from frame vocabulary ──────────────────────────
        prov_frame = {
            "source": inp.interview.context_frame.provenance.get("source", "interview"),
            "round": inp.round,
        }
        primitive_mappings: list[PrimitiveMapping] = [
            PrimitiveMapping(
                source_concept="lead",
                primitive="entity",
                target_name="lead",
                provenance={**prov_frame, "path": "$.business.sold_to_whom"},
            ),
            PrimitiveMapping(
                source_concept="lead lifecycle",
                primitive="state",
                target_name="lead_lifecycle",
                provenance={**prov_frame, "path": "$.lifecycle.stages"},
            ),
            PrimitiveMapping(
                source_concept="qualification assessment",
                primitive="event",
                target_name="qualification_assessment",
                provenance={**prov_frame, "path": "$.business.what_is_sold"},
            ),
            PrimitiveMapping(
                source_concept="agent-lead relationship",
                primitive="relationship",
                target_name="agent_lead",
                provenance={**prov_frame, "path": "$.business.sold_to_whom"},
            ),
            PrimitiveMapping(
                source_concept="first follow-up",
                primitive="task",
                target_name="first_follow_up",
                provenance={**prov_frame, "path": "$.task_types"},
            ),
        ]

        # ── Archetype + switches ──────────────────────────────────────────────
        archetype = "lead_qualification"
        switches = dict(_ARCHETYPE_SWITCHES.get(archetype, {}))

        # ── Calculation rules lifted from the interview's context frame ───────
        # Vectors come from the original fixture via the context_frame's provenance;
        # they are embedded in the fixture under $.calculations and surfaced here
        # verbatim (vector-lifting rule: never invent, always from real artifacts).
        #
        # In stub mode the interview_activity already read the fixture; we
        # reconstruct rule data from the interview provenance source.
        import json
        fixture_source = frame.provenance.get("source", "")
        fixture_path = fixture_source.replace("fixture:", "") if fixture_source.startswith("fixture:") else ""

        calculation_rules: list[CalculationRule] = []
        if fixture_path:
            try:
                with open(fixture_path) as fh:
                    raw = json.load(fh)
                for calc in raw.get("calculations", []):
                    calculation_rules.append(CalculationRule(
                        rule_id=calc["rule_id"],
                        description=calc["description"],
                        expression=calc["expression"],
                        test_vectors=calc["test_vectors"],
                        provenance={
                            "source": fixture_source,
                            "path": f"$.calculations[?(@.rule_id=='{calc['rule_id']}')]",
                            "round": inp.round,
                        },
                    ))
            except (OSError, KeyError) as exc:
                logger.warning("dissect_activity: could not load calc rules from %s: %s", fixture_path, exc)

        # ── Consequence taxonomy (from interview, possibly fault-injected or corrected) ─
        # Start from the taxonomy captured during interview.
        by_tool: dict[str, str] = dict(inp.interview.consequence_taxonomy.by_tool)
        taxonomy_provenance: dict[str, Any] = dict(inp.interview.consequence_taxonomy.provenance)
        taxonomy_provenance["round"] = inp.round

        fault_injected = False

        if inp.inject_fault and inp.round == 0 and inp.correction is None:
            # Discipline test: deliberately emit wrong class for transition_state.
            # The correct value per the fixture is "compensable"; we emit "reversible"
            # so validate catches it and the operator must submit_correction.
            by_tool["transition_state"] = "reversible"
            fault_injected = True
            taxonomy_provenance["fault"] = {
                "injected_at": "dissect:round0",
                "field": "by_tool.transition_state",
                "injected_value": "reversible",
                "correct_value": "compensable",
            }
            logger.info(
                "dissect_activity FAULT INJECTED operator=%s round=%d "
                "field=by_tool.transition_state injected=reversible",
                frame.operator_id,
                inp.round,
            )

        # Apply correction if provided (from submit_correction signal).
        if inp.correction is not None:
            target: str = inp.correction.get("target", "")
            value: str = inp.correction.get("value", "")
            evidence: str = inp.correction.get("evidence", "")
            # target format: "consequence_taxonomy.by_tool.<tool_name>"
            if target.startswith("consequence_taxonomy.by_tool."):
                tool_name = target[len("consequence_taxonomy.by_tool."):]
                old_value = by_tool.get(tool_name, "<not-set>")
                by_tool[tool_name] = value
                taxonomy_provenance["correction"] = {
                    "target": target,
                    "old_value": old_value,
                    "new_value": value,
                    "evidence": evidence,
                    "applied_at_round": inp.round,
                }
                logger.info(
                    "dissect_activity CORRECTION applied operator=%s round=%d "
                    "tool=%s old=%s new=%s",
                    frame.operator_id,
                    inp.round,
                    tool_name,
                    old_value,
                    value,
                )

        consequence_taxonomy = ConsequenceTaxonomy(
            by_tool=by_tool,
            provenance=taxonomy_provenance,
        )

        result = DissectionResult(
            primitive_mappings=primitive_mappings,
            archetype=archetype,
            switches=switches,
            calculation_rules=calculation_rules,
            consequence_taxonomy=consequence_taxonomy,
            round=inp.round,
            fault_injected=fault_injected,
            provenance={
                "source": frame.provenance.get("source", "interview"),
                "dissect_round": inp.round,
                "fault_injected": fault_injected,
            },
        )

        logger.info(
            "dissect_activity STUB mode operator=%s round=%d archetype=%s "
            "mappings=%d rules=%d fault=%s",
            frame.operator_id,
            inp.round,
            archetype,
            len(primitive_mappings),
            len(calculation_rules),
            fault_injected,
        )

        return result

    # ── Live mode ─────────────────────────────────────────────────────────────
    raise NotImplementedError(
        "Live dissect inference: implement in Phase E with real operator corpus. "
        "See docs/DISSECTION.md for extraction targets and prompt templates."
    )


register(Block(
    name="commission_dissect",
    input_type="harness.commissioning.activities.dissect.DissectActivityInput",
    output_type="harness.shared.contracts.commission.DissectionResult",
    idempotent=False,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
