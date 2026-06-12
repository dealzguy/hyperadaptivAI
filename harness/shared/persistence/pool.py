"""asyncpg connection-pool seam for the business Postgres.

Mirrors the secrets-provider singleton pattern: get_pool/set_pool/close_pool.

The pool MUST be created inside the worker's async main() — never at module
import time, and never bridged from a sync thread (asyncpg connections are
bound to the event loop that created them).
"""
from __future__ import annotations

import asyncio
import logging

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError(
            "asyncpg pool not initialised. "
            "Call create_pool() inside async main() before running the worker."
        )
    return _pool


def set_pool(pool: asyncpg.Pool | None) -> None:
    """Override the pool — for tests only."""
    global _pool
    _pool = pool


async def close_pool() -> None:
    """Gracefully close the pool. Call in the worker finally block."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


async def create_pool(dsn: str, min_size: int = 1, max_size: int = 25) -> asyncpg.Pool:
    """Create and register the pool with bounded retry.

    Thin: retry N then fatal — no jitter, no backoff curves (operator-error discipline).
    Enforces singleton: raises if called twice (double-init would silently leak first pool).
    """
    global _pool
    if _pool is not None:
        raise RuntimeError(
            "asyncpg pool already created. create_pool() must be called exactly once "
            "inside async main(). Use set_pool(None) + close_pool() in tests."
        )
    last_exc: Exception | None = None

    for attempt in range(1, 6):
        try:
            pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
            _pool = pool
            logger.info("asyncpg pool created (attempt %d/%d)", attempt, 5)
            return pool
        except Exception as exc:
            last_exc = exc
            logger.warning("Pool creation attempt %d/5 failed: %s", attempt, exc)
            if attempt < 5:
                await asyncio.sleep(2 ** attempt)

    raise RuntimeError(
        f"Failed to create asyncpg pool after 5 attempts. Last error: {last_exc}"
    ) from last_exc
