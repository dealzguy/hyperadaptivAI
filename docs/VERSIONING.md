# Workflow Versioning Discipline

Phase E. Last updated: 2026-06-12.

---

## Why we version

[PROD] The Temporal event history is immutable. Once a workflow instance starts, its recorded
decisions are replayed on every worker restart, task-queue drain, or mid-flight deployment.
If workflow code changes break the replay path, Temporal raises a non-determinism error and
the workflow becomes stuck.

[PROD] The only safe way to change `AgentLoopWorkflow` (or any workflow) logic is through
`workflow.patched()` — the Temporal versioning API. This lets old in-flight instances replay
on the pre-patch path while new instances take the post-patch path, on the same worker binary.

[DEV] Never edit running workflow logic directly. Always ship changes through the three-stage
lifecycle below.

---

## Three-stage lifecycle

### Stage 1 — `patched("name")`

[PROD] Introduce the guard and branch both paths:

```python
use_gate = workflow.patched("consequence-gate-v1")
if use_gate:
    # new path
    ...
else:
    # old path (pre-patch replay)
    ...
```

[PROD] All in-flight workflows that predate the patch replay the `else` branch. New workflows
evaluate `True` and take the `if` branch. The two paths can coexist indefinitely.

### Stage 2 — `deprecate_patch("name")`

[PROD] Once all pre-patch workflow instances have completed (confirmed via Temporal UI — no
open histories predate the patch), call `workflow.deprecate_patch("name")`. This tells
Temporal that the old path is unreachable; the `else` branch can be left in or removed.

[DEV] Confirm in the Temporal UI (or via `tctl`/CLI) that no open instances carry a history
older than the patch before advancing to Stage 2.

### Stage 3 — remove the block

[PROD] After `deprecate_patch` is confirmed stable across a full deploy cycle, the dead branch
and the `patched()` call may be removed in the next scheduled cleanup PR.

---

## The loop-memoization gotcha

[PROD] **Call `patched()` exactly once, before the loop. Store the result as a bool. Use the
bool inside the loop. Never call `patched()` inside a loop.**

Temporal memoizes the return value of `patched()` on replay: the first call determines the
branch for the entire replay. If `patched()` is called inside a loop, it is invoked multiple
times per replay and will return `True` for a call that originally returned `False` (or vice
versa), producing non-determinism and a stuck workflow.

> **Clarification (Python SDK):** In the Python SDK, `patched()` inside a loop consistently
> returns the same memoized value — the issue is it returns the *first call's* result for all
> subsequent calls in the same iteration context, which causes unexpected behavior when the
> loop runs on a mix of old and new replays (i.e. some iterations were recorded before the
> patch, some after). The safe practice: call `patched()` once before the loop, store the
> result as a bool, and use the bool inside the loop.

Correct pattern:

```python
use_gate = workflow.patched("consequence-gate-v1")  # ONCE, before the loop

for step in range(inp.max_steps):
    ...
    if use_gate:
        # new path: gate enforcement
        gate_verdict = await workflow.execute_activity(
            enforce_gate_activity, ...,
        )
        if gate_verdict == "approve":
            await workflow.execute_activity(act_activity, ...)
    else:
        # old path: direct act (pre-patch replay)
        await workflow.execute_activity(act_activity, ...)
```

Wrong pattern (do not do this):

```python
for step in range(inp.max_steps):
    ...
    if workflow.patched("consequence-gate-v1"):  # WRONG — inside the loop
        ...
```

---

## Current patches

### `consequence-gate-v1` — active

**Phase:** E  
**Status:** Active (Stage 1 — `patched()` guard in place; pre-patch instances still possible)

**What changed:**

| | Pre-patch | Post-patch |
|---|---|---|
| Path | DECIDE → ACT | DECIDE → gate decision → (optional approval wait) → ACT |
| Trigger | Always direct | Gate fires for compensable and irreversible actions (configurable) |
| Signal | — | `resolve_gate({decision_id, verdict, edited_action?})` resumes workflow |

**Guard location:** `harness/operations/workflows/agent_loop.py` — evaluated once before the
step loop.

**Advance to Stage 2 when:** all pre-Phase-E workflow instances in the Temporal namespace have
completed. Check via `temporal workflow list --status Running` — confirm zero instances
predate the Phase E deploy date (2026-06-12).

---

## Adding a new patch

[DEV] Follow this checklist when shipping a new workflow logic change:

1. Add a new entry in this file under "Current patches" with status "Active (Stage 1)".
2. Call `workflow.patched("your-patch-name")` once, before the affected loop or branch.
3. Implement both the new path and the old path (replay guard).
4. Record the patch in `docs/LIQUID-RESOLUTIONS.md` if it resolves a liquid.
5. [DEV] Write a replay-determinism test that exercises both branches.
6. Advance to Stage 2 only after founder confirmation that no pre-patch instances are open.
