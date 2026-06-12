"""Phase B exit-gate integration tests — end-to-end scripted workflow.

Gate clauses (Doc 13 §Phase B):
  1. Scripted workflow runs a fixture lead end-to-end via live Temporal + DB.
  2. Same workflow runs TWICE idempotently → exactly one row per derived key
     in all FOUR tables the Intake flow writes (entity, event, state, task).

Additional: DSN two-DB guard unit test; registry unit test; key derivation unit test.

Stack required for integration tests:
  temporal server start-dev
  podman compose -f deploy/compose.yaml -f deploy/compose.dev.yaml up -d postgres-business
  python -m harness.shared.persistence.bootstrap
  python -m harness.worker  (in a separate terminal)
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from temporalio.client import Client

from harness.shared.contracts.intake import NormalizedIntakeEvent
from harness.shared.molecules.intake import derive_entity_key

# ── Unit tests (no live stack required) ───────────────────────────────────────


def test_dsn_rejects_temporal_host(monkeypatch):
    """Two-DB fail-fast guard: build_dsn() raises if host is postgres-temporal."""
    monkeypatch.setenv("POSTGRES_USER", "harness")
    monkeypatch.setenv("POSTGRES_PASSWORD", "changeme")
    monkeypatch.setenv("POSTGRES_DB", "harness")
    monkeypatch.setenv("DB_HOST", "postgres-temporal")

    from harness.shared.contracts.secrets import EnvSecretsProvider, set_provider
    set_provider(EnvSecretsProvider())

    from harness.shared.persistence.dsn import build_dsn
    with pytest.raises(RuntimeError, match="postgres-temporal"):
        build_dsn()


def test_dsn_rejects_temporal_db_name(monkeypatch):
    """Two-DB guard: build_dsn() raises if POSTGRES_DB is 'temporal'."""
    monkeypatch.setenv("POSTGRES_USER", "harness")
    monkeypatch.setenv("POSTGRES_PASSWORD", "changeme")
    monkeypatch.setenv("POSTGRES_DB", "temporal")
    monkeypatch.setenv("DB_HOST", "postgres-business")

    from harness.shared.contracts.secrets import EnvSecretsProvider, set_provider
    set_provider(EnvSecretsProvider())

    from harness.shared.persistence.dsn import build_dsn
    with pytest.raises(RuntimeError, match="temporal"):
        build_dsn()


def test_registry_idempotent_reregistration():
    """Registry: re-registering same block is a no-op; different metadata raises."""
    from harness.shared.capability.registry import _registry, register
    from harness.shared.contracts.block import Block, ConsequenceClass

    b = Block("_test_verb", "in", "out", True, ConsequenceClass.REVERSIBLE, "0.1.0")
    register(b)
    register(b)  # identical — no-op
    assert _registry["_test_verb"] is b

    b_diff = Block("_test_verb", "in", "out_different", True, ConsequenceClass.REVERSIBLE, "0.1.0")
    with pytest.raises(ValueError, match="additive rule"):
        register(b_diff)

    del _registry["_test_verb"]  # cleanup test isolation


def test_key_derivation_deterministic():
    """Key derivation: same identity_candidates → same entity key."""
    e1 = NormalizedIntakeEvent("web_form", "f1", {"email": "a@b.com"}, {}, "2024-01-01T00:00:00+00:00")
    e2 = NormalizedIntakeEvent("web_form", "f2", {"email": "a@b.com"}, {"extra": "ignored"}, "2024-06-01T00:00:00+00:00")
    assert derive_entity_key(e1.identity_candidates) == derive_entity_key(e2.identity_candidates)

    e3 = NormalizedIntakeEvent("web_form", "f3", {"email": "other@b.com"}, {}, "2024-01-01T00:00:00+00:00")
    assert derive_entity_key(e1.identity_candidates) != derive_entity_key(e3.identity_candidates)


def test_webform_adapter_normalizes():
    """WebFormAdapter: email/phone lifted to identity_candidates; rest goes to captured."""
    from harness.shared.intake.webform import WebFormAdapter

    adapter = WebFormAdapter()
    event = adapter.normalize({
        "email": " Alice@Example.COM ",
        "phone": "555-1234",
        "first_name": "Alice",
        "form_id": "form-42",
        "submitted_at": "2024-01-15T10:00:00+00:00",
    })

    assert event.identity_candidates == {"email": "alice@example.com", "phone": "555-1234"}
    assert "first_name" in event.captured_attributes
    assert event.source_channel == "web_form"
    assert event.raw_payload_ref == "form-42"
    assert event.source_timestamp == "2024-01-15T10:00:00+00:00"


# ── Integration: end-to-end exit gate ─────────────────────────────────────────

_TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
_TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "skeleton-queue")


@pytest.mark.integration
async def test_lead_intake_end_to_end(db_pool, test_key_prefix):
    """Exit gate: scripted workflow runs a fixture lead end-to-end twice, idempotently.

    Asserts exactly one row per derived key in all FOUR tables the Intake
    flow writes: entity, event, state, task.
    (relate/relationship is verified in isolation by test_phase_b_blocks.py.)
    """
    client = await Client.connect(_TEMPORAL_HOST)

    fixture_event = NormalizedIntakeEvent(
        source_channel="web_form",
        raw_payload_ref=f"test-form-{test_key_prefix}",
        identity_candidates={"email": f"{test_key_prefix}@test.example.com"},
        captured_attributes={"first_name": "Gate", "last_name": "Test"},
        source_timestamp="2024-01-15T10:00:00+00:00",
    )

    entity_key = derive_entity_key(fixture_event.identity_candidates)
    workflow_id = f"lead-intake-{entity_key}"

    async def _run_once() -> dict:
        from harness.operations.workflows.lead_intake import LeadIntakeWorkflow
        handle = await client.start_workflow(
            LeadIntakeWorkflow.run,
            fixture_event,
            id=workflow_id,
            task_queue=_TASK_QUEUE,
            execution_timeout=timedelta(seconds=60),
        )
        return await handle.result()

    # First run — creates rows.
    result1 = await _run_once()
    assert result1["entity_key"] == entity_key
    assert result1["entity_created"] is True

    # Verify exactly one row per key in all four Intake-touched tables.
    async with db_pool.acquire() as conn:
        def _count(table, key):
            return conn.fetchval(
                f"SELECT COUNT(*) FROM {table} WHERE idempotency_key = $1", key
            )

        import hashlib, json

        def k(*parts):
            return hashlib.sha256(":".join(parts).encode()).hexdigest()[:32]

        event_key = k(entity_key, "web_form", f"test-form-{test_key_prefix}")
        state_key = k(entity_key, "lead", "engage_open")
        task_key = k(entity_key, "first_follow_up", event_key)

        assert await _count("entity", entity_key) == 1
        assert await _count("event", event_key) == 1
        assert await _count("state", state_key) == 1
        assert await _count("task", task_key) == 1

    # Second run — must be idempotent; all counts remain 1.
    result2 = await _run_once()
    assert result2["entity_id"] == result1["entity_id"]

    async with db_pool.acquire() as conn:
        event_key = k(entity_key, "web_form", f"test-form-{test_key_prefix}")
        state_key = k(entity_key, "lead", "engage_open")
        task_key = k(entity_key, "first_follow_up", event_key)

        assert await conn.fetchval("SELECT COUNT(*) FROM entity WHERE idempotency_key = $1", entity_key) == 1
        assert await conn.fetchval("SELECT COUNT(*) FROM event WHERE idempotency_key = $1", event_key) == 1
        assert await conn.fetchval("SELECT COUNT(*) FROM state WHERE idempotency_key = $1", state_key) == 1
        assert await conn.fetchval("SELECT COUNT(*) FROM task WHERE idempotency_key = $1", task_key) == 1
