# Memory — Implementation Reference

Phase C. Last updated: 2026-06-11.

---

## Overview

The system has four memory faces. Each face has a distinct access pattern, storage
location, and retention policy. They are composed — not unified — so the taxonomy
can grow per corpus without a global schema migration.

| Face | Table | Access | Retention |
|------|-------|--------|-----------|
| Structured (CRM) | `entity`, `relationship`, `event`, `state`, `task` | Phase B verbs | Permanent |
| Episodic | `agent_episodic` | append + bounded read | Permanent (append-only) |
| Directive | `agent_directive` | single-row upsert | Last-write-wins |
| Knowledge | `knowledge_doc` | ingest + vector search | Permanent |

`TODO(liquid: memory taxonomy v1 — first real corpus determines retention/eviction
policy per face. See Doc 13 §Phase E.)`

---

## Structured Memory (CRM) — Phase B

Five primitives: `entity`, `relationship`, `event`, `state`, `task`.
Five verbs: `create_entity`, `relate`, `record_event`, `transition_state`, `assign_task`.

Implemented in `harness/shared/crm/verbs.py` and `harness/shared/crm/primitives.py`.
Not repeated here — see Phase B documentation.

---

## Episodic Memory — `agent_episodic`

### Schema

```sql
CREATE TABLE IF NOT EXISTS agent_episodic (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         text        NOT NULL,
    run_id           text        NOT NULL,     -- stores workflow_id (stable across retries)
    step             int         NOT NULL,
    action_type      text        NOT NULL,
    action_payload   jsonb       NOT NULL DEFAULT '{}',
    outcome_payload  jsonb       NOT NULL DEFAULT '{}',
    model_id         text        NOT NULL DEFAULT '',
    token_count      int         NOT NULL DEFAULT 0,
    entity_key       text        NOT NULL DEFAULT '',
    idempotency_key  text        NOT NULL UNIQUE,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_episodic_lookup
    ON agent_episodic (agent_id, run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS agent_episodic_entity
    ON agent_episodic (agent_id, entity_key, created_at DESC);
```

Note: `run_id` stores the Temporal `workflow_id` (stable across replays and retries).
It is named `run_id` for historical reasons — treat it as `workflow_id` in queries.

### Access Methods (`PostgresMemoryProvider`)

**`write_episodic(WriteEpisodicInput) → WriteEpisodicOutput`**
- INSERT with all columns including `entity_key`. ON CONFLICT(idempotency_key) DO NOTHING.
- Re-SELECT on conflict to return the existing row's `id`.
- `created=True` on insert, `False` on conflict.

**`read_episodic(ReadEpisodicInput) → ReadEpisodicOutput`**
- Filters by `agent_id` (required), optional `entity_key`, optional `run_id`.
- Returns up to `limit` records, newest first.
- Used in `situate_activity` with `limit=5` (configurable via `retrieval_budget` in agent config).

### Idempotency

Every write is keyed by `idempotency_key`, which the workflow derives deterministically:
```python
f"{workflow_id}:{step}:episodic"
```
Killing and restarting the worker between ACT and RECORD will replay the RECORD activity
with the same key → ON CONFLICT → no duplicate row.

---

## Directive Memory — `agent_directive`

### Schema

```sql
CREATE TABLE IF NOT EXISTS agent_directive (
    agent_id      text        PRIMARY KEY,
    priority_text text        NOT NULL DEFAULT '',
    attributes    jsonb       NOT NULL DEFAULT '{}',
    updated_at    timestamptz NOT NULL DEFAULT now()
);
```

One row per `agent_id`. Semantics: last-write-wins operator override.

### Access Methods

**`read_directive(ReadDirectiveInput) → ReadDirectiveOutput`**
- Returns `found=False` (empty `priority_text`, empty `attributes`) when no row exists.
- No exception on missing row.

**`write_directive(WriteDirectiveInput) → WriteDirectiveOutput`**
- INSERT ... ON CONFLICT (agent_id) DO UPDATE SET priority_text, attributes, updated_at=now().
- `updated=True` on upsert (always, since updated_at changes).

### Correction Discipline

To inject a mid-run correction into a running agent:
1. Signal `pause_instance()` to the workflow.
2. Call `write_directive` with the new `priority_text`.
3. Signal `resume_instance()`.

At the top of the next SITUATE step, `read_directive` will return the updated directive,
which is then included in the system/context messages for the DECIDE step.

---

## Knowledge Memory — `knowledge_doc`

### Schema

```sql
CREATE TABLE IF NOT EXISTS knowledge_doc (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace       text        NOT NULL,
    content         text        NOT NULL,
    embedding       vector(768) NOT NULL,
    metadata        jsonb       NOT NULL DEFAULT '{}',
    idempotency_key text        NOT NULL UNIQUE,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS knowledge_doc_ns_vec
    ON knowledge_doc USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

**Embedding model:** `nomic-embed-text` via Ollama (768 dimensions, cosine similarity).
The model ID is configured in the config bundle — `embed_provider.py` reads it from the
`EMBED_MODEL_ID` environment variable (default: `ollama/nomic-embed-text`).

**ivfflat caveat:** the index performs worse than a sequential scan below ~390 rows.
After bulk-loading knowledge docs, run `ANALYZE knowledge_doc;` to update planner
statistics. The bootstrap script does NOT run this — it is meaningless on an empty table.

### Access Methods

**`ingest_knowledge(IngestKnowledgeInput) → IngestKnowledgeOutput`**
- Calls `embed([content])` → vector of 768 floats.
- Serializes as `"[f1,f2,...]"` string literal cast `::vector` — no pgvector-python dependency.
- INSERT ... ON CONFLICT(idempotency_key) DO NOTHING.

**`query_knowledge(QueryKnowledgeInput) → QueryKnowledgeOutput`**
- Embeds `query_text` with the same model.
- `SELECT content, metadata, embedding <=> $1::vector AS distance FROM knowledge_doc WHERE namespace=$2 ORDER BY distance LIMIT $3`
- Returns `KnowledgeHit` list sorted nearest-first (cosine distance).

### Phase C Status

`query_knowledge` is implemented but NOT called by `AgentLoopWorkflow` in Phase C.
`context_dict["knowledge"]` is always `[]`. The ingestion path is available for pre-loading
reference data. The agent loop will wire retrieval in Phase D once there is real content
to retrieve.

---

## `PostgresMemoryProvider`

All four non-CRM faces are accessed through a single provider class:

```
harness/shared/memory/postgres_memory.py — PostgresMemoryProvider(pool: asyncpg.Pool)
```

Methods: `write_episodic`, `read_episodic`, `read_directive`, `write_directive`,
`ingest_knowledge`, `query_knowledge`.

The provider is instantiated inside each activity (not at module level) to avoid
pool lifecycle issues. Activities obtain the pool via `get_pool()` from
`harness.shared.persistence.pool`.

---

## Contract Dataclasses

All memory I/O types are defined in `harness/shared/contracts/memory.py` as plain
`@dataclass` types — no asyncpg, no litellm, no I/O. Safe to import inside the
Temporal workflow sandbox if needed for type annotations.
