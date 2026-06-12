"""DSN assembly for the business Postgres.

Two-DB fail-fast guard: asserts the assembled DSN targets postgres-business,
never postgres-temporal. Fail-fast is the only enforcement layer — there is
no compile-time barrier, so making this check loud and early is critical.
Never logs the password or full DSN.
"""
from __future__ import annotations

import logging
import os

from harness.shared.contracts.secrets import get_secret

logger = logging.getLogger(__name__)

_TEMPORAL_DB_HOST = "postgres-temporal"
_TEMPORAL_DB_NAME = "temporal"


def build_dsn() -> str:
    """Assemble the business-Postgres DSN.

    Reads POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB from the secrets
    provider; DB_HOST and DB_PORT from plain env (config, not secret).

    Raises RuntimeError if the target looks like the Temporal database.
    """
    user = get_secret("POSTGRES_USER")
    password = get_secret("POSTGRES_PASSWORD")
    db = get_secret("POSTGRES_DB")
    host = os.environ.get("DB_HOST", "postgres-business")
    port = os.environ.get("DB_PORT", "5432")

    if host == _TEMPORAL_DB_HOST:
        raise RuntimeError(
            f"DB_HOST={host!r} points at postgres-temporal — "
            "the business DB must never co-mingle with Temporal's event store "
            "(two-Postgres hard rule, CLAUDE.md + Doc 11)."
        )
    if db == _TEMPORAL_DB_NAME:
        raise RuntimeError(
            f"POSTGRES_DB={db!r} is the Temporal database name — "
            "use a dedicated business database."
        )

    # Log host+db only; never log password or full DSN.
    logger.info("Building DSN for host=%s db=%s", host, db)
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"
