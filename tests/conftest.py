"""pytest configuration for Phase A + Phase B tests.

Integration tests (marked @pytest.mark.integration) require:
  - Temporal dev server:  temporal server start-dev
  - postgres-business:    podman compose -f deploy/compose.yaml -f deploy/compose.dev.yaml up -d postgres-business
  - Schema bootstrap:     python -m harness.shared.persistence.bootstrap
  - Worker (for e2e):     python -m harness.worker

  pytest tests/ -m integration

Unit tests run without a live stack.

DB isolation strategy: integration tests share a dedicated 'test' search_path
(schema) applied once per session, and idempotency keys are namespaced with a
per-test UUID prefix so assertions are per-key-local (no global COUNT(*) that
would collide across tests or re-runs).
"""
from __future__ import annotations

import os
import uuid

import pytest

# ── Markers ───────────────────────────────────────────────────────────────────


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires a running Temporal + postgres-business stack",
    )


# ── DB fixtures ───────────────────────────────────────────────────────────────

_TEST_DB_HOST = os.environ.get("TEST_DB_HOST", "127.0.0.1")
_TEST_DB_PORT = int(os.environ.get("TEST_DB_PORT", "5433"))
_TEST_DB_USER = os.environ.get("POSTGRES_USER", "harness")
_TEST_DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "changeme")
_TEST_DB_NAME = os.environ.get("POSTGRES_DB", "harness")


def _db_dsn() -> str:
    return (
        f"postgresql://{_TEST_DB_USER}:{_TEST_DB_PASSWORD}"
        f"@{_TEST_DB_HOST}:{_TEST_DB_PORT}/{_TEST_DB_NAME}"
    )


# Function-scoped pool to avoid event-loop mismatch with pytest-asyncio 0.23.x
# (asyncpg pools are bound to the loop that created them; function-scoped
# tests get a fresh loop each run, so the pool must be created in that same loop).
@pytest.fixture
async def db_pool():
    """Function-scoped asyncpg pool for integration tests."""
    import asyncpg
    from harness.shared.persistence.bootstrap import apply_schema

    pool = await asyncpg.create_pool(_db_dsn(), min_size=1, max_size=5)
    await apply_schema(pool)
    yield pool
    await pool.close()


@pytest.fixture
def test_key_prefix() -> str:
    """Per-test idempotency key namespace — keeps assertions per-key-local."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def db_conn():
    """Per-test asyncpg connection. Tests use test_key_prefix for row isolation."""
    import asyncpg
    conn = await asyncpg.connect(_db_dsn())
    yield conn
    await conn.close()
