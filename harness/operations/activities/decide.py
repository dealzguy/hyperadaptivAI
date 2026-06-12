"""decide_activity — invoke inference to choose the next agent action.

Consequence class: REVERSIBLE (pure inference call; no external side effects).
Idempotent: False — inference output is nondeterministic. The idempotency_key
field is accepted for logging/audit tracing only, not for deduplication.
NOTE: INFER_STUB=1 env var enables deterministic stub output for testing.

Invariant 2 (model-agnostic above the inference line): model_id comes from
the caller (AgentLoopInput, sourced from the config bundle) — never hardcoded
here or in the workflow.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.contracts.infer import InferInput
from harness.shared.inference.litellm_provider import infer

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@dataclass
class DecideInput:
    agent_id: str
    run_id: str
    step: int
    model_id: str
    context_dict: dict
    tool_allowlist: list
    budget_remaining: int
    idempotency_key: str


@dataclass
class DecideResult:
    action_type: str
    action_payload: dict
    rationale: str
    tokens_used: int
    confidence: float


@activity.defn
async def decide_activity(inp: DecideInput) -> DecideResult:
    """Choose the next action via inference.

    STUB MODE (INFER_STUB=1): returns the first tool in allowlist without a
    model call — used for deterministic loop tests.

    LIVE MODE: calls infer() → LiteLLM → local Ollama only. model_id is
    validated by _guard_model_id inside litellm_provider (allowlist enforced).
    """
    if os.environ.get("INFER_STUB") == "1":
        fallback = inp.tool_allowlist[0] if inp.tool_allowlist else "record_event"
        logger.info(
            "decide_activity STUB mode agent=%s step=%d action=%s",
            inp.agent_id, inp.step, fallback,
        )
        return DecideResult(
            action_type=fallback,
            action_payload={},
            rationale="stub",
            tokens_used=0,
            confidence=1.0,
        )

    tool_list_str = ", ".join(inp.tool_allowlist)
    context_summary = json.dumps(inp.context_dict, default=str)

    system_msg = (
        f"You are an agent. Your available actions are: [{tool_list_str}]. "
        "Choose the next single action given the context. "
        "Respond as JSON with keys: action_type (string), action_payload (object), "
        "rationale (string), confidence (float 0-1). "
        "action_type MUST be one of the listed available actions."
    )
    user_msg = f"Context: {context_summary}\nBudget remaining tokens: {inp.budget_remaining}"

    infer_input = InferInput(
        model_id=inp.model_id,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        policy={"max_tokens": 512, "temperature": 0.0},
    )

    result = await infer(infer_input)

    # Parse the JSON decision from model content.
    action_type = inp.tool_allowlist[0] if inp.tool_allowlist else "record_event"
    action_payload: dict = {}
    rationale = ""
    confidence = 0.5

    try:
        parsed = json.loads(result.content)
        action_type = str(parsed.get("action_type", action_type))
        action_payload = parsed.get("action_payload", {})
        if not isinstance(action_payload, dict):
            action_payload = {}
        rationale = str(parsed.get("rationale", ""))
        raw_conf = parsed.get("confidence", confidence)
        confidence = float(raw_conf) if isinstance(raw_conf, (int, float)) else confidence
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning(
            "decide_activity: failed to parse model JSON at step=%d: %s — using fallback",
            inp.step, exc,
        )

    logger.info(
        "decide_activity agent=%s step=%d action=%s confidence=%.2f tokens=%d",
        inp.agent_id, inp.step, action_type, confidence, result.tokens_used,
    )

    return DecideResult(
        action_type=action_type,
        action_payload=action_payload,
        rationale=rationale,
        tokens_used=result.tokens_used,
        confidence=confidence,
    )


register(Block(
    name="decide",
    input_type="harness.operations.activities.decide.DecideInput",
    output_type="harness.operations.activities.decide.DecideResult",
    idempotent=False,
    consequence_class=ConsequenceClass.REVERSIBLE,
    version=_VERSION,
))
