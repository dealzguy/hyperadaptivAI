"""PostgresMemoryProvider — asyncpg-backed implementation of the four memory faces.

Mirrors the pattern in harness.shared.crm.verbs:
  - asyncpg only here (never in contracts, molecules, or workflows)
  - INSERT … ON CONFLICT DO NOTHING RETURNING id, re-SELECT on conflict
  - All writes are idempotency_key-keyed

Embedding is stored as a Postgres vector literal "[f1,f2,...]"::vector —
no pgvector-python dependency required.

This class is instantiated with an asyncpg Pool (from harness.shared.persistence.pool).
It is NOT a Temporal activity itself — activities in memory/activities.py call it.
"""
from __future__ import annotations

import json
import logging

import asyncpg

from harness.shared.contracts.memory import (
    EpisodicRecord,
    IngestKnowledgeInput,
    IngestKnowledgeOutput,
    KnowledgeHit,
    QueryKnowledgeInput,
    QueryKnowledgeOutput,
    ReadDirectiveInput,
    ReadDirectiveOutput,
    ReadEpisodicInput,
    ReadEpisodicOutput,
    WriteDirectiveInput,
    WriteDirectiveOutput,
    WriteEpisodicInput,
    WriteEpisodicOutput,
)
from harness.shared.inference.embed_provider import DEFAULT_EMBED_MODEL, embed

logger = logging.getLogger(__name__)


def _vec_literal(vec: list[float]) -> str:
    """Serialize a float list to a Postgres vector literal: "[f1,f2,...]"."""
    return "[" + ",".join(map(str, vec)) + "]"


class PostgresMemoryProvider:
    """asyncpg-backed four-face memory provider.

    Constructor:
        pool — asyncpg.Pool created by harness.shared.persistence.pool.create_pool()
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _insert_or_get(
        self,
        conn: asyncpg.Connection,
        table: str,
        insert_sql: str,
        insert_args: list,
        key: str,
    ) -> tuple[str, bool]:
        """INSERT … ON CONFLICT DO NOTHING RETURNING id.

        Returns (id_str, created_bool).
        On conflict re-SELECTs by idempotency_key.
        """
        row = await conn.fetchrow(insert_sql, *insert_args)
        if row is not None:
            return str(row["id"]), True
        existing = await conn.fetchrow(
            f"SELECT id FROM {table} WHERE idempotency_key = $1", key
        )
        if existing is None:
            raise RuntimeError(
                f"INSERT on {table} returned nothing and SELECT found nothing "
                f"for idempotency_key={key!r}. This should not happen."
            )
        return str(existing["id"]), False

    # ── write_episodic ────────────────────────────────────────────────────────

    async def write_episodic(self, payload: WriteEpisodicInput) -> WriteEpisodicOutput:
        async with self._pool.acquire() as conn:
            row_id, created = await self._insert_or_get(
                conn,
                "agent_episodic",
                """
                INSERT INTO agent_episodic
                    (agent_id, run_id, step, action_type, action_payload,
                     outcome_payload, model_id, token_count, entity_key, idempotency_key)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING id
                """,
                [
                    payload.agent_id,
                    payload.run_id,
                    payload.step,
                    payload.action_type,
                    json.dumps(payload.action_payload),
                    json.dumps(payload.outcome_payload),
                    payload.model_id,
                    payload.token_count,
                    payload.entity_key,
                    payload.idempotency_key,
                ],
                payload.idempotency_key,
            )
        logger.info(
            "write_episodic agent=%s step=%d key=%s id=%s created=%s",
            payload.agent_id, payload.step, payload.idempotency_key, row_id, created,
        )
        return WriteEpisodicOutput(
            id=row_id,
            idempotency_key=payload.idempotency_key,
            created=created,
        )

    # ── read_episodic ─────────────────────────────────────────────────────────

    async def read_episodic(self, payload: ReadEpisodicInput) -> ReadEpisodicOutput:
        """Read episodic records, newest first.

        Filters applied in order of specificity:
          - agent_id  always required
          - entity_key if non-empty
          - run_id    if non-empty
        """
        conditions = ["agent_id = $1"]
        args: list = [payload.agent_id]
        param = 2

        if payload.entity_key:
            conditions.append(f"entity_key = ${param}")
            args.append(payload.entity_key)
            param += 1

        if payload.run_id:
            conditions.append(f"run_id = ${param}")
            args.append(payload.run_id)
            param += 1

        where = " AND ".join(conditions)
        args.append(payload.limit)

        sql = f"""
            SELECT step, action_type, action_payload, outcome_payload, created_at
            FROM agent_episodic
            WHERE {where}
            ORDER BY created_at DESC, step DESC
            LIMIT ${param}
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)

        records = [
            EpisodicRecord(
                step=r["step"],
                action_type=r["action_type"],
                action_payload=r["action_payload"] if isinstance(r["action_payload"], dict) else json.loads(r["action_payload"]),
                outcome_payload=r["outcome_payload"] if isinstance(r["outcome_payload"], dict) else json.loads(r["outcome_payload"]),
                created_at=r["created_at"].isoformat(),
            )
            for r in rows
        ]
        return ReadEpisodicOutput(records=records)

    # ── read_directive ────────────────────────────────────────────────────────

    async def read_directive(self, payload: ReadDirectiveInput) -> ReadDirectiveOutput:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT agent_id, priority_text, attributes
                FROM agent_directive
                WHERE agent_id = $1
                """,
                payload.agent_id,
            )
        if row is None:
            return ReadDirectiveOutput(
                agent_id=payload.agent_id,
                priority_text="",
                attributes={},
                found=False,
            )
        attrs = row["attributes"] if isinstance(row["attributes"], dict) else json.loads(row["attributes"])
        return ReadDirectiveOutput(
            agent_id=row["agent_id"],
            priority_text=row["priority_text"],
            attributes=attrs,
            found=True,
        )

    # ── write_directive ───────────────────────────────────────────────────────

    async def write_directive(self, payload: WriteDirectiveInput) -> WriteDirectiveOutput:
        """Upsert directive. Last-write-wins on conflict (agent_id is unique)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO agent_directive (agent_id, priority_text, attributes, idempotency_key)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (agent_id) DO UPDATE
                    SET priority_text  = EXCLUDED.priority_text,
                        attributes     = EXCLUDED.attributes,
                        idempotency_key = EXCLUDED.idempotency_key,
                        updated_at     = now()
                RETURNING agent_id, (xmax = 0) AS inserted
                """,
                payload.agent_id,
                payload.priority_text,
                json.dumps(payload.attributes),
                payload.idempotency_key,
            )
        updated = row is not None
        logger.info(
            "write_directive agent=%s key=%s updated=%s",
            payload.agent_id, payload.idempotency_key, updated,
        )
        return WriteDirectiveOutput(agent_id=payload.agent_id, updated=updated)

    # ── ingest_knowledge ──────────────────────────────────────────────────────

    async def ingest_knowledge(self, payload: IngestKnowledgeInput) -> IngestKnowledgeOutput:
        """Embed content and INSERT into knowledge_doc.

        Embedding model: payload.model_id if non-empty, else DEFAULT_EMBED_MODEL.
        Embedding stored as Postgres vector literal — no pgvector-python dependency.
        """
        model_id = payload.model_id if payload.model_id else DEFAULT_EMBED_MODEL
        vecs = await embed([payload.content], model_id=model_id)
        vec_lit = _vec_literal(vecs[0])

        async with self._pool.acquire() as conn:
            row_id, created = await self._insert_or_get(
                conn,
                "knowledge_doc",
                """
                INSERT INTO knowledge_doc (namespace, content, embedding, metadata, idempotency_key)
                VALUES ($1, $2, $3::vector, $4, $5)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING id
                """,
                [
                    payload.namespace,
                    payload.content,
                    vec_lit,
                    json.dumps(payload.metadata),
                    payload.idempotency_key,
                ],
                payload.idempotency_key,
            )
        logger.info(
            "ingest_knowledge ns=%s key=%s id=%s created=%s",
            payload.namespace, payload.idempotency_key, row_id, created,
        )
        return IngestKnowledgeOutput(
            id=row_id,
            idempotency_key=payload.idempotency_key,
            created=created,
        )

    # ── query_knowledge ───────────────────────────────────────────────────────

    async def query_knowledge(self, payload: QueryKnowledgeInput) -> QueryKnowledgeOutput:
        """Embed query_text then retrieve nearest neighbours via cosine distance."""
        model_id = payload.model_id if payload.model_id else DEFAULT_EMBED_MODEL
        vecs = await embed([payload.query_text], model_id=model_id)
        vec_lit = _vec_literal(vecs[0])

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT content, metadata, embedding <=> $1::vector AS distance
                FROM knowledge_doc
                WHERE namespace = $2
                ORDER BY distance
                LIMIT $3
                """,
                vec_lit,
                payload.namespace,
                payload.limit,
            )

        hits = [
            KnowledgeHit(
                content=r["content"],
                metadata=r["metadata"] if isinstance(r["metadata"], dict) else json.loads(r["metadata"]),
                distance=float(r["distance"]),
            )
            for r in rows
        ]
        return QueryKnowledgeOutput(hits=hits)
