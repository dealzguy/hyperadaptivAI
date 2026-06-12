"""Infer contract — typed I/O dataclasses and model-ID guard.

Contract: infer(InferInput) -> InferResult
Settled constraint (doc 12 §2): nothing above this line names a model.
The implementation lives in harness/shared/inference/litellm_provider.py.

_guard_model_id: allowlist-based guard, configured via INFER_ALLOWED_PREFIXES env var
(comma-separated provider prefix strings). Defaults to ("anthropic/",) for initial
testing. Operators add providers by configuration, not code edits (Invariant 3: no
closed enumerations on growing sets). Nothing above infer() names a provider —
this guard enforces the open-set rule, not a specific provider (Invariant 2:
model-agnostic above the inference line).
See docs/CONFIG-BUNDLE-SPEC.md §model_policy for normative grammar.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_INFER_ALLOWED_PREFIXES_DEFAULT = ("anthropic/",)


def _get_allowed_prefixes() -> tuple[str, ...]:
    """Read INFER_ALLOWED_PREFIXES env var (comma-separated) or use default."""
    raw = os.environ.get("INFER_ALLOWED_PREFIXES", "")
    if raw.strip():
        return tuple(p.strip() for p in raw.split(",") if p.strip())
    return _INFER_ALLOWED_PREFIXES_DEFAULT


@dataclass
class InferInput:
    model_id: str                          # e.g. "anthropic/claude-sonnet-4-6" (or "openai/gpt-4o-mini", "groq/llama-3.1-8b-instant")
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
    """Raise ValueError if model_id does not match the configured provider allowlist.

    Allowlist is driven by env INFER_ALLOWED_PREFIXES (comma-separated prefix strings).
    Defaults to ("anthropic/",) for testing. Operators add providers by configuration,
    not code edits (Invariant 3: no closed enumerations on growing sets).
    Nothing above infer() names a provider — this guard enforces the open-set rule,
    not a specific provider (Invariant 2: model-agnostic above the inference line).
    """
    allowed = _get_allowed_prefixes()
    if not any(model_id.startswith(p) for p in allowed):
        raise ValueError(
            f"model_id {model_id!r} does not match any configured provider prefix. "
            f"Allowed prefixes (INFER_ALLOWED_PREFIXES): {allowed}. "
            "Add the provider prefix to INFER_ALLOWED_PREFIXES to enable it."
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
