# VALIDATION.md — Stage 3: Validation Ladder

**Status:** Normative for Stage 3 of the commissioning pipeline. Implemented in
`harness/commissioning/activities/validate.py`.

---

## 1. Purpose

Stage 3 certifies the `BundleSpec` produced by `construct_activity` before the
bundle is written to disk by `promote_activity`. A bundle that fails certification
is never promoted: `CommissioningWorkflow.run()` raises a non-retryable
`ApplicationError` on validation failure, and `promote_activity` independently
guards against an uncertified bundle reaching disk.

Validation runs a tiered ladder. Tier 0 always runs. Tiers 1 and 2 are conditional
on the availability of data that Phase D fixtures do not yet supply; their absence
is recorded explicitly and never treated as a pass.

---

## 2. Validation Tier Ladder

### Tier 0 — Always Run

Tier 0 has four independent checks. All four must pass for `ValidateActivityResult.passed`
to be `True`. Failure in any check populates `failures` with an offending field path
and sets `passed=False`.

#### (a) Schema Check

Every agent object must contain all 13 required fields with correct Python types.
Every flow object must contain all 8 required fields. Every vocab file must have a
`_note` key whose value starts with `"Open set — append never edit."` and at least
one list-valued payload key.

The required field sets are defined as open dicts in `validate.py`:
`_REQUIRED_AGENT_FIELDS` (13 entries) and `_REQUIRED_FLOW_FIELDS` (8 entries). New
fields are added to these dicts when the schema is extended.

Failure format: `"agents/<stem>.json: missing required field '<field>'"` or
`"agents/<stem>.json: field '<field>' has type '<actual>', expected <expected>"`.

#### (b) Structural Comparison Against Golden Bundle

The golden bundle is `config/bundle-v0/`. Comparison is **schema-level** (key sets
and structural consistency), never value-deep — operator-specific values legitimately
differ from the golden example.

What is compared:

- **Agent key sets:** every field present in `config/bundle-v0/agents/lead-qualifier-v0.json`
  must also be present in the emitted agent object. The emitted object may have
  additional fields (acceptable superset).
- **Flow key sets:** every field present in `config/bundle-v0/flows/lead-intake-first-follow-up.json`
  must be present in the emitted flow.
- **`gates.by_tool`:** all keys in golden `by_tool` must appear in the emitted `by_tool`.
  The emitted bundle may have additional `by_tool` keys (more restrictive gating
  is acceptable; fewer keys than the golden is a certification failure).
- **`model_policy` guard:** every value in `agent.model_policy` is passed through
  `_guard_model_id()`. A value not starting with `"ollama/"` or `"ollama_chat/"` is
  a certification failure.
- **`manifest.json`:** explicitly excluded from golden comparison. Bundle-v0 has no
  manifest.json; the comparison skips this file entirely.
- **`_note` prefix-match:** vocab file notes are checked with `startswith("Open set — append never edit.")` only — the suffix (e.g. `"States used in lead_lifecycle state machine."`) may differ between bundles.

Failure format: `"agents/<stem>.json: golden field '<field>' missing"` or
`"agents/<stem>.json: gates.by_tool missing 'transition_state' (taxonomy says compensable/irreversible — golden requires approve-gated)"`.

#### (c) Vector Reproduction

Every `CalculationRule` in `DissectionResult.calculation_rules` is evaluated
against each of its `test_vectors`. The evaluation uses a restricted arithmetic AST
evaluator (`_eval_expression` in `validate.py`):

- Only arithmetic operators: `+`, `-`, `*`, `/`, `//`, `%`, `**`.
- No builtins, no attribute access, no function calls — any other AST node type
  raises `ValueError`.
- The expression must be in assignment form: `"lhs = rhs"`. The LHS variable name
  is the result to return.
- Input bindings come from `vec["inputs"]`; the evaluator returns `vec["expected"]`
  for comparison.

This check verifies that calculation rules are deterministically reproducible
without a model call.

Failure format:
`"rule '<rule_id>' vector[<i>]: expression=<expr> inputs=<inputs> expected=<expected> got=<actual>"`.

#### (d) Scenario Simulation

For every `ScenarioCard` in `InterviewResult.scenario_cards`:

- Each value in `card.expected_stages` must be present in the union of all list
  values in all vocab files (`vocab.stages.stages`, plus any other list-valued vocab
  keys).
- `card.expected_outcome` must be present in the same set.

This ensures the scenario paths are self-consistent with the emitted vocabulary —
a stage name referenced in a scenario card but missing from `vocab/stages.json`
would cause a runtime state-machine failure in production.

Failure format:
`"card '<card_id>': expected_stage '<stage>' not in vocab stages [...]"` or
`"card '<card_id>': expected_outcome '<outcome>' not in vocab stages [...]"`.

---

### Tier 1 — Historical Outcome Comparison (Conditional)

**Condition:** availability of linked intake → outcome history for the operator
(real transaction records from a live or pilot deployment).

**Phase D status:** SKIPPED. Reason recorded in `tiers_skipped`:
`"no linked intake→outcome history in fixture (Phase E requires real corpus)"`.

**When implemented (Phase E):** compare the emitted lifecycle stages and scoring
rules against observed conversion paths in historical data. Detect systematic
mismatches between scenario-card assumptions and actual deal shapes.

---

### Tier 2 — Comparable Live-Process Benchmark (Conditional)

**Condition:** availability of a live comparable process for A/B-style comparison.

**Phase D status:** SKIPPED. Reason recorded in `tiers_skipped`:
`"no comparable live process available (Phase E requires live telemetry)"`.

**When implemented (Phase E):** compare the emitted agent configuration against a
reference deployment's performance metrics (conversion rate, escalation rate, stall
frequency) within a defined statistical confidence window.

---

## 3. Compensation Policy for Absent Tiers

Tiers 1 and 2 being absent does not block promotion but does impose compensation
obligations on the promoted bundle:

- The `manifest.json` records `tiers_skipped` with human-readable reasons.
- The operator should plan a probation window during which the bundle's live
  performance is monitored before expanding its scope.
- Additional manual gate approvals may be required during the probation window.

This policy is recorded in the manifest, not enforced in code (enforcement is an
operations configuration concern, not a commissioning concern).

---

## 4. ValidateActivityResult Schema

```python
@dataclass
class ValidateActivityResult:
    passed:        bool
    tiers_run:     list[str]         # ["tier0"] on clean pass; [] on Tier 0 failure
    tiers_skipped: dict[str, str]    # {"tier1": "<reason>", "tier2": "<reason>"}
    failures:      list[str]         # empty when passed; offending field paths when not
    report:        dict              # nested report keyed by tier name
```

The `report` dict structure:

```python
{
    "tier0": {
        "passed": True,
        "schema":            {"passed": True, "failures": []},
        "golden_comparison": {"passed": True, "failures": []},
        "vector_reproduction": {
            "passed": True,
            "rules_checked": 1,
            "failures": [],
        },
        "scenario_simulation": {
            "passed": True,
            "cards_checked": 5,
            "failures": [],
        },
    },
    "tier1": {"skipped": "no linked intake→outcome history ..."},
    "tier2": {"skipped": "no comparable live process ..."},
}
```

---

## 5. Promote Gate

`promote_activity` independently checks `validation.passed` before writing any
files. If `passed` is `False` it raises a non-retryable `ApplicationError`:

```
promote_activity: refusing to promote uncertified bundle
'<bundle_id>' — validation failures: [...]
```

This provides defence-in-depth: even if the workflow logic changes, an uncertified
bundle cannot reach disk via the promote activity.

---

## 6. Block Registration

```python
Block(
    name="commission_validate",
    consequence_class=ConsequenceClass.REVERSIBLE,
    idempotent=True,
    version="0.1.0",
)
```

REVERSIBLE because validation is read-only analysis with no external side effects.
`idempotent=True` because the activity is a pure function of its inputs.

---

## 7. Discipline Test Coverage

The `test_discipline_correction` integration test (Phase D gate clause 3) exercises
the full fault-detection path:

1. `inject_fault=True` → round-0 dissect emits `transition_state: reversible`.
2. `construct_activity` excludes `transition_state` from `by_tool` (only non-reversible
   tools appear).
3. `validate_activity` Tier 0 golden comparison fails: `"gates.by_tool missing
   'transition_state' (taxonomy says compensable/irreversible — golden requires
   approve-gated)"`.
4. Workflow raises `ApplicationError` — the round-0 bundle is never promoted.
5. Human reviewer calls `submit_correction`, dissect re-runs with `correction` applied.
6. Round-1 bundle has correct `transition_state: compensable` → `by_tool` includes
   `transition_state: "approve"` → Tier 0 passes → promote succeeds.

This path confirms that the validation ladder correctly catches the downstream effect
of a wrong consequence classification.
