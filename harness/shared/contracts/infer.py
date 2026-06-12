"""Infer contract — typed I/O dataclasses and model-ID guard.

Contract: infer(InferInput) -> InferResult
Settled constraint (doc 12 §2): nothing above this line names a model.
The implementation lives in harness/shared/inference/litellm_provider.py.

_guard_model_id: allowlist-based — ONLY "ollama/<name>" is permitted.
Previous denylist (CLOUD_MODEL_PREFIXES) was bypassable via provider-prefixed
LiteLLM IDs like "openai/gpt-4o", "anthropic/claude-3-haiku", "groq/...", etc.
Allowlist closes the entire class in one check and does not enumerate cloud
providers (satisfies Invariant 3: no closed enumerations on growing sets).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InferInput:
    model_id: str                          # e.g. "ollama/llama3.2:3b"
    messages: list[dict[str, Any]]         # [{"role": "user", "content": "..."}]
    tools: list[dict[str, Any]] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)  # max_tokens, temperature, …
    response_format: dict[str, Any] = field(default_factory=dict)  # structured outputs; {} = none
    # TODO(liquid: policy schema — Phase D config-bundle spec formalizes)


@dataclass
class InferResult:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    model_id_used: str = ""
    finish_reason: str = ""


def _guard_model_id(model_id: str) -> None:
    """Raise ValueError if model_id is not a local Ollama model.

    Allowlist: only "ollama/<name>" is accepted. Any other prefix (including
    LiteLLM provider-prefixed IDs like openai/, anthropic/, groq/, azure/,
    vertex_ai/, bedrock/, xai/, or bare names like gpt-4) is rejected.
    """
    if not model_id.startswith("ollama/"):
        raise ValueError(
            f"model_id {model_id!r} is not a local Ollama model. "
            "All inference must route through local Ollama. "
            "Use 'ollama/<model-name>' format (e.g. 'ollama/llama3.2:3b')."
        )


def validate_policy(policy: dict[str, Any]) -> None:
    """Validate known policy keys; warn-and-ignore unknown keys (open set).

    Known keys:
      max_tokens  — int, must be > 0
      temperature — float, must be in [0.0, 2.0]

    Unknown keys are warned about but not rejected, preserving the open-set
    invariant (Invariant 3) while preventing silent misconfiguration.
    TODO(liquid: policy schema — Phase D config-bundle spec formalizes)
    """
    known_keys = {"max_tokens", "temperature"}
    for key, value in policy.items():
        if key == "max_tokens":
            if not isinstance(value, int) or value <= 0:
                raise ValueError(
                    f"policy['max_tokens'] must be a positive int, got {value!r}"
                )
        elif key == "temperature":
            if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 2.0):
                raise ValueError(
                    f"policy['temperature'] must be a float in [0.0, 2.0], got {value!r}"
                )
        elif key not in known_keys:
            logger.warning(
                "validate_policy: unknown policy key %r=%r — ignored "
                "(will be formalized in Phase D config-bundle spec)",
                key,
                value,
            )
