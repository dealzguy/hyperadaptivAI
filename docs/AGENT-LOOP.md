# Agent Loop — Implementation Reference

Phase C. Last updated: 2026-06-11.

---

## Overview

`AgentLoopWorkflow` is a durable Temporal workflow that drives an agent through a
SITUATE → DECIDE → ACT → RECORD cycle up to `max_steps` times. Every step that
touches inference, storage, or the clock does so through an activity — the workflow
body itself is purely deterministic.

Workflow ID convention: `agent-loop-{flow_id}-{entity_id}`

---

## Four-Step Cycle

### 1. SITUATE — `situate_activity`

**Input:** `SituateInput(agent_id, run_id, entity_id, step_number, idempotency_key)`

**What it does:**
- Reads the last 5 episodic records for `(agent_id, entity_key=entity_id)` via
  `PostgresMemoryProvider.read_episodic`.
- Reads the active directive for `agent_id` via `PostgresMemoryProvider.read_directive`.
- Builds a `context_dict` with keys: `entity_id`, `step`, `recent_history`, `directive`,
  `knowledge` (empty list — Phase D will populate via `query_knowledge`).

**Output:** `SituateResult(context_dict, tokens_used=0)` — pure read, no tokens consumed.

**Consequence class:** REVERSIBLE. Retry policy: 3 attempts, 2-minute timeout.

---

### 2. DECIDE — `decide_activity`

**Input:** `DecideInput(agent_id, run_id, step, model_id, context_dict, tool_allowlist,
budget_remaining, idempotency_key)`

**What it does (live mode):**
- Builds a system prompt listing `tool_allowlist` and a user prompt from `context_dict`.
- Calls `infer(InferInput(...))` → LiteLLM → Ollama (local only). `model_id` comes from
  `AgentLoopInput`, which is sourced from the config bundle — workflow code never names a
  model (invariant 2).
- Parses JSON response for keys: `action_type`, `action_payload`, `rationale`, `confidence`.
- Falls back gracefully on parse error (logs warning, uses first allowlist entry).

**STUB mode (`INFER_STUB=1`):** returns the first tool in `tool_allowlist` immediately
without a model call. Used for deterministic loop tests.

**Output:** `DecideResult(action_type, action_payload, rationale, tokens_used, confidence)`

**Consequence class:** REVERSIBLE (pure inference, no external side effects). Retry policy:
3 attempts, 5-minute timeout.

**How `model_id` flows:**
```
config/bundle-v0/agents/*.json  →  AgentLoopInput.model_id
    →  DecideInput.model_id
        →  InferInput.model_id
            →  litellm_provider.infer()  [_guard_model_id enforces ollama/ollama_chat prefix]
                →  LiteLLM
                    →  Ollama (localhost:11434)
```

Nothing above the `infer()` call names a model.

---

### 3. ACT — `act_activity`

**Input:** `ActInput(action_type, action_payload, entity_id, idempotency_key)`

**What it does:**
- Looks up `action_type` in the capability registry (`registry.get(action_type)`).
- If not found: returns `ActResult(error=...)` — soft error, never raises (P0-2 compliance).
  The workflow parks on `ActResult.error` rather than retrying forever.
- Injects cross-cutting fields the model should not supply:
  - `idempotency_key` → all verbs
  - `entity_id` → all verbs
  - `occurred_at` → `record_event` only (server-side UTC; model never fabricates timestamps — P1-2)
- Dispatches to the CRM verb directly (same activity context); wraps exceptions → soft error.

**Output:** `ActResult(outcome_payload, consequence_class, error)`

**Error containment (P0-2):** bounded `RetryPolicy(maximum_attempts=2)` at the call site;
`ActivityError` (retry exhaustion) is caught in the workflow and routes to `_record_park`.

**Consequence class:** REVERSIBLE (the routing shell; inner consequence class is the verb's).
Retry policy: 2 attempts, 2-minute timeout.

---

### 4. RECORD — `record_activity`

**Input:** `RecordInput(agent_id, run_id, step, action_type, action_payload, outcome_payload,
model_id, token_count, entity_key, idempotency_key)`

**What it does:**
- Writes one row to `agent_episodic` via `PostgresMemoryProvider.write_episodic`.
- ON CONFLICT(idempotency_key) DO NOTHING — idempotent, safe to replay.

**Output:** `RecordResult(id, created)`

**Consequence class:** REVERSIBLE. Retry policy: 5 attempts, 2-minute timeout.
The higher attempt count ensures the audit trail is written even under transient DB
pressure — "failure degrades into a visible queue, never silent loss."

---

## Budget and Stall Detection

After RECORD, `check_budget` (a sync activity running in the thread pool) evaluates:

| Condition | Reason returned | Workflow action |
|-----------|----------------|-----------------|
| `tokens_used >= token_budget` | `token_budget_exceeded` | Return `AgentLoopResult` |
| `steps_completed >= max_steps` | `step_budget_exceeded` | Return `AgentLoopResult` |
| Last N action types all identical (N = `stall_threshold`) | `stall_detected` | Return `AgentLoopResult` |
| None | — | Continue |

`BudgetInput` carries: `tokens_used`, `token_budget`, `steps_completed`, `max_steps`,
`recent_action_types` (sliding window of length `stall_threshold`), `stall_threshold`.

Default values (from `AgentLoopInput`): `max_steps=10`, `token_budget=4096`,
`stall_threshold=3`. Config bundle overrides these via the `AgentLoopInput` values loaded
from the flow definition.

---

## Signal Handlers

All signal handlers only flip boolean flags — no DB, no inference, no clocks.

| Signal | Effect |
|--------|--------|
| `pause_instance()` | Sets `_paused=True`. Workflow parks at `await workflow.wait_condition(lambda: not self._paused)` at the top of the next iteration (safe boundary). |
| `resume_instance()` | Sets `_paused=False`. The `wait_condition` clears and the loop continues. |
| `stop_instance()` | Sets `_stop=True`. Checked at the top of each iteration; triggers a clean `AgentLoopResult(stop_reason="stop_signal")`. |

---

## Query Handler

`get_state() -> dict` returns `{"paused": bool, "steps": int, "tokens": int}` synchronously
with no side effects.

---

## Park Semantics

Any terminal condition (budget, stall, act error, stop signal) results in returning an
`AgentLoopResult` with a descriptive `stop_reason` string (open set — not an enum).

Act errors also trigger `_record_park()`: a best-effort `record_activity` call writing an
episodic row with `action_type="park"` and `action_payload={"reason": ...}`. If this
write fails it is swallowed (audit loss is preferable to masking the original error).

`stop_reason` values defined at Phase C:
- `"completed"` — loop ran to natural end of `max_steps`
- `"stop_signal"` — `stop_instance` signal received
- `"parked_act_error"` — act raised ActivityError or returned soft error
- `"token_budget_exceeded"` / `"step_budget_exceeded"` / `"stall_detected"` — budget/stall

---

## Determinism Note

The workflow body (`run()`, signals, queries) contains zero side effects. All
nondeterminism lives in activities:

- Clocks: `occurred_at` injection in `act_activity`
- Inference: `decide_activity` (or stub if `INFER_STUB=1`)
- DB reads/writes: `situate_activity`, `record_activity`
- Config reads: would be `load_agent_definition` (Phase D full bundle loader)

This means Temporal can safely replay the workflow history on any worker restart or
task-queue drain without divergence.

---

## Knowledge Retrieval

The loop does NOT call `query_knowledge` in Phase C. The `context_dict["knowledge"]` field
is always an empty list. Roadmap note: Phase D will wire `query_knowledge` into the situate
step once the knowledge ingestion path has real content to retrieve.

---

## INFER_STUB=1 Mode

Set `INFER_STUB=1` in the environment to run the full loop deterministically without Ollama:

- `decide_activity` returns the first tool in `tool_allowlist` with `confidence=1.0`,
  `tokens_used=0`, and `rationale="stub"`.
- All other activities (situate, act, record, budget) run normally against the live DB.
- Exit gate tests use this mode with the time-skipping workflow environment.
