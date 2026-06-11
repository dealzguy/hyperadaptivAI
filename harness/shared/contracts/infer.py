"""Infer contract — Phase A stub only. No real model calls in this phase.

Contract: infer(request) -> InferResult
Settled constraint (doc 12 §2): nothing above this line names a model.
Phase C replaces this stub with LiteLLM + Ollama behind the same interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InferRequest:
    model_id: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    policy: dict[str, Any] | None = None


@dataclass
class InferResult:
    content: str
    model_id: str
    usage: dict[str, Any] = field(default_factory=dict)


async def infer(request: InferRequest) -> InferResult:
    """Phase A stub — returns deterministic echo. Replaced in Phase C."""
    last_content = ""
    if request.messages:
        last_content = str(request.messages[-1].get("content", ""))
    return InferResult(
        content=f"[STUB] echo: {last_content}",
        model_id=request.model_id,
    )
