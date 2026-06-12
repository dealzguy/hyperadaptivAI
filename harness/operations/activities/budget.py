"""check_budget — synchronous activity that enforces loop termination conditions.

This is a pure-logic activity: no DB, no inference, no I/O.
It is sync (not async) — defined with @activity.defn on a plain def, executed
in the thread-pool executor supplied to the Worker.

Consequence class: REVERSIBLE (read-only decision; no side effects).
Idempotent: True (deterministic from inputs; safe to retry).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@dataclass
class BudgetInput:
    tokens_used: int
    token_budget: int
    steps_completed: int
    max_steps: int
    recent_action_types: list
    stall_threshold: int


@dataclass
class BudgetResult:
    should_continue: bool
    reason: str
    should_escalate: bool


@activity.defn
def check_budget(inp: BudgetInput) -> BudgetResult:
    """Return whether the loop should continue, and why if not.

    Termination conditions (in priority order):
      1. Token budget exhausted → park, no escalation.
      2. Step budget exhausted → park, no escalation.
      3. Stall: last N consecutive action_types are all identical → park + escalate.
    """
    if inp.tokens_used >= inp.token_budget:
        logger.info(
            "check_budget: token budget exceeded (%d >= %d)",
            inp.tokens_used, inp.token_budget,
        )
        return BudgetResult(
            should_continue=False,
            reason="token budget exceeded",
            should_escalate=False,
        )

    if inp.steps_completed >= inp.max_steps:
        logger.info(
            "check_budget: max steps reached (%d >= %d)",
            inp.steps_completed, inp.max_steps,
        )
        return BudgetResult(
            should_continue=False,
            reason="max steps reached",
            should_escalate=False,
        )

    n = inp.stall_threshold
    if n > 0 and len(inp.recent_action_types) >= n:
        last_n = inp.recent_action_types[-n:]
        if len(set(last_n)) == 1:
            logger.info(
                "check_budget: stall detected — last %d actions all %r",
                n, last_n[0],
            )
            return BudgetResult(
                should_continue=False,
                reason="stall detected",
                should_escalate=True,
            )

    return BudgetResult(should_continue=True, reason="ok", should_escalate=False)


register(Block(
    name="check_budget",
    input_type="harness.operations.activities.budget.BudgetInput",
    output_type="harness.operations.activities.budget.BudgetResult",
    idempotent=True,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
