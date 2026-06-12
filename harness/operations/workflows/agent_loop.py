"""AgentLoopWorkflow — durable agentic loop (Phase C).

Four-step cycle per iteration: SITUATE → DECIDE → ACT → RECORD.
Terminates on: loop completion, token/step budget, stall, stop signal, or error.

Sandbox safety:
  All imports of asyncpg, litellm, or any I/O library MUST appear inside
  workflow.unsafe.imports_passed_through() blocks. Workflow code (run(), signals,
  queries) must contain ZERO side effects — no DB, no inference, no clocks.
  Only Temporal activity calls cross the determinism boundary.

Signal handlers:
  pause_instance() / resume_instance() — park at top of next iteration.
  stop_instance()                      — clean exit after current iteration.

Query:
  get_state() → dict  (sync, no side effects)

Workflow ID convention: "agent-loop-{flow_id}-{entity_id}"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from harness.operations.activities.situate import SituateInput, situate_activity
    from harness.operations.activities.decide import DecideInput, decide_activity
    from harness.operations.activities.act import ActInput, act_activity
    from harness.operations.activities.record import RecordInput, record_activity
    from harness.operations.activities.budget import BudgetInput, check_budget

logger = logging.getLogger(__name__)


# ── I/O dataclasses ───────────────────────────────────────────────────────────

@dataclass
class AgentLoopInput:
    agent_id: str
    entity_id: str
    flow_id: str
    model_id: str
    max_steps: int = 10
    token_budget: int = 4096
    stall_threshold: int = 3
    tool_allowlist: list = field(default_factory=lambda: ["record_event"])
    idempotency_key: str = ""


@dataclass
class AgentLoopResult:
    steps_completed: int
    total_tokens: int
    stop_reason: str


# ── Workflow ──────────────────────────────────────────────────────────────────

@workflow.defn
class AgentLoopWorkflow:
    """Durable agentic loop: situate → decide → act → record × N.

    DETERMINISM NOTE: All nondeterminism lives in activities.
    Signal handlers only flip boolean flags — no DB, no inference, no clocks.
    """

    def __init__(self) -> None:
        self._paused: bool = False
        self._stop: bool = False
        self._steps_completed: int = 0
        self._total_tokens: int = 0

    # ── Signals ───────────────────────────────────────────────────────────────

    @workflow.signal
    async def pause_instance(self) -> None:
        """Park this instance at the top of its next iteration."""
        self._paused = True

    @workflow.signal
    async def resume_instance(self) -> None:
        """Resume a paused instance."""
        self._paused = False

    @workflow.signal
    async def stop_instance(self) -> None:
        """Request a clean exit after the current iteration completes."""
        self._stop = True

    # ── Query ─────────────────────────────────────────────────────────────────

    @workflow.query
    def get_state(self) -> dict:
        """Return current loop state (sync — no side effects)."""
        return {
            "paused": self._paused,
            "steps": self._steps_completed,
            "tokens": self._total_tokens,
        }

    # ── Run ───────────────────────────────────────────────────────────────────

    @workflow.run
    async def run(self, inp: AgentLoopInput) -> AgentLoopResult:
        wf_id = workflow.info().run_id   # stable within an execution; used as run_id in episodic
        recent_types: list[str] = []

        for step in range(inp.max_steps):
            # ── Stop signal check ─────────────────────────────────────────
            if self._stop:
                return AgentLoopResult(
                    steps_completed=self._steps_completed,
                    total_tokens=self._total_tokens,
                    stop_reason="stop_signal",
                )

            # ── Instance-level pause (safe boundary) ──────────────────────
            if self._paused:
                await workflow.wait_condition(lambda: not self._paused)

            # ── SITUATE ───────────────────────────────────────────────────
            ctx = await workflow.execute_activity(
                situate_activity,
                SituateInput(
                    agent_id=inp.agent_id,
                    run_id=wf_id,
                    entity_id=inp.entity_id,
                    step_number=step,
                    idempotency_key=f"{inp.idempotency_key}:s:{step}",
                ),
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            # ── DECIDE ────────────────────────────────────────────────────
            decision = await workflow.execute_activity(
                decide_activity,
                DecideInput(
                    agent_id=inp.agent_id,
                    run_id=wf_id,
                    step=step,
                    model_id=inp.model_id,
                    context_dict=ctx.context_dict,
                    tool_allowlist=inp.tool_allowlist,
                    budget_remaining=inp.token_budget - self._total_tokens,
                    idempotency_key=f"{inp.idempotency_key}:d:{step}",
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            # ── ACT ───────────────────────────────────────────────────────
            # Bounded retry + error containment (P0-2): ActivityError is caught;
            # act_activity itself returns ActResult.error for unknown-tool cases
            # without raising, so that path is handled in the ActResult check below.
            try:
                outcome = await workflow.execute_activity(
                    act_activity,
                    ActInput(
                        action_type=decision.action_type,
                        action_payload=decision.action_payload,
                        entity_id=inp.entity_id,
                        idempotency_key=f"{inp.idempotency_key}:a:{step}",
                    ),
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
            except ActivityError as exc:
                # Activity exhausted retries or raised non-retryable — park.
                # Write a minimal episodic row so the run is auditable.
                await _record_park(
                    wf_id=wf_id,
                    inp=inp,
                    step=step,
                    reason=f"act_error:{exc}",
                    idempotency_key=f"{inp.idempotency_key}:r:{step}:park",
                )
                return AgentLoopResult(
                    steps_completed=self._steps_completed,
                    total_tokens=self._total_tokens,
                    stop_reason="parked_act_error",
                )

            # If act_activity returned a soft error (unknown tool), park.
            if outcome.error:
                await _record_park(
                    wf_id=wf_id,
                    inp=inp,
                    step=step,
                    reason=f"act_soft_error:{outcome.error}",
                    idempotency_key=f"{inp.idempotency_key}:r:{step}:park",
                )
                return AgentLoopResult(
                    steps_completed=self._steps_completed,
                    total_tokens=self._total_tokens,
                    stop_reason="parked_act_error",
                )

            # ── RECORD ────────────────────────────────────────────────────
            await workflow.execute_activity(
                record_activity,
                RecordInput(
                    agent_id=inp.agent_id,
                    run_id=wf_id,
                    step=step,
                    action_type=decision.action_type,
                    action_payload=decision.action_payload,
                    outcome_payload=outcome.outcome_payload,
                    model_id=inp.model_id,
                    token_count=decision.tokens_used,
                    entity_key=inp.entity_id,
                    idempotency_key=f"{inp.idempotency_key}:r:{step}",
                ),
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )

            self._steps_completed = step + 1
            self._total_tokens += decision.tokens_used
            recent_types.append(decision.action_type)

            # ── BUDGET CHECK ──────────────────────────────────────────────
            budget_ok = await workflow.execute_activity(
                check_budget,
                BudgetInput(
                    tokens_used=self._total_tokens,
                    token_budget=inp.token_budget,
                    steps_completed=self._steps_completed,
                    max_steps=inp.max_steps,
                    recent_action_types=recent_types[-inp.stall_threshold:],
                    stall_threshold=inp.stall_threshold,
                ),
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            if not budget_ok.should_continue:
                return AgentLoopResult(
                    steps_completed=self._steps_completed,
                    total_tokens=self._total_tokens,
                    stop_reason=budget_ok.reason,
                )

        # Loop exhausted without early termination.
        return AgentLoopResult(
            steps_completed=self._steps_completed,
            total_tokens=self._total_tokens,
            stop_reason="completed",
        )


# ── Park helper ───────────────────────────────────────────────────────────────

async def _record_park(
    wf_id: str,
    inp: AgentLoopInput,
    step: int,
    reason: str,
    idempotency_key: str,
) -> None:
    """Write an episodic row marking a park event (audit trail, never silent loss)."""
    try:
        await workflow.execute_activity(
            record_activity,
            RecordInput(
                agent_id=inp.agent_id,
                run_id=wf_id,
                step=step,
                action_type="park",
                action_payload={"reason": reason},
                outcome_payload={},
                model_id=inp.model_id,
                token_count=0,
                entity_key=inp.entity_id,
                idempotency_key=idempotency_key,
            ),
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
    except ActivityError:
        # Best-effort audit; do not mask the park by raising here.
        pass
