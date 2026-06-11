"""
Infer contract — the seam between all harness code and the model layer.

Nothing above this line names a model. Phase A provides the stub implementation
only; Phase C replaces it with the Ollama + LiteLLM backend behind the same
interface signature.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InferRequest:
    model_id: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    policy: dict[str, Any]


@dataclass
class InferResponse:
    content: str
    model: str
    tokens_used: int
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Contract interface — Phase C implements this with Ollama + LiteLLM.
# ---------------------------------------------------------------------------

async def infer(request: InferRequest) -> InferResponse:
    raise NotImplementedError("infer() is not implemented in Phase A; use infer_stub() for tests")


# ---------------------------------------------------------------------------
# Stub — Phase A only.  Smoke-tested by tests/test_infer_stub.py.
# No model call; no containers required.
# ---------------------------------------------------------------------------

async def infer_stub(request: InferRequest) -> InferResponse:
    return InferResponse(
        content="[stub] no model call in Phase A",
        model="stub",
        tokens_used=0,
        tool_calls=[],
    )
