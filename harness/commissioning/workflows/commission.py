"""CommissioningWorkflow — Phase D durable commissioning pipeline.

Stages: interview → dissect (with correction loop) → construct → validate
        → await_promote → promote → promoted

Sandbox safety (matches agent_loop.py pattern):
  All imports of activity modules MUST appear inside
  workflow.unsafe.imports_passed_through() blocks.  Workflow code (run(),
  signals, queries) must contain ZERO side effects — no file I/O, no DB,
  no inference, no clocks, no env reads.

Signal handlers:
  submit_correction(correction: dict) — inject a correction into the active
      dissect round and unblock the review gate.
  advance_stage()                     — accept the current dissect round
      without a correction and unblock the review gate.
  approve_promote()                   — one human click; triggers Stage 4.

Queries:
  get_stage() → str         — current stage string (sync, no side effects)
  get_artifacts() → dict    — stage → asdict snapshot (sync, no side effects)

Workflow ID convention: "commission-{operator_id}"

Determinism invariants:
  - Signal handlers ONLY set boolean flags or dict/None values — no activity
    calls, no I/O, no clocks.
  - self._dissect_reviewed is reset BEFORE each dissect round's activity call
    (fixes the signal-race identified in the review findings — a signal
    arriving during the activity is not clobbered).
  - All artifact snapshots stored as plain dicts via dataclasses.asdict()
    so get_artifacts() query payloads are serializable.
"""
from __future__ import annotations

import dataclasses
import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from harness.shared.contracts.commission import (
        CommissioningInput,
        CommissioningResult,
    )
    from harness.commissioning.activities.interview import (
        InterviewActivityInput,
        interview_activity,
    )
    from harness.commissioning.activities.dissect import (
        DissectActivityInput,
        dissect_activity,
    )
    from harness.commissioning.activities.construct import (
        ConstructActivityInput,
        construct_activity,
    )
    from harness.commissioning.activities.validate import (
        ValidateActivityInput,
        validate_activity,
    )
    from harness.commissioning.activities.promote import (
        PromoteActivityInput,
        promote_activity,
    )

logger = logging.getLogger(__name__)


@workflow.defn
class CommissioningWorkflow:
    """Durable commissioning pipeline: interview → dissect → construct → validate → promote.

    DETERMINISM NOTE: All nondeterminism lives in activities.
    Signal handlers only flip boolean flags or record dict values — no I/O,
    no inference, no clocks.  Artifact snapshots are stored as plain dicts.
    """

    def __init__(self) -> None:
        self._stage: str = "init"
        self._artifacts: dict = {}            # stage-key -> asdict snapshot
        self._correction: dict | None = None
        self._dissect_reviewed: bool = False
        self._promote_approved: bool = False
        self._corrections_applied: list[dict] = []

    # ── Signals ───────────────────────────────────────────────────────────────

    @workflow.signal
    async def submit_correction(self, correction: dict) -> None:
        """Inject a correction for the current dissect round.

        Sets the pending correction value and unblocks the dissect_review gate.
        The workflow loop will apply this correction in the next dissect round.
        """
        self._correction = correction
        self._dissect_reviewed = True

    @workflow.signal
    async def advance_stage(self) -> None:
        """Accept the current dissect round without issuing a correction.

        Unblocks the dissect_review gate; _correction remains None so the
        loop breaks without re-running dissect.
        """
        self._dissect_reviewed = True

    @workflow.signal
    async def approve_promote(self) -> None:
        """One human click — triggers Stage 4 promote.

        Per CLAUDE.md: promote waits for one human click absent explicit
        written policy.  auto_promote=True in CommissioningInput represents
        that explicit written policy (used only in the end-to-end fixture test).
        """
        self._promote_approved = True

    # ── Queries ───────────────────────────────────────────────────────────────

    @workflow.query
    def get_stage(self) -> str:
        """Return the current stage string (sync, no side effects)."""
        return self._stage

    @workflow.query
    def get_artifacts(self) -> dict:
        """Return all stage artifact snapshots as plain dicts (sync, no side effects).

        Values are stored as dataclasses.asdict() outputs at stage completion,
        so this is serializable without further processing.
        """
        return self._artifacts

    # ── Run ───────────────────────────────────────────────────────────────────

    @workflow.run
    async def run(self, inp: CommissioningInput) -> CommissioningResult:
        """Execute the commissioning pipeline.

        Stage machine (open set of stage strings, no Python enum):
          interview → dissect (loop) → [dissect_review] → construct →
          validate → [await_promote] → promote → promoted
        """
        from temporalio.exceptions import ApplicationError

        # ── Stage 0: Interview ────────────────────────────────────────────────
        self._stage = "interview"
        interview = await workflow.execute_activity(
            interview_activity,
            InterviewActivityInput(
                operator_id=inp.operator_id,
                fixture_path=inp.fixture_path,
                idempotency_key=f"{inp.idempotency_key}:interview",
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._artifacts["interview"] = dataclasses.asdict(interview)

        # ── Stage 1: Dissect with human-review correction loop ────────────────
        # Signal race fix: self._dissect_reviewed is reset BEFORE each round's
        # activity call, not after, so a signal arriving during the activity is
        # recorded properly rather than clobbered by the reset.
        round_num = 0
        correction: dict | None = None
        last_dissection = None

        while True:
            self._stage = "dissect"
            # Reset the gate flag BEFORE the activity so any signal that fires
            # during the activity is not lost (it will set the flag to True
            # before we check it in wait_condition below).
            self._dissect_reviewed = False

            dissection = await workflow.execute_activity(
                dissect_activity,
                DissectActivityInput(
                    interview=interview,
                    round=round_num,
                    inject_fault=inp.inject_fault,
                    correction=correction,
                    idempotency_key=f"{inp.idempotency_key}:dissect:{round_num}",
                ),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            self._artifacts[f"dissect:{round_num}"] = dataclasses.asdict(dissection)
            last_dissection = dissection
            correction = None   # consumed — clear for next round

            if inp.auto_advance_dissect:
                break   # no review gate in auto mode

            # Wait for human review signal (advance_stage or submit_correction).
            self._stage = "dissect_review"
            await workflow.wait_condition(lambda: self._dissect_reviewed)

            if self._correction is None:
                # advance_stage received — accept current round, exit loop.
                break

            # submit_correction received — apply in next round.
            correction = self._correction
            self._correction = None
            self._corrections_applied.append({
                "stage": "dissect",
                "correction": correction,
                "round": round_num + 1,   # the round that will apply this correction
            })
            round_num += 1
            # Loop back: reset _dissect_reviewed BEFORE executing the activity
            # again (done at the top of the while loop).

        # ── Stage 2: Construct ────────────────────────────────────────────────
        self._stage = "construct"
        bundle = await workflow.execute_activity(
            construct_activity,
            ConstructActivityInput(
                operator_id=inp.operator_id,
                dissection=last_dissection,
                idempotency_key=f"{inp.idempotency_key}:construct",
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._artifacts["construct"] = dataclasses.asdict(bundle)

        # ── Stage 3: Validate ─────────────────────────────────────────────────
        self._stage = "validate"
        vresult = await workflow.execute_activity(
            validate_activity,
            ValidateActivityInput(
                bundle=bundle,
                interview=interview,
                dissection=last_dissection,
                golden_bundle_path=inp.golden_bundle_path,
                idempotency_key=f"{inp.idempotency_key}:validate",
            ),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._artifacts["validate"] = dataclasses.asdict(vresult)

        if not vresult.passed:
            raise ApplicationError(
                f"commissioning_validate: tier0 certification failed for "
                f"operator '{inp.operator_id}': {vresult.failures}",
                non_retryable=True,
            )

        # Patch tiers_run into the bundle for promote.
        # Dataclasses arrive as values from the activity; rebuild with updated field.
        import dataclasses as _dc
        bundle_with_tiers = _dc.replace(bundle, tiers_run=vresult.tiers_run)

        # ── Stage 4: Await promote (one human click) ──────────────────────────
        if not inp.auto_promote:
            self._stage = "await_promote"
            await workflow.wait_condition(lambda: self._promote_approved)

        # ── Stage 4: Promote ──────────────────────────────────────────────────
        self._stage = "promote"
        presult = await workflow.execute_activity(
            promote_activity,
            PromoteActivityInput(
                bundle=bundle_with_tiers,
                validation=vresult,
                output_root=inp.output_root,
                operator_id=inp.operator_id,
                idempotency_key=f"{inp.idempotency_key}:promote",
            ),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._artifacts["promote"] = dataclasses.asdict(presult)

        self._stage = "promoted"

        return CommissioningResult(
            operator_id=inp.operator_id,
            final_stage="promoted",
            bundle_path=presult.bundle_path,
            dissect_rounds=round_num + 1,
            corrections_applied=self._corrections_applied,
            tiers_run=vresult.tiers_run,
            validation_report=vresult.report,
        )
