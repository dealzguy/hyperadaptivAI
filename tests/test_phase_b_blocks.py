"""Phase B block tests — golden and property tests for all five verb activities.

Coverage obligation (Phase B exit gate):
  5 verbs × {golden, property} = 10 test obligations.

Test isolation: all idempotency keys are namespaced with test_key_prefix
(a per-test UUID prefix), so assertions are per-key-local and tests can
run repeatedly without collisions. No global COUNT(*) assertions.

Property tests use Hypothesis to assert the idempotency invariant:
  writing the same key N times → exactly one row for that key.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness.shared.crm.primitives import (
    AssignTaskInput,
    CreateEntityInput,
    RecordEventInput,
    RelateInput,
    TransitionStateInput,
)

pytestmark = pytest.mark.integration

# ── Helpers ───────────────────────────────────────────────────────────────────


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _count_by_key(conn, table: str, key: str) -> int:
    row = await conn.fetchrow(
        f"SELECT COUNT(*) AS n FROM {table} WHERE idempotency_key = $1", key
    )
    return row["n"]


# ── create_entity ─────────────────────────────────────────────────────────────


async def test_create_entity_golden(db_conn, test_key_prefix):
    """Golden: insert a new entity row; re-insert is a no-op."""
    from harness.shared.crm.verbs import create_entity
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    key = f"{test_key_prefix}:entity:lead1"

    out1 = await create_entity(CreateEntityInput(entity_type="lead", attributes={"name": "Alice"}, idempotency_key=key))
    assert out1.idempotency_key == key
    assert out1.created is True

    out2 = await create_entity(CreateEntityInput(entity_type="lead", attributes={"name": "Alice"}, idempotency_key=key))
    assert out2.id == out1.id
    assert out2.created is False

    count = await _count_by_key(db_conn, "entity", key)
    assert count == 1


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=15)
@given(attrs=st.dictionaries(
    st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters="\x00")),
    st.text(max_size=20, alphabet=st.characters(blacklist_characters="\x00")),
    max_size=5,
))
async def test_create_entity_property_idempotency(db_conn, test_key_prefix, attrs):
    """Property: same key with any jsonb attributes → exactly one row for that key."""
    from harness.shared.crm.verbs import create_entity
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    key = f"{test_key_prefix}:prop:entity:{hash(json.dumps(attrs, sort_keys=True)) % 10000}"

    await create_entity(CreateEntityInput(entity_type="lead", attributes=attrs, idempotency_key=key))
    await create_entity(CreateEntityInput(entity_type="lead", attributes=attrs, idempotency_key=key))
    count = await _count_by_key(db_conn, "entity", key)
    assert count == 1


# ── relate ────────────────────────────────────────────────────────────────────


async def test_relate_golden(db_conn, test_key_prefix):
    """Golden: insert relationship; re-insert is a no-op."""
    from harness.shared.crm.verbs import create_entity, relate
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())

    e1 = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:re1"))
    e2 = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:re2"))
    rel_key = f"{test_key_prefix}:rel:1"

    out1 = await relate(RelateInput("knows", e1.id, e2.id, {}, rel_key))
    assert out1.created is True

    out2 = await relate(RelateInput("knows", e1.id, e2.id, {}, rel_key))
    assert out2.id == out1.id
    assert out2.created is False
    assert await _count_by_key(db_conn, "relationship", rel_key) == 1


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=10)
@given(rtype=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_characters="\x00")))
async def test_relate_property_idempotency(db_conn, test_key_prefix, rtype):
    """Property: same relationship key → exactly one row."""
    from harness.shared.crm.verbs import create_entity, relate
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    e1 = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:rp1:{hash(rtype)%1000}"))
    e2 = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:rp2:{hash(rtype)%1000}"))
    key = f"{test_key_prefix}:relprop:{hash(rtype)%10000}"
    await relate(RelateInput(rtype, e1.id, e2.id, {}, key))
    await relate(RelateInput(rtype, e1.id, e2.id, {}, key))
    assert await _count_by_key(db_conn, "relationship", key) == 1


# ── record_event ──────────────────────────────────────────────────────────────


async def test_record_event_golden(db_conn, test_key_prefix):
    """Golden: insert event; re-insert is a no-op."""
    from harness.shared.crm.verbs import create_entity, record_event
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    entity = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:ev_e"))
    ev_key = f"{test_key_prefix}:ev1"

    out1 = await record_event(RecordEventInput("intake_received", entity.id, {"x": 1}, iso_now(), ev_key))
    assert out1.created is True

    out2 = await record_event(RecordEventInput("intake_received", entity.id, {"x": 1}, iso_now(), ev_key))
    assert out2.id == out1.id
    assert out2.created is False
    assert await _count_by_key(db_conn, "event", ev_key) == 1


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=10)
@given(payload=st.dictionaries(st.text(min_size=1, max_size=8, alphabet=st.characters(blacklist_characters="\x00")), st.integers(), max_size=4))
async def test_record_event_property_idempotency(db_conn, test_key_prefix, payload):
    """Property: same event key with any jsonb payload → exactly one row."""
    from harness.shared.crm.verbs import create_entity, record_event
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    entity = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:evp_e:{hash(str(payload))%1000}"))
    key = f"{test_key_prefix}:evprop:{hash(json.dumps(payload, sort_keys=True))%10000}"
    await record_event(RecordEventInput("test_ev", entity.id, payload, iso_now(), key))
    await record_event(RecordEventInput("test_ev", entity.id, payload, iso_now(), key))
    assert await _count_by_key(db_conn, "event", key) == 1


# ── transition_state ──────────────────────────────────────────────────────────


async def test_transition_state_golden(db_conn, test_key_prefix):
    """Golden: append state row; re-append same key is a no-op; history preserved."""
    from harness.shared.crm.verbs import create_entity, transition_state
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    entity = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:st_e"))
    st_key = f"{test_key_prefix}:st1"

    out1 = await transition_state(TransitionStateInput(entity.id, "lead", "engage_open", {}, st_key))
    assert out1.created is True

    # Second run: same key → no new row (idempotent).
    out2 = await transition_state(TransitionStateInput(entity.id, "lead", "engage_open", {}, st_key))
    assert out2.id == out1.id
    assert out2.created is False
    assert await _count_by_key(db_conn, "state", st_key) == 1

    # Different key → second row (history preserved, append-only).
    st_key2 = f"{test_key_prefix}:st2"
    out3 = await transition_state(TransitionStateInput(entity.id, "lead", "qualified", {}, st_key2))
    assert out3.created is True
    assert await _count_by_key(db_conn, "state", st_key2) == 1


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=10)
@given(position=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_characters="\x00")))
async def test_transition_state_property_idempotency(db_conn, test_key_prefix, position):
    """Property: same state key → exactly one row for that key."""
    from harness.shared.crm.verbs import create_entity, transition_state
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    entity = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:stp_e:{hash(position)%1000}"))
    key = f"{test_key_prefix}:stprop:{hash(position)%10000}"
    await transition_state(TransitionStateInput(entity.id, "lead", position, {}, key))
    await transition_state(TransitionStateInput(entity.id, "lead", position, {}, key))
    assert await _count_by_key(db_conn, "state", key) == 1


# ── assign_task ───────────────────────────────────────────────────────────────


async def test_assign_task_golden(db_conn, test_key_prefix):
    """Golden: insert task; re-insert is a no-op."""
    from harness.shared.crm.verbs import assign_task, create_entity
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    entity = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:ta_e"))
    tk_key = f"{test_key_prefix}:tk1"

    out1 = await assign_task(AssignTaskInput("first_follow_up", entity.id, {}, tk_key))
    assert out1.created is True

    out2 = await assign_task(AssignTaskInput("first_follow_up", entity.id, {}, tk_key))
    assert out2.id == out1.id
    assert out2.created is False
    assert await _count_by_key(db_conn, "task", tk_key) == 1


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=10)
@given(task_type=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_characters="\x00")))
async def test_assign_task_property_idempotency(db_conn, test_key_prefix, task_type):
    """Property: same task key → exactly one row for that key."""
    from harness.shared.crm.verbs import assign_task, create_entity
    from harness.shared.persistence.pool import set_pool

    class _FakePool:
        def acquire(self):
            return _FakePoolCtx(db_conn)

    class _FakePoolCtx:
        def __init__(self, conn):
            self._conn = conn
        async def __aenter__(self):
            return self._conn
        async def __aexit__(self, *_):
            pass

    set_pool(_FakePool())
    entity = await create_entity(CreateEntityInput("lead", {}, f"{test_key_prefix}:tap_e:{hash(task_type)%1000}"))
    key = f"{test_key_prefix}:tkprop:{hash(task_type)%10000}"
    await assign_task(AssignTaskInput(task_type, entity.id, {}, key))
    await assign_task(AssignTaskInput(task_type, entity.id, {}, key))
    assert await _count_by_key(db_conn, "task", key) == 1
