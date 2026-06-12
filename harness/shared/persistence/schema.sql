-- Five-primitive schema for the business Postgres (Phase B).
-- Two-Postgres hard rule: this SQL targets ONLY postgres-business, never postgres-temporal.
-- State is append-only (bigserial seq + created_at ordering).
-- All type/machine/position/status are text — no enums (invariant 3: no closed sets).
-- idempotency_key UNIQUE enforces exactly-once writes across retries.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS entity (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    type             text        NOT NULL,
    attributes       jsonb       NOT NULL DEFAULT '{}',
    idempotency_key  text        UNIQUE NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS relationship (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    type             text        NOT NULL,
    from_entity_id   uuid        NOT NULL REFERENCES entity(id),
    to_entity_id     uuid        NOT NULL REFERENCES entity(id),
    attributes       jsonb       NOT NULL DEFAULT '{}',
    idempotency_key  text        UNIQUE NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    type             text        NOT NULL,
    actor            text        NOT NULL DEFAULT '',
    entity_id        uuid        NOT NULL REFERENCES entity(id),
    payload          jsonb       NOT NULL DEFAULT '{}',
    occurred_at      timestamptz NOT NULL,
    idempotency_key  text        UNIQUE NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Append-only: each transition INSERTs a new row.
-- Current position = latest by seq per (entity_id, machine).
-- No UPDATE-in-place: audit history is preserved for Phase C replay audit.
CREATE TABLE IF NOT EXISTS state (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id        uuid        NOT NULL REFERENCES entity(id),
    machine          text        NOT NULL,
    position         text        NOT NULL,
    attributes       jsonb       NOT NULL DEFAULT '{}',
    idempotency_key  text        UNIQUE NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    seq              bigserial   NOT NULL
);

CREATE TABLE IF NOT EXISTS task (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    type             text        NOT NULL,
    assignee         text        NOT NULL DEFAULT '',
    entity_id        uuid        NOT NULL REFERENCES entity(id),
    status           text        NOT NULL DEFAULT 'open',
    attributes       jsonb       NOT NULL DEFAULT '{}',
    idempotency_key  text        UNIQUE NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);
