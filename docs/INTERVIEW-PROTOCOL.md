# INTERVIEW-PROTOCOL.md — Stage 0: Operator Interview

**Status:** Normative for Stage 0 of the commissioning pipeline. Implemented in
`harness/commissioning/activities/interview.py`. Live-inference mode is deferred
to Phase E; stub mode is the current implementation.

---

## 1. Purpose

[PROD] Stage 0 reads a structured fixture representing an operator's business context and
extracts three artefacts:

1. **ContextFrame** — the operator's business identity and lifecycle vocabulary.
2. **ConsequenceTaxonomy** — per-tool consequence classes (`reversible`,
   `compensable`, `irreversible`).
3. **ScenarioCards** — 5–10 deal-shape scenarios walked from real cases.

[PROD] The output `InterviewResult` feeds directly into Stage 1 (dissect). [PROD] All fields
carry provenance records that trace each value to its fixture source path.

---

## 2. Traversal Order

The interview traverses the fixture in this fixed order. In live-inference mode this
would become a guided dialogue. In stub mode it is a direct field-lift.

1. `what_is_sold` — what the operator sells.
2. `sold_to_whom` — the target customer segment.
3. `lifecycle` — the ordered set of lifecycle state names.
4. `revenue_concentration` — revenue distribution note.
5. `exceptions` — edge cases that override the standard flow.
6. `consequence taxonomy` — for each tool in `$.tools`, record its `consequence_class`.
7. `scenario walking` — for each entry in `$.scenarios`, lift the deal-shape narrative
   and expected stage path.
8. `frame_readback` — synthesise a plain-language summary in operator vocabulary,
   confirming field extraction (used to detect hallucination in live mode).

---

## 3. Fixture Format

The interview reads a JSON fixture file. Path is passed as `fixture_path` in
`InterviewActivityInput`. The fixture file must be a valid JSON object with the
following top-level keys.

### 3.1 Required Keys

```json
{
  "operator_id": "meridian-realty-v0",
  "business": {
    "name": "Meridian Realty Partners",
    "what_is_sold": "residential property representation",
    "sold_to_whom": "home buyers and sellers in the Meridian metro",
    "revenue_concentration": "...",
    "exceptions": ["...", "..."]
  },
  "lifecycle": {
    "stages": ["new", "qualifying", "qualified", "disqualified", "first_follow_up_done"]
  },
  "channels": ["web_form"],
  "task_types": ["first_follow_up", "agent_gate_approval", "agent_escalation"],
  "tools": [
    { "name": "record_event",    "consequence_class": "reversible"  },
    { "name": "transition_state","consequence_class": "compensable" },
    { "name": "assign_task",     "consequence_class": "compensable" }
  ],
  "calculations": [
    {
      "rule_id": "lead-score-v0",
      "description": "...",
      "expression": "score = 2*budget_match + 1*timeline_match",
      "test_vectors": [
        { "inputs": { "budget_match": 1, "timeline_match": 1 }, "expected": 3 },
        ...
      ]
    }
  ],
  "scenarios": [
    {
      "card_id": "card-01",
      "title": "Clean qualify — buyer with pre-approval",
      "narrative": "...",
      "expected_stages": ["new", "qualifying", "qualified", "first_follow_up_done"],
      "expected_outcome": "first_follow_up_done"
    },
    ...
  ]
}
```

### 3.2 Scenario Card Constraints

- [PROD] Minimum 5, maximum 10 scenario cards per fixture.
- [PROD] `expected_outcome` must be a value present in `lifecycle.stages`. The validate
  Tier 0 scenario simulation check (`expected_outcome ∈ vocab.stages`) will fail
  otherwise.
- [PROD] `expected_stages` may contain repeated values (e.g. a lead cycling through
  `"qualifying"` twice). All values must be present in `lifecycle.stages`.
- [PROD] The interview activity enforces the 5–10 card count with a non-retryable
  `ApplicationError` — a fixture with fewer than 5 or more than 10 cards is a
  fixture defect, not a transient.

### 3.3 Tool List

[PROD] The `$.tools` array is the authoritative source for consequence taxonomy. Each entry:

| Field | Type | Required |
|---|---|---|
| `name` | `str` | Yes — must be a valid tool name in `tool_allowlist` |
| `consequence_class` | `str` | Yes — open string: `"reversible"`, `"compensable"`, or `"irreversible"` |
| `rationale` | `str` | No — human justification; ignored by code |

---

## 4. Output Schema

### 4.1 ContextFrame

| Field | Source JSON path | Notes |
|---|---|---|
| `operator_id` | `InterviewActivityInput.operator_id` | Passed from workflow input |
| `business_name` | `$.business.name` | |
| `what_is_sold` | `$.business.what_is_sold` | |
| `sold_to_whom` | `$.business.sold_to_whom` | |
| `lifecycle_stages` | `$.lifecycle.stages` | [PROD] Open set — order is significant (state machine ordering) |
| `revenue_concentration` | `$.business.revenue_concentration` | |
| `exceptions_that_matter` | `$.business.exceptions` | |
| `version` | `0` | Bumped on correction |
| `provenance` | `{"source": "fixture:<path>", "path": "$.business"}` | |

### 4.2 ConsequenceTaxonomy

```python
by_tool: {
    "record_event":    "reversible",
    "transition_state": "compensable",
    "assign_task":      "compensable",
}
provenance: {
    "source": "fixture:<path>",
    "path": "$.tools[*].{name,consequence_class}",
}
```

[PROD] `by_tool` is a plain dict with open-set string values. It is not a Python enum
(Invariant 3 — [PROD]). New consequence classes may be added by appending to the taxonomy;
no code changes are required.

### 4.3 ScenarioCard

| Field | Source JSON path |
|---|---|
| `card_id` | `$.scenarios[i].card_id` |
| `title` | `$.scenarios[i].title` |
| `narrative` | `$.scenarios[i].narrative` |
| `expected_stages` | `$.scenarios[i].expected_stages` |
| `expected_outcome` | `$.scenarios[i].expected_outcome` |
| `provenance` | `{"source": "fixture:<path>", "path": "$.scenarios[?(@.card_id=='<id>')]"}` |

### 4.4 InterviewResult

```python
@dataclass
class InterviewResult:
    context_frame: ContextFrame
    consequence_taxonomy: ConsequenceTaxonomy
    scenario_cards: list[ScenarioCard]   # 5–10 cards
    frame_readback: str
```

The `frame_readback` in stub mode is synthesised deterministically as:

```
{business_name} sells {what_is_sold} to {sold_to_whom}.
Lead lifecycle: {stage1} → {stage2} → ...
Revenue note: {revenue_concentration}.
```

---

## 5. Stub Mode vs Live Mode

### Stub Mode (INFER_STUB=1)

The activity reads the fixture file directly and maps fields to the output
dataclasses. All provenance records reference `"source": "fixture:<fixture_path>"`
and the JSON path within the fixture. [PROD] Stub mode is deterministic: same fixture
always produces the same `InterviewResult`.

[DEV] Stub mode is used in all Phase D tests and CI runs.

### Live Mode

Raises `NotImplementedError` with a pointer to Phase E. The live implementation
should:

1. Load the fixture as a structured brief.
2. [PROD] Call `infer()` per the Stage 0 prompt templates (to be defined in Phase E) with
   the fixture as context.
3. [PROD] Validate the model response against the output schema.
4. [PROD] Re-issue targeted follow-up calls for any field that fails schema validation
   (up to a configurable retry budget before raising `ApplicationError`).

[PROD] Live mode output must produce the same `InterviewResult` schema — the downstream
dissect/construct/validate stages are unaware of whether the interview ran in stub
or live mode.

---

## 6. Block Registration

```python
Block(
    name="commission_interview",
    consequence_class=ConsequenceClass.REVERSIBLE,
    idempotent=False,
    version="0.1.0",
)
```

[PROD] `idempotent=False` because live-inference calls are nondeterministic. [PROD] The
`idempotency_key` field on `InterviewActivityInput` is accepted for audit tracing
only, not for deduplication. [PROD] Temporal's retry policy (maximum_attempts=3,
start_to_close_timeout=10 min) governs transient failures.

---

## 7. Reference Fixture

Canonical example fixture: `fixtures/commission_fixture_01.json`

Operator: Meridian Realty Partners (`meridian-realty-v0`). Lifecycle stages are
identical to `config/bundle-v0/` vocab so the golden comparison in validate Tier 0
passes exactly. [DEV] This fixture is the authoritative input for all Phase D integration
tests.
