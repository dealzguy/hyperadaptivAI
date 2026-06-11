"""
Smoke test for the infer contract stub.

Exercises the interface (types, return values) without any model call or
containers.  This is the 'smoke test through the infer contract stub' required
by CLAUDE.md for Phase A.
"""
import pytest

from harness.contracts.infer import InferRequest, InferResponse, infer_stub


@pytest.mark.asyncio
async def test_infer_stub_returns_response():
    req = InferRequest(
        model_id="stub",
        messages=[{"role": "user", "content": "ping"}],
        tools=[],
        policy={},
    )
    resp = await infer_stub(req)
    assert isinstance(resp, InferResponse)
    assert resp.model == "stub"
    assert resp.tokens_used == 0
    assert resp.tool_calls == []
    assert "[stub]" in resp.content


@pytest.mark.asyncio
async def test_infer_stub_ignores_model_id():
    """Stub returns the same canned response regardless of model_id."""
    req = InferRequest(
        model_id="some-real-model",
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        policy={},
    )
    resp = await infer_stub(req)
    assert resp.model == "stub"


@pytest.mark.asyncio
async def test_infer_raises_not_implemented():
    """The real infer() contract raises until Phase C implements it."""
    from harness.contracts.infer import infer

    req = InferRequest(model_id="any", messages=[], tools=[], policy={})
    with pytest.raises(NotImplementedError):
        await infer(req)
