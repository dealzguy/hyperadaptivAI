"""LiteLLM-backed infer provider — routes to a configured external API provider via LiteLLM.

Provider selected by model_id prefix; API key read from env (e.g. ANTHROPIC_API_KEY
for anthropic/ models). Optional INFER_API_BASE for self-hosted or OpenAI-compatible
endpoints.

litellm.num_retries is set to 0 here (module import time) so the value is
established before any completion call is made.  The canonical place to
enforce this is worker.py main() (which imports this module before starting
the worker), but setting it here as well ensures correctness even in test
contexts that import this module directly.

Temporal handles all retries via activity retry policy; LiteLLM retries would
create duplicate side-effects that Temporal cannot track.
"""
from __future__ import annotations

import logging
import os

import litellm

from harness.shared.contracts.infer import InferInput, InferResult, _guard_model_id, validate_policy

# Disable LiteLLM retries — Temporal activity retry policy owns this.
litellm.num_retries = 0

logger = logging.getLogger(__name__)

async def infer(inp: InferInput) -> InferResult:
    """Call the configured API provider via LiteLLM.  Raises ValueError for unconfigured model IDs."""
    _guard_model_id(inp.model_id)
    validate_policy(inp.policy)

    kwargs: dict = {
        "model": inp.model_id,
        "messages": inp.messages,
        "num_retries": 0,
    }

    infer_api_base = os.environ.get("INFER_API_BASE", "")
    if infer_api_base:
        kwargs["api_base"] = infer_api_base

    if inp.policy.get("max_tokens"):
        kwargs["max_tokens"] = inp.policy["max_tokens"]
    if inp.policy.get("temperature") is not None:
        kwargs["temperature"] = inp.policy["temperature"]
    if inp.tools:
        kwargs["tools"] = inp.tools
        kwargs["tool_choice"] = "auto"
    if inp.response_format:
        kwargs["response_format"] = inp.response_format

    logger.debug("infer: model=%s api_base=%s", inp.model_id, kwargs.get("api_base", ""))
    resp = await litellm.acompletion(**kwargs)

    choice = resp.choices[0]

    tool_calls: list[dict] = []
    if choice.message.tool_calls:
        tool_calls = [
            {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }
            for tc in choice.message.tool_calls
        ]

    return InferResult(
        content=choice.message.content or "",
        tool_calls=tool_calls,
        tokens_used=resp.usage.total_tokens if resp.usage else 0,
        model_id_used=resp.model or inp.model_id,
        finish_reason=choice.finish_reason or "",
    )
