"""Infer contract — typed I/O dataclasses and model-ID guard.

Contract: infer(InferInput) -> InferResult
Settled constraint (doc 12 §2): nothing above this line names a model.
The implementation lives in harness/shared/inference/litellm_provider.py.

_guard_model_id: allowlist-based — ONLY "ollama/<name>" (completion endpoint)
OR "ollama_chat/<name>" (chat-completions endpoint) is permitted.
See docs/CONFIG-BUNDLE-SPEC.md §model_policy for normative grammar.
Liquid resolution recorded in docs/LIQUID-RESOLUTIONS.md ("infer guard prefix set").
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
    # TODO(liquid: policy schema) RESOLVED — see docs/CONFIG-BUNDLE-SPEC.md §policy.
    # Known keys: max_tokens (int>0), temperature (float[0,2]); open for append.


@dataclass
class InferResult:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    model_id_used: str = ""
    finish_reason: str = ""


def _guard_model_id(model_id: str) -> None:
    """Raise ValueError if model_id is not a local Ollama model.

    Allowlist: "ollama/<name>" (generation endpoint) and "ollama_chat/<name>"
    (chat completions endpoint — required for structured outputs, used in config
    bundles as model_policy.decide and model_policy.escalate).
    Both prefixes route exclusively to local Ollama — cloud isolation is preserved.
    Any other prefix (openai/, anthropic/, groq/, azure/, vertex_ai/, bedrock/,
    xai/, bare gpt-4, etc.) is rejected.
    """
    if not model_id.startswith(("ollama/", "ollama_chat/")):
        raise ValueError(
            f"model_id {model_id!r} is not a local Ollama model. "
            "All inference must route through local Ollama. "
            "Use 'ollama/<name>' or 'ollama_chat/<name>' format."
        )


def validate_policy(policy: dict[str, Any]) -> None:
    """Validate known policy keys; warn-and-ignore unknown keys (open set).

    Known keys:
      max_tokens  — int, must be > 0
      temperature — float, must be in [0.0, 2.0]

    Unknown keys are warned about but not rejected, preserving the open-set
    invariant (Invariant 3) while preventing silent misconfiguration.
    TODO(liquid: policy schema) RESOLVED — see docs/CONFIG-BUNDLE-SPEC.md §policy.
    Known keys: max_tokens (int>0), temperature (float[0,2]); open for append.
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
