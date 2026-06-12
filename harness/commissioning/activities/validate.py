"""validate_activity — Stage 3 of commissioning: certify the BundleSpec
against a four-check Tier 0 ladder and record absent higher tiers.

Consequence class: REVERSIBLE (read-only analysis; no external side effects).
Idempotent: True — deterministic function of its inputs.

Tier 0 checks (always run):
  (a) Schema check — every agent has the 13 required fields with correct types;
      every flow has the 8 required fields; every vocab file has _note + list.
  (b) Structural comparison against the golden bundle-v0 — same key sets per
      file class; gates consistent with taxonomy; model_policy values pass
      _guard_model_id.  Comparison is SCHEMA-LEVEL (field names/types),
      never value-deep (operator-specific values legitimately differ).
      manifest.json is EXCLUDED from golden comparison (bundle-v0 has none).
  (c) Vector reproduction — every CalculationRule test vector is evaluated
      exactly against its expression using a restricted arithmetic evaluator.
  (d) Scenario simulation — for every ScenarioCard: each expected_stage ∈
      vocab.stages AND expected_outcome ∈ vocab.stages.

Tier 1/2: conditional stubs that record their absence in tiers_skipped with
a human-readable reason (fixture has no intake→outcome history / live process).

Golden comparison semantics:
  - _note prefix-match only ("Open set — append never edit." prefix required).
  - by_tool gate keys: only non-reversible tools must appear; assign_task
    appearing in by_tool in the emitted bundle (but not golden) is acceptable
    as a structural superset — comparison checks that ALL golden by_tool keys
    are present, not that the key sets are equal (gates may be more restrictive).

See docs/VALIDATION.md for the full tier ladder and compensation policy.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.contracts.commission import (
    BundleSpec,
    CalculationRule,
    DissectionResult,
    InterviewResult,
    ValidateActivityResult,
)
from harness.shared.contracts.infer import _guard_model_id

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"

# Required field names + expected Python types for agent and flow objects.
# Open-set: new fields are added here when the schema is extended.
_REQUIRED_AGENT_FIELDS: dict[str, type | tuple[type, ...]] = {
    "id": str,
    "department": str,
    "role": str,
    "objectives": list,
    "tool_allowlist": list,
    "autonomy_level": str,
    "gates": dict,
    "escalation_rules": dict,
    "model_policy": dict,
    "retrieval_budget": int,
    "step_budget": int,
    "token_budget": int,
    "version": (str, int),          # bundle-v0 has string "0"; new bundles may use int
}

_REQUIRED_FLOW_FIELDS: dict[str, type | tuple[type, ...]] = {
    "id": str,
    "version": str,
    "description": str,
    "trigger": dict,
    "workflow_type": str,
    "agent_id": str,
    "workflow_id_template": str,
    "goal_payload_template": dict,
}

_VOCAB_NOTE_PREFIX = "Open set — append never edit."


@dataclass
class ValidateActivityInput:
    bundle: BundleSpec
    interview: InterviewResult
    dissection: DissectionResult
    golden_bundle_path: str
    idempotency_key: str = ""


@activity.defn(name="commission_validate")
async def validate_activity(inp: ValidateActivityInput) -> ValidateActivityResult:
    """Stage 3: certify the BundleSpec.

    Runs Tier 0 unconditionally.  Records Tier 1/2 as skipped with reason.
    Sets bundle.tiers_run to ["tier0"] on a clean pass (caller updates the
    BundleSpec field — dataclasses are passed by value across activity boundaries
    so the workflow reconstructs the bundle with tiers_run set).

    Returns ValidateActivityResult with passed=False and failures populated
    if any Tier 0 check fails; does NOT raise — the workflow decides whether
    to propagate as ApplicationError.
    """
    import json

    failures: list[str] = []
    report: dict[str, Any] = {
        "tier0": {},
        "tier1": {},
        "tier2": {},
    }

    # ── (a) Schema check ──────────────────────────────────────────────────────
    schema_failures: list[str] = []

    for stem, agent_obj in inp.bundle.agents.items():
        for field_name, expected_type in _REQUIRED_AGENT_FIELDS.items():
            if field_name not in agent_obj:
                schema_failures.append(
                    f"agents/{stem}.json: missing required field '{field_name}'"
                )
            else:
                val = agent_obj[field_name]
                if not isinstance(val, expected_type):
                    schema_failures.append(
                        f"agents/{stem}.json: field '{field_name}' has type "
                        f"{type(val).__name__!r}, expected {expected_type}"
                    )

    for stem, flow_obj in inp.bundle.flows.items():
        for field_name, expected_type in _REQUIRED_FLOW_FIELDS.items():
            if field_name not in flow_obj:
                schema_failures.append(
                    f"flows/{stem}.json: missing required field '{field_name}'"
                )
            else:
                val = flow_obj[field_name]
                if not isinstance(val, expected_type):
                    schema_failures.append(
                        f"flows/{stem}.json: field '{field_name}' has type "
                        f"{type(val).__name__!r}, expected {expected_type}"
                    )

    for vocab_key, vocab_obj in inp.bundle.vocab.items():
        if "_note" not in vocab_obj:
            schema_failures.append(
                f"vocab/{vocab_key}.json: missing '_note' key"
            )
        else:
            note = vocab_obj["_note"]
            if not isinstance(note, str) or not note.startswith(_VOCAB_NOTE_PREFIX):
                schema_failures.append(
                    f"vocab/{vocab_key}.json: '_note' must start with "
                    f"'{_VOCAB_NOTE_PREFIX}', got {note!r}"
                )
        # Each vocab file must have at least one list-valued key besides _note.
        list_keys = [k for k, v in vocab_obj.items() if k != "_note" and isinstance(v, list)]
        if not list_keys:
            schema_failures.append(
                f"vocab/{vocab_key}.json: no list-valued payload key found"
            )

    report["tier0"]["schema"] = {
        "passed": len(schema_failures) == 0,
        "failures": schema_failures,
    }
    failures.extend(schema_failures)

    # ── (b) Structural comparison against golden bundle ───────────────────────
    golden_failures: list[str] = []

    golden_agent_path = os.path.join(
        inp.golden_bundle_path, "agents", "lead-qualifier-v0.json"
    )
    golden_flow_path = os.path.join(
        inp.golden_bundle_path, "flows", "lead-intake-first-follow-up.json"
    )

    if os.path.isfile(golden_agent_path):
        with open(golden_agent_path) as fh:
            golden_agent: dict[str, Any] = json.load(fh)
        for stem, agent_obj in inp.bundle.agents.items():
            # Schema-level: all golden fields must be present (key-set check).
            for gf in golden_agent:
                if gf not in agent_obj:
                    golden_failures.append(
                        f"agents/{stem}.json: golden field '{gf}' missing"
                    )
            # Gates consistency: golden by_tool keys must all appear in emitted by_tool.
            golden_by_tool = golden_agent.get("gates", {}).get("by_tool", {})
            emitted_by_tool = agent_obj.get("gates", {}).get("by_tool", {})
            for key in golden_by_tool:
                if key not in emitted_by_tool:
                    golden_failures.append(
                        f"agents/{stem}.json: gates.by_tool missing '{key}' "
                        f"(taxonomy says compensable/irreversible — golden requires approve-gated)"
                    )
            # model_policy values must pass the model-ID guard.
            mp = agent_obj.get("model_policy", {})
            for role_key, model_id in mp.items():
                try:
                    _guard_model_id(str(model_id))
                except ValueError as exc:
                    golden_failures.append(
                        f"agents/{stem}.json: model_policy['{role_key}'] rejected: {exc}"
                    )
    else:
        logger.warning(
            "validate_activity: golden agent not found at %s — skipping golden comparison",
            golden_agent_path,
        )

    if os.path.isfile(golden_flow_path):
        with open(golden_flow_path) as fh:
            golden_flow: dict[str, Any] = json.load(fh)
        for stem, flow_obj in inp.bundle.flows.items():
            for gf in golden_flow:
                if gf not in flow_obj:
                    golden_failures.append(
                        f"flows/{stem}.json: golden field '{gf}' missing"
                    )
    else:
        logger.warning(
            "validate_activity: golden flow not found at %s — skipping golden flow comparison",
            golden_flow_path,
        )

    report["tier0"]["golden_comparison"] = {
        "passed": len(golden_failures) == 0,
        "failures": golden_failures,
    }
    failures.extend(golden_failures)

    # ── (c) Vector reproduction ───────────────────────────────────────────────
    vector_failures: list[str] = []

    for rule in inp.dissection.calculation_rules:
        for i, vec in enumerate(rule.test_vectors):
            try:
                actual = _eval_expression(rule.expression, vec["inputs"])
                expected = vec["expected"]
                if actual != expected:
                    vector_failures.append(
                        f"rule '{rule.rule_id}' vector[{i}]: "
                        f"expression={rule.expression!r} "
                        f"inputs={vec['inputs']} "
                        f"expected={expected} got={actual}"
                    )
            except Exception as exc:
                vector_failures.append(
                    f"rule '{rule.rule_id}' vector[{i}]: evaluation error: {exc}"
                )

    report["tier0"]["vector_reproduction"] = {
        "passed": len(vector_failures) == 0,
        "rules_checked": len(inp.dissection.calculation_rules),
        "failures": vector_failures,
    }
    failures.extend(vector_failures)

    # ── (d) Scenario simulation ───────────────────────────────────────────────
    scenario_failures: list[str] = []

    # Collect all vocab stage names across all vocab files.
    all_stages: set[str] = set()
    for vocab_obj in inp.bundle.vocab.values():
        for key, val in vocab_obj.items():
            if key != "_note" and isinstance(val, list):
                # Include all string items — covers both stages list and task_types etc.
                all_stages.update(v for v in val if isinstance(v, str))

    for card in inp.interview.scenario_cards:
        for stage in card.expected_stages:
            if stage not in all_stages:
                scenario_failures.append(
                    f"card '{card.card_id}': expected_stage '{stage}' "
                    f"not in vocab stages {sorted(all_stages)}"
                )
        if card.expected_outcome not in all_stages:
            scenario_failures.append(
                f"card '{card.card_id}': expected_outcome '{card.expected_outcome}' "
                f"not in vocab stages {sorted(all_stages)}"
            )

    report["tier0"]["scenario_simulation"] = {
        "passed": len(scenario_failures) == 0,
        "cards_checked": len(inp.interview.scenario_cards),
        "failures": scenario_failures,
    }
    failures.extend(scenario_failures)

    # ── Tier 0 summary ────────────────────────────────────────────────────────
    tier0_passed = len(failures) == 0
    report["tier0"]["passed"] = tier0_passed
    tiers_run = ["tier0"] if tier0_passed else []

    # ── Tier 1/2: conditional — record absence with reason ────────────────────
    tiers_skipped: dict[str, str] = {
        "tier1": "no linked intake→outcome history in fixture (Phase E requires real corpus)",
        "tier2": "no comparable live process available (Phase E requires live telemetry)",
    }
    report["tier1"] = {"skipped": tiers_skipped["tier1"]}
    report["tier2"] = {"skipped": tiers_skipped["tier2"]}

    passed = tier0_passed

    logger.info(
        "validate_activity operator=%s passed=%s tier0=%s failures=%d",
        inp.bundle.bundle_id,
        passed,
        tier0_passed,
        len(failures),
    )

    return ValidateActivityResult(
        passed=passed,
        tiers_run=tiers_run,
        tiers_skipped=tiers_skipped,
        failures=failures,
        report=report,
    )


# ── Restricted arithmetic expression evaluator ───────────────────────────────

def _eval_expression(expression: str, inputs: dict[str, Any]) -> Any:
    """Evaluate a simple arithmetic assignment expression against input bindings.

    Only arithmetic operators (+, -, *, /, **, //, %) and numeric literals are
    permitted.  No builtins, no attribute access, no function calls.

    Supports: "score = 2*budget_match + 1*timeline_match"
    The left-hand side is the variable name to return.

    Raises ValueError for malformed or unsafe expressions.
    """
    import ast

    # Expect "lhs = rhs" form.
    if "=" not in expression:
        raise ValueError(f"expression must be an assignment: {expression!r}")

    lhs, _, rhs = expression.partition("=")
    lhs = lhs.strip()
    rhs = rhs.strip()

    # Parse the RHS as an AST and validate it contains only safe nodes.
    try:
        tree = ast.parse(rhs, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"expression parse error: {exc}") from exc

    _validate_ast_node(tree.body)

    # Evaluate with only the input bindings available.
    namespace = dict(inputs)
    # pylint: disable=eval-used
    result = eval(compile(tree, filename="<expression>", mode="eval"), {"__builtins__": {}}, namespace)  # noqa: S307
    return result


def _validate_ast_node(node: Any) -> None:
    """Recursively validate that an AST node contains only safe arithmetic."""
    import ast

    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Name,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.UAdd,
        ast.USub,
        ast.Load,
    )
    if not isinstance(node, allowed):
        raise ValueError(
            f"unsafe AST node {type(node).__name__!r} in expression — "
            "only arithmetic operators and name lookups are permitted"
        )
    for child in ast.iter_child_nodes(node):
        _validate_ast_node(child)


register(Block(
    name="commission_validate",
    input_type="harness.commissioning.activities.validate.ValidateActivityInput",
    output_type="harness.shared.contracts.commission.ValidateActivityResult",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
