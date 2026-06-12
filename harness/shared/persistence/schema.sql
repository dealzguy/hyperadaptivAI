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

-- Agent episodic memory (Phase C). Append-only.
-- entity_key added in Phase C for entity-scoped situate retrieval.
-- Migration note for existing dev DBs: the ALTER below is idempotent (ADD COLUMN IF NOT EXISTS).
-- Drop the dev volume or run:
--   ALTER TABLE agent_episodic ADD COLUMN IF NOT EXISTS entity_key text NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS agent_episodic (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         text        NOT NULL,
    run_id           text        NOT NULL,   -- stores workflow_id; append-only, stable across retries
    step             int         NOT NULL,
    action_type      text        NOT NULL,
    action_payload   jsonb       NOT NULL DEFAULT '{}',
    outcome_payload  jsonb       NOT NULL DEFAULT '{}',
    model_id         text        NOT NULL DEFAULT '',
    token_count      int         NOT NULL DEFAULT 0,
    entity_key       text        NOT NULL DEFAULT '',
    idempotency_key  text        UNIQUE NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);
-- Idempotent migration for existing dev DBs that predate the entity_key column.
ALTER TABLE agent_episodic ADD COLUMN IF NOT EXISTS entity_key text NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS agent_episodic_lookup ON agent_episodic (agent_id, run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS agent_episodic_entity ON agent_episodic (agent_id, entity_key, created_at DESC);

-- Agent directive (editable priorities). One row per agent_id (upsert).
CREATE TABLE IF NOT EXISTS agent_directive (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         text        UNIQUE NOT NULL,
    priority_text    text        NOT NULL DEFAULT '',
    attributes       jsonb       NOT NULL DEFAULT '{}',
    idempotency_key  text        NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Knowledge store (pgvector). Requires vector extension.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS knowledge_doc (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace        text        NOT NULL,
    content          text        NOT NULL,
    embedding        vector(768),
    metadata         jsonb       NOT NULL DEFAULT '{}',
    idempotency_key  text        UNIQUE NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS knowledge_doc_embedding ON knowledge_doc USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
