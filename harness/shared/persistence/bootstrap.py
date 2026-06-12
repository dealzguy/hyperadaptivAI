"""One-shot schema bootstrap for the business Postgres.

Run ONCE before starting workers on a fresh volume:
    python -m harness.shared.persistence.bootstrap

Idempotent: schema.sql uses CREATE TABLE IF NOT EXISTS / CREATE EXTENSION IF NOT EXISTS.
NOT run inside the worker hot path — this avoids multi-worker DDL races, and works on
already-initialised volumes where an initdb mount would silently no-op.

TODO(liquid: schema migration tool — Alembic/Atlas/sqitch) — this bootstrap gives no
migration path; first real migration is Phase C+. Flagged, not chosen.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib

from harness.shared.persistence.dsn import build_dsn
from harness.shared.persistence.pool import close_pool, create_pool

logger = logging.getLogger(__name__)

_SCHEMA_SQL = pathlib.Path(__file__).parent / "schema.sql"


async def apply_schema(pool: object) -> None:
    """Execute schema.sql against the given pool. Idempotent."""
    sql = _SCHEMA_SQL.read_text()
    async with pool.acquire() as conn:
        await conn.execute(sql)
    logger.info("Schema applied from %s", _SCHEMA_SQL.name)


async def _main() -> None:
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s %(message)s")
    dsn = build_dsn()
    pool = await create_pool(dsn)
    try:
        await apply_schema(pool)
        logger.info("Bootstrap complete.")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(_main())
