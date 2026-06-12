"""Memory contract — typed I/O dataclasses for the four-face memory system.

Four faces:
  episodic   — append-only agent action/outcome log, keyed by agent_id + entity_key
  directive  — editable priority instructions, one row per agent_id (upsert)
  knowledge  — pgvector knowledge store, namespace-scoped semantic search
  (structured — Phase B CRM primitives; already in harness.shared.crm.primitives)

All dataclasses are JSON-native (stdlib only) — safe in the Temporal workflow
sandbox. No asyncpg, no litellm, no I/O here.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── write_episodic ────────────────────────────────────────────────────────────

@dataclass
class WriteEpisodicInput:
    agent_id: str
    run_id: str          # stores workflow_id — stable across retries/resets
    step: int
    action_type: str
    action_payload: dict
    outcome_payload: dict
    model_id: str
    token_count: int
    entity_key: str
    idempotency_key: str


@dataclass
class WriteEpisodicOutput:
    id: str
    idempotency_key: str
    created: bool


# ── read_episodic ─────────────────────────────────────────────────────────────

@dataclass
class EpisodicRecord:
    step: int
    action_type: str
    action_payload: dict
    outcome_payload: dict
    created_at: str      # ISO-8601 string — no datetime in JSON-native contract


@dataclass
class ReadEpisodicInput:
    agent_id: str
    entity_key: str = ""
    run_id: str = ""
    limit: int = 10


@dataclass
class ReadEpisodicOutput:
    records: list[EpisodicRecord] = field(default_factory=list)


# ── read_directive / write_directive ──────────────────────────────────────────

@dataclass
class ReadDirectiveInput:
    agent_id: str


@dataclass
class ReadDirectiveOutput:
    agent_id: str
    priority_text: str
    attributes: dict
    found: bool          # False when no directive row exists yet


@dataclass
class WriteDirectiveInput:
    agent_id: str
    priority_text: str
    attributes: dict
    idempotency_key: str


@dataclass
class WriteDirectiveOutput:
    agent_id: str
    updated: bool        # True on first insert, True on upsert overwrite


# ── ingest_knowledge / query_knowledge ────────────────────────────────────────

@dataclass
class IngestKnowledgeInput:
    namespace: str
    content: str
    metadata: dict
    idempotency_key: str
    model_id: str = ""   # "" → embed_provider DEFAULT_EMBED_MODEL


@dataclass
class IngestKnowledgeOutput:
    id: str
    idempotency_key: str
    created: bool


@dataclass
class QueryKnowledgeInput:
    namespace: str
    query_text: str
    limit: int = 5
    model_id: str = ""   # "" → embed_provider DEFAULT_EMBED_MODEL


@dataclass
class KnowledgeHit:
    content: str
    metadata: dict
    distance: float


@dataclass
class QueryKnowledgeOutput:
    hits: list[KnowledgeHit] = field(default_factory=list)
