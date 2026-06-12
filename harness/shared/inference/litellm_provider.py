"""LiteLLM-backed infer provider — routes to local Ollama only.

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

# OLLAMA_BASE_URL env var is set by compose.yaml for the harness-worker service.
# Default is localhost for local dev (outside compose).
OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


async def infer(inp: InferInput) -> InferResult:
    """Call Ollama via LiteLLM.  Raises ValueError for cloud model IDs."""
    _guard_model_id(inp.model_id)
    validate_policy(inp.policy)

    kwargs: dict = {
        "model": inp.model_id,
        "messages": inp.messages,
        "api_base": OLLAMA_BASE_URL,
        "num_retries": 0,
    }

    if inp.policy.get("max_tokens"):
        kwargs["max_tokens"] = inp.policy["max_tokens"]
    if inp.policy.get("temperature") is not None:
        kwargs["temperature"] = inp.policy["temperature"]
    if inp.tools:
        kwargs["tools"] = inp.tools
        kwargs["tool_choice"] = "auto"
    if inp.response_format:
        kwargs["response_format"] = inp.response_format

    logger.debug("infer: model=%s base=%s", inp.model_id, OLLAMA_BASE_URL)
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
