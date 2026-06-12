# ENVIRONMENT.md — Phase A resolved liquids and environment facts

*Written at Phase A, per doc 13 §Phase A build documents. Records the two
`TODO(liquid: ...)` items explicitly assigned to repo-init by doc 12 §11.*

## Resolved liquids

### TODO(liquid: repo layout — founder specifies at repo init)

Resolved at Phase A. Proposed and approved at repo init.

```
version1/
├── CLAUDE.md                          standing law, constraints, conventions
├── docs/                              reference docs + build documents per phase
│   ├── 05-assets-and-offering.md
│   ├── 08-software-licensing-reference.md
│   ├── 11-stack-architecture.md
│   ├── 12-initial-build-prompt.md
│   ├── 13-build-roadmap.md
│   ├── operator-error.md
│   └── ENVIRONMENT.md                 ← this file
├── deploy/                            provisional compose deploy bundle
│   ├── compose.yaml                   4-pod bundle (Quadlet stays liquid until Phase E)
│   ├── config/                        non-secret config templates (mounted into harness pod)
│   └── secrets/                       gitignored secret values + template
├── harness/                           Python package — harness pod
│   ├── worker.py                      Temporal worker entry point
│   ├── shared/                        zero mode assumptions — shared substrate
│   │   └── contracts/                 inference + secrets contract seams
│   ├── workflows/
│   │   └── skeleton/                  Phase A walking skeleton
│   ├── operations/                    Phase C+ operations mode (placeholder)
│   └── commissioning/                 Phase D+ commissioning mode (placeholder)
├── Dockerfile.harness                 harness pod OCI image
├── pyproject.toml                     Python project + dependency pins
└── tests/                             test suite — unit + integration
```

The master distinction (commissioning vs. operations) is visible in the filesystem:
`harness/operations/` and `harness/commissioning/` are placeholders that expand
in Phases C and D respectively. The shared substrate (`harness/shared/`) carries
zero mode assumptions.

### TODO(liquid: SDK and dependency pins — founder specifies at repo init)

Resolved at Phase A. Proposed and approved at repo init.

| Component | Pin | License | Tier | Rationale |
|-----------|-----|---------|------|-----------|
| Python | 3.12 | PSF | Green | Stable; asyncio improvements; Temporal SDK 3.9+ |
| temporalio | 1.9.0 | MIT | Green | Latest stable 1.x; async-first Python SDK |
| pytest | 8.2.0 | MIT | Green | Dev dep; standard test runner |
| pytest-asyncio | 0.23.8 | MIT | Green | Dev dep; async test support |

Docker images:

| Service | Image | License | Tier | Rationale |
|---------|-------|---------|------|-----------|
| Business Postgres | pgvector/pgvector:pg16 | MIT/PostgreSQL | Green | pgvector built in; pg16 stable |
| Temporal Postgres | postgres:16.3 | PostgreSQL | Green | Temporal's own event store; kept separate |
| Temporal server | temporalio/auto-setup:1.27.2 | MIT | Green | Auto-inits DB schema; single-node dev |
| Temporal UI | temporalio/ui:2.31.2 | MIT | Green | Web UI for workflow inspection |
| Ollama | ollama/ollama:0.6.5 | MIT | Green | Inference pod; models pulled at deploy time |
| Harness base | python:3.12-slim | PSF | Green | Matches Python pin; slim keeps image small |

**Verification obligation:** Re-check all pins at integration time and on every upgrade
per doc 08 vetting workflow. License drift is real (n8n, Open WebUI precedent).

## Host assumptions

- OS: Ubuntu (hardened per doc 05 / doc 11)
- Container runtime: Podman (Apache 2.0 — green tier)
- GPU passthrough: TODO(liquid: rootless-vs-GPU resolved per host at Phase E)
- Manifest format: compose (provisional); TODO(liquid: Quadlet vs. compose — resolved by Phase E observation per doc 13)

## Phase B additions

### New dependencies (Phase B, resolved)

| Package | Pin | License | Tier | Notes |
|---------|-----|---------|------|-------|
| asyncpg | 0.30.0 | MIT | Green | Async Postgres driver; async activities only |
| hypothesis | >=6.100,<7 | MPL-2.0 | Yellow | Dev-only; unmodified; not redistributed; property tests only |

asyncpg: MIT license (not Apache-2.0 — both are green tier, constraint met).
Hypothesis: MPL-2.0 is yellow tier per Doc 08. Obligation ("publish modifications
to MPL files") does NOT apply — Hypothesis is unmodified, dev-only, and not
included in the distributed artifact. Pinned in `[project.optional-dependencies].dev`
only. Must be excluded from NOTICES/SBOM distribution entry.

### Schema bootstrap

Schema is applied once per fresh volume via the dedicated one-shot entrypoint:
```
python -m harness.shared.persistence.bootstrap
```
This is NOT run inside the worker hot path (avoids multi-worker DDL races; works
on already-initialised volumes where an initdb mount would silently no-op).

`TODO(liquid: schema migration tool — Alembic/Atlas/sqitch)` — bootstrap gives no
migration path. First real migration is Phase C+. Flagged, not chosen.

### Dev overlay

The dev overlay exposes `postgres-business` on `127.0.0.1:5433` for local testing
and bootstrap. Apply on top of canonical compose:
```
podman compose -f deploy/compose.yaml -f deploy/compose.dev.yaml up -d
```
Port exposure is NOT in `compose.yaml` — keeps the canonical compose production-clean.
`sslmode=disable` is acceptable for loopback dev.
`TODO(liquid: sslmode=require)` — when the business DB moves off-host (Phase E).

### Two-Postgres invariant

The `build_dsn()` function (`harness/shared/persistence/dsn.py`) contains a
fail-fast guard that asserts `DB_HOST != postgres-temporal` and `POSTGRES_DB != temporal`.
This is the only runtime enforcement of the two-DB hard rule. `DB_HOST=postgres-business`
is set in `deploy/compose.yaml` as a non-secret config env var.

## Remaining liquids (not resolved in Phase A or B)

See doc 13 for the full liquid map. Open liquids:
- Manifest format (compose is provisional; Quadlet resolved at Phase E)
- Pod packing and Supabase-under-Podman lean profile (Phase E, per host)
- Rootless vs. GPU passthrough (Phase E, per host)
- Monitoring stack (Phase E, by observation)
- Memory taxonomy (Phase C, from first real corpus)
- Agent internals (Phase C, first deployment)
- Schema migration tool — Alembic/Atlas/sqitch (Phase C+)
- Pydantic data converter + temporalio >= 1.11 (Phase C, with typed money/datetime DTOs)
- sslmode=require for business DB (Phase E, when off-host)
- Richer identity resolution (Phase E, first real corpus)
- compensation_handler field on Block + reversing-transition blocks (Phase C, first compensable block)

All resolved liquids are recorded here as they close, with their authorizing evidence.
