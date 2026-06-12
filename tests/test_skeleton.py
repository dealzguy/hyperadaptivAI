"""Phase A exit gate tests.

Unit tests: run always (no stack required).
Integration tests: marked @pytest.mark.integration — require running compose stack.

Phase A gate criteria (doc 13):
  ✓ Hello-world workflow runs end-to-end
  ✓ Infer contract stub returns deterministic response (smoke test)
  ✓ Software/config/data separation: compose.yaml uses named volumes + mounted config
"""
import uuid

import pytest

# ── Unit tests — no stack required ────────────────────────────────────────

def test_guard_accepts_default_allowlist():
    """_guard_model_id accepts the default allowlist prefix (anthropic/) without any env set."""
    from harness.shared.contracts.infer import _guard_model_id, InferInput
    # Should not raise — anthropic/ is the default allowed prefix
    _guard_model_id("anthropic/claude-sonnet-4-6")
    # InferInput is constructable with an allowed model_id
    inp = InferInput(
        model_id="anthropic/claude-sonnet-4-6",
        messages=[{"role": "user", "content": "ping"}],
    )
    assert inp.model_id == "anthropic/claude-sonnet-4-6"


def test_secrets_provider_raises_on_missing_key():
    """Secrets contract raises clearly when a key is absent."""
    from harness.shared.contracts.secrets import EnvSecretsProvider
    provider = EnvSecretsProvider()
    with pytest.raises(RuntimeError, match="NONEXISTENT_KEY_XYZ"):
        provider.get("NONEXISTENT_KEY_XYZ")


def test_hello_activity_returns_greeting():
    """hello_activity is deterministic and testable in isolation."""
    from harness.workflows.skeleton.activity import hello_activity
    assert hello_activity("Phase-A") == "Hello, Phase-A!"


# ── Integration tests — require running compose stack ─────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_hello_workflow_end_to_end():
    """HelloWorkflow runs end-to-end against a live Temporal server."""
    from temporalio.client import Client
    from harness.workflows.skeleton.workflow import HelloWorkflow

    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        HelloWorkflow.run,
        "Phase-A",
        id=f"test-hello-{uuid.uuid4()}",
        task_queue="skeleton-queue",
    )
    assert result == "Hello, Phase-A!"
