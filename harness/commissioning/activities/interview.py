"""interview_activity — Stage 0 of commissioning: read the operator fixture and
extract a structured InterviewResult.

Consequence class: REVERSIBLE (read-only; no external side effects).
Idempotent: False — live inference is nondeterministic.  The idempotency_key
field is accepted for logging/audit tracing only, not for deduplication.
NOTE: INFER_STUB=1 env var enables deterministic fixture-based output for testing.

Stage 0 traversal order (INTERVIEW-PROTOCOL.md §2):
  what_is_sold → sold_to_whom → lifecycle → revenue_concentration →
  exceptions → consequence_taxonomy per tool → scenario walking → frame read-back

In stub mode, all fields are lifted verbatim from the fixture JSON with full
provenance records referencing the fixture path and JSON-path of each value.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.contracts.commission import (
    ContextFrame,
    ConsequenceTaxonomy,
    InterviewResult,
    ScenarioCard,
)

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@dataclass
class InterviewActivityInput:
    operator_id: str
    fixture_path: str
    model_id: str = ""          # ignored in stub mode; used in live mode for infer()
    idempotency_key: str = ""


@activity.defn(name="commission_interview")
async def interview_activity(inp: InterviewActivityInput) -> InterviewResult:
    """Stage 0: read fixture, extract ContextFrame/ConsequenceTaxonomy/ScenarioCards.

    STUB MODE (INFER_STUB=1): lifts all fields directly from the fixture JSON
    with provenance {"source": "fixture:<path>", "path": "$.<json-path>"}.
    Validates 5 <= len(scenario_cards) <= 10; raises non_retryable ApplicationError
    otherwise (an interview with too few cards is a fixture defect, not a transient).

    LIVE MODE: calls infer() per INTERVIEW-PROTOCOL.md prompt templates.
    Not yet implemented for Phase D (implemented in Phase E with real corpus).
    """
    from temporalio.exceptions import ApplicationError

    prov_source = f"fixture:{inp.fixture_path}"

    # ── Load fixture (file I/O is fine in activities) ─────────────────────────
    with open(inp.fixture_path) as fh:
        fixture = json.load(fh)

    if os.environ.get("INFER_STUB") == "1":
        biz = fixture["business"]
        lifecycle = fixture["lifecycle"]

        context_frame = ContextFrame(
            operator_id=inp.operator_id,
            business_name=biz["name"],
            what_is_sold=biz["what_is_sold"],
            sold_to_whom=biz["sold_to_whom"],
            lifecycle_stages=lifecycle["stages"],
            revenue_concentration=biz["revenue_concentration"],
            exceptions_that_matter=biz.get("exceptions", []),
            version=0,
            provenance={
                "source": prov_source,
                "path": "$.business",
            },
        )

        by_tool: dict[str, str] = {
            t["name"]: t["consequence_class"]
            for t in fixture.get("tools", [])
        }
        consequence_taxonomy = ConsequenceTaxonomy(
            by_tool=by_tool,
            provenance={
                "source": prov_source,
                "path": "$.tools[*].{name,consequence_class}",
            },
        )

        scenario_cards: list[ScenarioCard] = [
            ScenarioCard(
                card_id=s["card_id"],
                title=s["title"],
                narrative=s["narrative"],
                expected_stages=s["expected_stages"],
                expected_outcome=s["expected_outcome"],
                provenance={
                    "source": prov_source,
                    "path": f"$.scenarios[?(@.card_id=='{s['card_id']}')]",
                },
            )
            for s in fixture.get("scenarios", [])
        ]

        card_count = len(scenario_cards)
        if card_count < 5 or card_count > 10:
            raise ApplicationError(
                f"interview_activity: fixture must contain 5–10 scenario cards, "
                f"got {card_count} in {inp.fixture_path}",
                non_retryable=True,
            )

        frame_readback = (
            f"{biz['name']} sells {biz['what_is_sold']} to "
            f"{biz['sold_to_whom']}. "
            f"Lead lifecycle: {' → '.join(lifecycle['stages'])}. "
            f"Revenue note: {biz['revenue_concentration']}."
        )

        logger.info(
            "interview_activity STUB mode operator=%s stages=%s cards=%d",
            inp.operator_id,
            lifecycle["stages"],
            card_count,
        )

        return InterviewResult(
            context_frame=context_frame,
            consequence_taxonomy=consequence_taxonomy,
            scenario_cards=scenario_cards,
            frame_readback=frame_readback,
        )

    # ── Live mode ─────────────────────────────────────────────────────────────
    raise NotImplementedError(
        "Live interview inference: implement in Phase E with real operator corpus. "
        "See docs/INTERVIEW-PROTOCOL.md for prompt templates."
    )


register(Block(
    name="commission_interview",
    input_type="harness.commissioning.activities.interview.InterviewActivityInput",
    output_type="harness.shared.contracts.commission.InterviewResult",
    idempotent=False,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
