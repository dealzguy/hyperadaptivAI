# DISSECTION.md — Stage 1: Dissect

**Status:** Normative for Stage 1 of the commissioning pipeline. Implemented in
`harness/commissioning/activities/dissect.py`. Live-inference mode is deferred to
Phase E; stub mode is the current implementation.

---

## 1. Purpose

Stage 1 takes an `InterviewResult` and extracts four things:

1. **Primitive mappings** — operator vocabulary concepts mapped to the five CRM
   primitives.
2. **Archetype + switches** — the workflow archetype that best matches the operator's
   process, plus behavioural switch values.
3. **Calculation rules** — deterministic scoring rules with test vectors lifted
   verbatim from the fixture.
4. **Consequence taxonomy** — inherited from the interview, possibly corrected by a
   human reviewer via the `submit_correction` signal.

Stage 1 may run more than once within a single commissioning workflow execution if
the human reviewer submits corrections (see §5). The round number is tracked in
`DissectionResult.round`.

---

## 2. Extraction Targets

### 2.1 Data → Five CRM Primitives

[PROD] The five CRM primitives are an open set of strings (Invariant 3 — no Python enum).
The standard five are:

| Primitive | What it models | Example mapping |
|---|---|---|
| `entity` | A persistent business object | `"lead"` → entity `"lead"` |
| `state` | Lifecycle state machine | `"lead lifecycle"` → state `"lead_lifecycle"` |
| `event` | A fact that occurred | `"qualification assessment"` → event `"qualification_assessment"` |
| `relationship` | A link between entities | `"agent-lead relationship"` → relationship `"agent_lead"` |
| `task` | A work item to be done | `"first follow-up"` → task `"first_follow_up"` |

Each `PrimitiveMapping` carries provenance pointing at the fixture JSON path that
authorised the mapping:

```python
PrimitiveMapping(
    source_concept="lead",
    primitive="entity",
    target_name="lead",
    provenance={
        "source": "fixture:<path>",
        "path": "$.business.sold_to_whom",
        "round": 0,
    },
)
```

### 2.2 Process → Archetype + Switches

The archetype is selected by matching the operator's process shape to the archetype
template table in `construct.py` (`_ARCHETYPE_TEMPLATES`, open dict). For Phase D
only `"lead_qualification"` is registered.

Switches are baseline values from the archetype's template entry:

```python
{
    "autonomy_level":        "gated",
    "escalate_to":           "human_task",
    "confidence_threshold":  0.5,
}
```

[PROD] Switch values are config data, not code. New archetypes append new entries to
`_ARCHETYPE_TEMPLATES`; the archetype name and its baseline switches are data in
that table, not Python constants.

### 2.3 Calculations → Rules with Real Test Vectors

Calculation rules are lifted verbatim from `$.calculations` in the fixture. [PROD] The
vector-lifting rule is absolute: **test vectors must come from real fixture
artifacts, never be invented**. The fixture is re-opened during the dissect
activity via the provenance source path recorded in the interview's taxonomy.

Each `CalculationRule` carries provenance:

```python
CalculationRule(
    rule_id="lead-score-v0",
    description="Weighted lead score ...",
    expression="score = 2*budget_match + 1*timeline_match",
    test_vectors=[
        {"inputs": {"budget_match": 1, "timeline_match": 1}, "expected": 3},
        {"inputs": {"budget_match": 0, "timeline_match": 1}, "expected": 1},
        {"inputs": {"budget_match": 1, "timeline_match": 0}, "expected": 2},
        {"inputs": {"budget_match": 0, "timeline_match": 0}, "expected": 0},
    ],
    provenance={
        "source": "fixture:<path>",
        "path": "$.calculations[?(@.rule_id=='lead-score-v0')]",
        "round": 0,
    },
)
```

### 2.4 Consequence Taxonomy

[PROD] The consequence taxonomy is inherited from `InterviewResult.consequence_taxonomy`
and carried forward into `DissectionResult.consequence_taxonomy`. It may be
modified by:

- Fault injection (discipline test, see §4).
- Correction application (human review, see §5).

---

## 3. Provenance Format

[PROD] Every provenance dict follows this schema:

```python
{
    "source": "fixture:<path>",        # e.g. "fixture:fixtures/commission_fixture_01.json"
    "path": "$.<json-path>",           # JSONPath expression within the fixture
    "round": <int>,                    # dissect round number (0 = first pass)
}
```

For taxonomy provenance, two additional keys may appear:

- `"fault"` — populated when fault injection is active (see §4).
- `"correction"` — populated when a correction is applied (see §5).

[PROD] These keys serve as branch-node locators in the audit trail: a reviewer or debugger
can pinpoint exactly where the taxonomy diverged from the fixture values.

---

## 4. Fault Injection (Discipline Test)

[DEV] The discipline test verifies that the commissioning pipeline can detect and correct
a wrong consequence classification before promoting the bundle.

[DEV] Activation: `DissectActivityInput(inject_fault=True, round=0, correction=None)`.
This condition is honoured **only on round 0**. If `correction` is not None or
`round > 0`, fault injection is skipped.

What it does: sets `by_tool["transition_state"] = "reversible"` (the correct value
per the fixture is `"compensable"`). This causes `construct_activity` to exclude
`transition_state` from `gates.by_tool`, and `validate_activity` to fail Tier 0
with a failure message naming the field:

```
agents/<stem>.json: gates.by_tool missing 'transition_state'
(taxonomy says compensable/irreversible — golden requires approve-gated)
```

Provenance stamp:

```python
taxonomy_provenance["fault"] = {
    "injected_at": "dissect:round0",
    "field":       "by_tool.transition_state",
    "injected_value": "reversible",
    "correct_value":  "compensable",
}
```

The `DissectionResult.fault_injected` field is set to `True` and recorded in the
top-level provenance dict. Test `test_discipline_correction` polls `get_artifacts()`
and asserts that `provenance.fault` is present in the round-0 artifact before
sending `submit_correction`.

---

## 5. Correction Mechanism (Branch Rollback)

When `auto_advance_dissect=False`, the commissioning workflow pauses at
`"dissect_review"` after each dissect round and waits for one of two signals:

- `advance_stage()` — accept the current round; exit the dissect loop.
- `submit_correction(correction: dict)` — apply a correction and re-run dissect
  from the corrected state (rollback-regenerate).

### 5.1 Correction Dict Format

```python
{
    "target":   "consequence_taxonomy.by_tool.transition_state",
    "value":    "compensable",
    "evidence": "fixture $.tools[1].consequence_class",
}
```

| Field | Description |
|---|---|
| `target` | Dotted path to the field being corrected. Currently only `consequence_taxonomy.by_tool.<tool_name>` is supported. |
| `value` | The corrected value. |
| `evidence` | Human-readable justification, typically citing the fixture path. |

### 5.2 Rollback-Regenerate Semantics

[PROD] "Branch rollback" is implemented as a typed correction loop within one Temporal
workflow execution — not as a `temporal workflow reset`. The history records each
dissect round as a distinct activity execution. The workflow state machine re-runs
Stage 1 with the corrected input; Stages 2–4 only run after the loop exits.

This differs from the literal "native Temporal reset" phrasing in Doc 12 and is
flagged explicitly as a design decision. [PROD] The typed loop is replay-safe and
deterministic; a literal workflow reset would not have access to the correction
signal data within the same execution.

The `CommissioningResult.dissect_rounds` field records how many dissect rounds
were needed (1 = no corrections, 2+ = corrections applied).

### 5.3 Provenance Trail After Correction

```python
taxonomy_provenance["correction"] = {
    "target":          "consequence_taxonomy.by_tool.transition_state",
    "old_value":       "reversible",
    "new_value":       "compensable",
    "evidence":        "fixture $.tools[1].consequence_class",
    "applied_at_round": 1,
}
```

[PROD] The correction provenance is written into the taxonomy that `DissectionResult`
carries. Downstream activities (construct, validate) receive only the corrected
taxonomy; the workflow's `_corrections_applied` list records the full history.

---

## 6. Signal Race Avoidance

[PROD] `self._dissect_reviewed = False` is reset at the **top** of each iteration of the
dissect loop, **before** the `execute_activity` call. This ensures a signal that
arrives during the activity execution is not clobbered by the reset. The pattern
is documented in the `CommissioningWorkflow` module docstring.

---

## 7. DissectionResult Schema

```python
@dataclass
class DissectionResult:
    primitive_mappings:   list[PrimitiveMapping]
    archetype:            str          # e.g. "lead_qualification"
    switches:             dict         # {"autonomy_level": "gated", ...}
    calculation_rules:    list[CalculationRule]   # >= 1 with real test vectors
    consequence_taxonomy: ConsequenceTaxonomy     # from interview, possibly corrected
    round:                int          # 0 = first pass; bumped on correction loop
    fault_injected:       bool         # discipline-test marker
    provenance:           dict         # {"source": ..., "dissect_round": ..., "fault_injected": ...}
```

---

## 8. Block Registration

```python
Block(
    name="commission_dissect",
    consequence_class=ConsequenceClass.REVERSIBLE,
    idempotent=False,
    version="0.1.0",
)
```

[PROD] REVERSIBLE because dissect performs analysis only — no external side effects.
[PROD] `idempotent=False` because live-inference calls are nondeterministic (stub mode is
deterministic but the block registration reflects the live-mode contract).

---

## 9. Live Mode (Phase E)

Raises `NotImplementedError`. The live implementation should:

1. Receive the `InterviewResult` as context.
2. [PROD] Call `infer()` to produce primitive mappings, archetype selection, and
   archetype switch recommendations.
3. [PROD] Validate all five primitive types are covered (entity, state, event,
   relationship, task) — if any are missing, issue a targeted follow-up call.
4. [PROD] Lift calculation rules from the fixture (not from the model — vectors must
   always come from real artifacts, never from model output).
5. [PROD] Return `DissectionResult` with the same schema as stub mode.
