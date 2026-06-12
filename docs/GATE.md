# Gate Design — Human-Approval Gate (Phase E)

Phase E. Last updated: 2026-06-12.

---

## Purpose

[PROD] The gate enforces the agent spec's `gates` block between the DECIDE and ACT steps.
It ensures no irreversible or compensable action is taken without operator awareness and
approval, unless the agent's `autonomy_level` is configured to allow it. This is the
"human-on-the-loop" control surface: the agent always proposes; the gate determines whether
the operator must confirm before execution proceeds.

---

## Autonomy levels

[PROD] The `autonomy_level` field in the agent spec controls gate behaviour. Three levels:

| Level | Reversible (R) | Compensable (C) | Irreversible (I) |
|-------|---------------|-----------------|-----------------|
| `shadow` | record-only, no ACT | record-only, no ACT | record-only, no ACT |
| `gated` | auto | approve | approve |
| `autonomous` | auto | auto | approve |

[PROD] `shadow` mode: the agent proposes actions and all outcomes are recorded, but no CRM
verb is ever executed. Used for probation / new-agent trials.

[PROD] `gated` mode: reversible actions execute automatically; compensable and irreversible
actions require operator approval via the gate queue before execution.

[PROD] `autonomous` mode default: reversible=auto, compensable=auto, irreversible=approve.
Config takes precedence: `by_consequence_class` and `by_tool` in the agent spec can override
any default. The operator controls the gate matrix through config (e.g. setting
`{"irreversible": "auto"}` in `by_consequence_class` overrides the built-in default).

[PROD] `autonomy_level` is operator-configurable via the agent spec JSON — it is data, not
code. Changing it requires a commissioning re-run and config-bundle promote (one human click).

---

## The `by_tool` override

[PROD] The `gates.by_tool` map in the agent spec takes highest precedence over consequence
class. If `transition_state` is listed under `by_tool: { "transition_state": "approve" }`,
that tool always requires approval regardless of its consequence class or autonomy level.

Precedence order (highest to lowest):
1. `gates.by_tool[tool_name]`
2. `gates.by_consequence_class[consequence_class]` filtered through `autonomy_level`
3. Default: `"approve"` (fail-safe)

[PROD] Fail-safe: an unknown or missing consequence class resolves to `"approve"` — the
safest default. Unknown tools not listed in `by_tool` fall through to consequence class.

---

## The gate molecule

[PROD] `gate_decision(consequence_class, gates_config, autonomy_level, tool_name) -> "auto" | "approve"`

Location: `harness/operations/molecules/gate.py`

[PROD] This function is pure and deterministic — no I/O, no randomness, no clocks. It is
safe to call inside workflow code (it never violates the determinism boundary). It encodes
the precedence table above into a single testable unit.

Inputs:
- `consequence_class`: `"reversible"` | `"compensable"` | `"irreversible"` (open set for
  future classes — unknown values resolve to `"approve"`)
- `gates_config`: the `gates` dict from the agent spec
- `autonomy_level`: `"shadow"` | `"gated"` | `"autonomous"`
- `tool_name`: the action type being evaluated

Output: `"auto"` (proceed without approval) or `"approve"` (halt and queue for operator).

---

## Workflow enforcement

[PROD] Gate logic in `AgentLoopWorkflow` ships via `workflow.patched("consequence-gate-v1")`.
See `docs/VERSIONING.md` for the patched/deprecate/remove lifecycle.

**Signal-based resumption:**

[PROD] When the gate returns `"approve"`, the workflow creates a gate-approval task (see
Persistence below) and awaits the `resolve_gate` signal:

```
workflow.wait_condition(lambda: self._gate_resolved)
```

[PROD] The signal `resolve_gate` carries a `GateVerdict` payload:

```python
{
    "decision_id": str,   # matches the task row id
    "verdict": "approve" | "reject" | "edit",
    "edited_action": dict | None   # populated only for "edit" verdict
}
```

Three verdicts:
- **approve** — workflow executes the action as proposed.
- **reject** — workflow skips the ACT step; records a "gate_rejected" episodic event and
  continues the loop.
- **edit** — operator supplies a modified `action_payload`; workflow executes the edited
  action. The edited payload is logged in the episodic record for auditability.

[PROD] The signal handler only sets flags and stores data — no DB, no inference, no clocks
(determinism boundary).

---

## Persistence

[PROD] **Approval queue:** When a gate fires, the workflow (via an activity) writes a `task`
row with `type="agent_gate_approval"` to the business Postgres. Fields include:
- `entity_id`: the lead being acted upon
- `payload`: `{decision_id, agent_id, tool_name, proposed_payload, consequence_class}`
- `status`: `"open"` → `"approved"` or `"rejected"` on signal receipt

[PROD] **Probation ledger:** In `shadow` mode, each suppressed action is logged as an `event`
row (`type="gate_suppressed"`) against the lead entity, and a `state` row records the
probation period. This creates a complete audit trail for graduated-autonomy decisions.

[PROD] All persistence is idempotent: task creation uses an idempotency key derived from
`(run_id, step, tool_name)`; duplicate signals are no-ops.

---

## Operator workflow (CLI)

The operator interacts with pending gates through the operator CLI:

```bash
# List all open gate approvals
python -m harness.operations.operator_cli list-gates

# Show full detail of a single pending gate
python -m harness.operations.operator_cli show-gate <decision_id>

# Approve a pending gate
python -m harness.operations.operator_cli approve <decision_id>

# Reject a pending gate
python -m harness.operations.operator_cli reject <decision_id>

# Edit and approve (supply modified action type and JSON payload)
python -m harness.operations.operator_cli edit <decision_id> --action-type <type> --action-payload '{"key": "value"}'

# Pause / resume a single workflow instance
python -m harness.operations.operator_cli pause <workflow_id>
python -m harness.operations.operator_cli resume <workflow_id>

# Pause / resume all instances of a flow class
python -m harness.operations.operator_cli pause-flow <flow_id>
python -m harness.operations.operator_cli resume-flow <flow_id>

# Daily operational digest
python -m harness.operations.operator_cli digest
```

Each command sends the `resolve_gate` signal to the relevant Temporal workflow instance by
workflow ID (`agent-loop-{flow_id}-{entity_id}`).

---

## Example: lead-qualifier agent in gated mode

1. Operator has configured `lead-qualifier-v0.json` with `autonomy_level: "gated"` and
   `gates.by_tool: { "transition_state": "approve" }`.
2. Agent runs SITUATE → DECIDE → selects `transition_state` (compensable) with
   `payload: {"stage_id": "qualifying"}`.
3. `gate_decision("compensable", gates_config, "gated", "transition_state")` returns
   `"approve"` (both `by_tool` and consequence class require it).
4. Workflow writes a `task` row and pauses at `wait_condition`.
5. Operator runs `list-gates`, sees the pending decision, reviews the proposed transition.
6. Operator runs `approve <decision_id>`.
7. Temporal delivers the `resolve_gate` signal; workflow resumes; `act_activity` runs
   `transition_state`; RECORD step writes the episodic entry.

---

## Non-goals

[PROD] The gate is not a rules engine — `gate_decision` encodes one decision table. Complex
approval workflows (multi-approver, timed escalation) are future config on the task primitive,
not changes to gate.py.

[PROD] The gate does not validate business correctness of the proposed action — only whether
it requires approval. Business validation lives inside the CRM verbs.
