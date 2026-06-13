# Codebase Map — HyperadaptivAI version1

*Last updated: 2026-06-12. Purpose: prevent re-implementation of settled code. Read this before
touching any file. Each entry states what the file IS, why it exists, what invariant it enforces,
and the only legitimate reasons to change it.*

---

## How to use this map

A file is **settled** when its contract is locked by a CLAUDE.md invariant or a resolved liquid.
Editing it requires a plan + founder approval. A file is **extensible** when adding to it (without
changing existing behaviour) is the expected growth path. A file is **additive-only** when you
must add new files instead of editing the existing one.

---

## Entry point

| File | What it IS | Touch when |
|------|-----------|-----------|
| `harness/worker.py` | Single Temporal worker entry point. Registers ALL workflows and activities on `skeleton-queue`. Builds the asyncpg pool. Bootstrap is explicitly NOT run here (DDL-race prevention). | Adding a new workflow or activity to the worker's registration list. Never re-architect the pool or main() loop without a plan. |

**Read before touching:** `docs/AGENT-LOOP.md`, `docs/BLOCKS.md`.

---

## Shared substrate (`harness/shared/`) — zero mode assumptions

Files here know nothing about commissioning vs. operations. Any file that imports from here is safe;
no file in `shared/` may import from `harness/operations/` or `harness/commissioning/`.

### Contracts (seam definitions — edit only to extend the contract, never to break it)

| File | What it IS | Invariant |
|------|-----------|----------|
| `shared/contracts/infer.py` | The `infer()` contract + `_guard_model_id()` allowlist (open-set via `INFER_ALLOWED_PREFIXES`). Nothing above this line names a provider or model. | Invariant 2 (model-agnostic). Add providers by config; never hardcode a model ID here. |
| `shared/contracts/block.py` | `BlockSpec` dataclass — typed I/O, consequence class, compensation handler, idempotency key. Every block registered in the capability registry conforms to this. | Invariant 4 (additive). Add new fields; never remove. |
| `shared/contracts/intake.py` | `IntakePayload` — the one contract between any intake channel and the harness. | Invariant 7 (one contract per seam). Change only when the seam between intake and harness changes. |
| `shared/contracts/commission.py` | Typed I/O for commissioning workflow — interview/dissect/construct/validate/promote. | Locked. Change requires Phase D re-plan. |
| `shared/contracts/secrets.py` | Typed secrets contract (reads env vars). | Add new secrets by adding a field; never remove or rename existing fields. |
| `shared/contracts/memory.py` | Memory contract for episodic read/write. | Open for append; structure locked. |

### Capability registry (additive-only)

| File | What it IS | Touch when |
|------|-----------|-----------|
| `shared/capability/registry.py` | Central `BlockSpec` registry. `get(name)` → `BlockSpec`. New blocks register themselves on import. | Never edit existing entries. Add new blocks by importing the new block file in `worker.py`. The gate molecule reads consequence classes from here — don't change the key format. |

### CRM spine

| File | What it IS | Touch when |
|------|-----------|-----------|
| `shared/crm/primitives.py` | Five CRM primitives (entity, relationship, event, state, task) as typed dataclasses. | Adding a field to a primitive requires a schema migration + plan. Never remove fields. |
| `shared/crm/verbs.py` | Five verbs (create, relate, record, transition, assign). Each is a Temporal activity registered on `skeleton-queue`. Features are config on this spine — you never add a sixth verb without a plan. | Bug fixes only. Structural changes require a plan. |

**Read before touching:** `docs/12-initial-build-prompt.md` §5 (CRM spine), `docs/BLOCKS.md`.

### Inference

| File | What it IS | Touch when |
|------|-----------|-----------|
| `shared/inference/litellm_provider.py` | LiteLLM adapter. Calls `infer()` contract. Reads `INFER_API_BASE` (optional) and `ANTHROPIC_API_KEY` etc. from env. Does NOT name a model. | Adding a new provider quirk (new header, new response field). Never put a model name here. |
| `shared/inference/embed_provider.py` | Embedding stub. Returns `[]` today. **LIQUID OPEN** — do not wire until embedding provider is chosen. | Only when the embedding-provider liquid is resolved. See `docs/LIQUID-RESOLUTIONS.md`. |

### Persistence

| File | What it IS | Touch when |
|------|-----------|-----------|
| `shared/persistence/schema.sql` | Full Postgres schema — all tables, indexes, pgvector extension. | Adding a column or index. Never drop/rename a column without a migration plan. |
| `shared/persistence/bootstrap.py` | One-shot DDL runner. Creates schema + system entity (idempotent). Run as `python -m harness.shared.persistence.bootstrap` — never in the worker (DDL-race prevention). | When schema.sql changes. Never make it non-idempotent. |
| `shared/persistence/constants.py` | `SYSTEM_ENTITY_ID` — fixed UUID for harness-internal CRM rows. | Never change the UUID. It is referenced by existing DB rows. |
| `shared/persistence/dsn.py` | Builds asyncpg DSN from env vars (`DB_HOST`, `DB_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`). | Only to add a new connection parameter. |
| `shared/persistence/pool.py` | Asyncpg connection pool lifecycle (create/close). | Only for pool tuning (max_size). |

### Intake

| File | What it IS | Touch when |
|------|-----------|-----------|
| `shared/intake/webform.py` | Web-form intake adapter. Implements the `IntakePayload` contract. One of potentially many adapters. | Adding fields the web form collects. New channels → new adapter files, never edit this one. |
| `shared/molecules/intake.py` | Intake molecule — bridges adapter output to `LeadIntakeWorkflow` input. | Bug fixes only. |

### Memory

| File | What it IS | Touch when |
|------|-----------|-----------|
| `shared/memory/postgres_memory.py` | Episodic read/write via asyncpg. Reads/writes `event` rows tagged as memory episodes. | Bug fixes or adding a new memory operation. |

---

## Operations mode (`harness/operations/`) — runs forever

### The agent loop (SETTLED — versioned by `workflow.patched()`)

| File | What it IS | Touch when |
|------|-----------|-----------|
| `operations/workflows/agent_loop.py` | `AgentLoopWorkflow` — the durable four-step loop (SITUATE→DECIDE→ACT→RECORD). Signals: pause/resume/stop/resolve_gate. Queries: get_state/get_pending_gates. Gate versioned behind `patched("consequence-gate-v1")`. **Shadow mode is safety-critical: misreading it is a P0.** | Adding a new signal or query (additive). Changing loop behaviour requires `workflow.patched()` — read `docs/VERSIONING.md` first. Never change the pre-patch code path. |
| `operations/workflows/lead_intake.py` | `LeadIntakeWorkflow` — durable intake → agent-loop trigger. | Bug fixes only. |
| `operations/molecules/gate.py` | `gate_decision()` pure function. Deterministic truth table: shadow/gated/autonomous × reversible/compensable/irreversible × by_tool overrides → "auto"\|"approve". No I/O. | Only to add a new autonomy level (plan required — open enumeration only on the level set). Never change existing return values for existing inputs. |
| `operations/activities/situate.py` | SITUATE activity — builds agent context from CRM + memory. Checks flow-class pause state. Returns `SituateResult`. | Adding new context sources. Never remove existing fields from `SituateResult`. |
| `operations/activities/decide.py` | DECIDE activity — calls `infer()` to get the next action. Reads `INFER_STUB=1` for offline testing. | Bug fixes. Model ID comes from input, never hardcoded here. |
| `operations/activities/act.py` | ACT activity — dispatches to capability registry block by `action_type`. Returns `ActResult`. | Bug fixes. New tool support → new block in registry, not editing this file. |
| `operations/activities/record.py` | RECORD activity — writes episodic row to `event` table. | Bug fixes. Never change the episodic row schema without a plan. |
| `operations/activities/budget.py` | Budget check activity — evaluates token + step limits + stall detection. Returns `BudgetResult`. | Adding a new stop condition. Never change existing conditions without verifying all tests pass. |

**Read before touching:** `docs/AGENT-LOOP.md`, `docs/GATE.md`, `docs/VERSIONING.md`.

### Operator CLI

| File | What it IS | Touch when |
|------|-----------|-----------|
| `operations/operator_cli.py` | CLI for human operators. Commands: `list-gates`, `show-gate`, `approve`, `reject`, `edit`, `pause`, `resume`, `pause-flow`, `resume-flow`, `digest`. Connects to Temporal + asyncpg. `TEMPORAL_HOST`, `DB_PORT`, `POSTGRES_USER`, `POSTGRES_DB` from env. **Always `set -a && source secrets.env && set +a`** before running — plain `source` without `set -a` creates shell vars Python can't read. | Adding a new CLI command (additive). Never change existing command signatures or output format without updating `docs/GATE.md`. |

**Read before touching:** `docs/GATE.md` (signal protocol, positional args).

---

## Commissioning mode (`harness/commissioning/`) — runs once per business

| File | What it IS | Touch when |
|------|-----------|-----------|
| `commissioning/workflows/commission.py` | `CommissioningWorkflow` — interview→dissect→construct→validate→promote. Human approval gate on promote. | Bug fixes. Structural changes require a plan. |
| `commissioning/activities/interview.py` | Elicits raw operator intent via `infer()`. | Bug fixes. |
| `commissioning/activities/dissect.py` | Structures raw intent into typed archetype data. | Bug fixes. |
| `commissioning/activities/construct.py` | Builds the config bundle (agent spec, gates, model_policy). **LIQUID OPEN**: golden-bundle model_policy is hardcoded for Phase E testing — resolve before Phase F. | Only to fix the liquid. See `docs/LIQUID-RESOLUTIONS.md`. |
| `commissioning/activities/validate.py` | Schema-validates the bundle before promote. | Adding new validation rules. Never relax existing rules. |
| `commissioning/activities/promote.py` | Writes promoted bundle to persistence. One human click always (no-auto-promote invariant). | Bug fixes only. |

**Read before touching:** `docs/12-initial-build-prompt.md` §7, `docs/VALIDATION.md`.

---

## Deployment (`deploy/`)

| File | What it IS | Touch when |
|------|-----------|-----------|
| `deploy/compose.yaml` | Podman compose bundle — temporal, postgres-temporal, postgres-harness, harness-worker. Ollama service was removed in Phase E. | Adding a new service. Never co-mingle Temporal postgres and harness postgres. |
| `deploy/secrets/secrets.env` | **GITIGNORED**. Real API keys + DB creds. Never commit. Created manually on each host. | Rotating keys or adding a new provider. |
| `config/bundle-v0/` | Seed config bundle for testing. `lead-qualifier-v0.json` is the canonical first agent spec. | Testing only. Production bundles are promoted by commissioning workflow. |

---

## Config (`config/`)

| File | What it IS | Touch when |
|------|-----------|-----------|
| `config/bundle-v0/agents/lead-qualifier-v0.json` | Canonical test agent spec. `autonomy_level: gated`, consequence gates configured, `model_policy` set to Sonnet for Phase E testing. | Testing config changes. Never promote this bundle to production — it's for dev/smoke tests only. |

---

## Key cross-cutting rules (anti-overwrite checklist)

Before editing any file, check:

1. **Is it behind a `workflow.patched()`?** (`agent_loop.py`) — you must add a new patch, never change the patched path.
2. **Is it a contract seam?** (`contracts/`, `crm/verbs.py`, `crm/primitives.py`) — additive only; breaking changes require a plan.
3. **Does it touch the determinism boundary?** (anything in `operations/workflows/`) — no I/O, no clocks, no randomness; violations silently corrupt replay.
4. **Is there a liquid on it?** (`embed_provider.py`, `construct.py`) — resolve the liquid first; see `docs/LIQUID-RESOLUTIONS.md`.
5. **Does it register in the capability registry?** (`shared/capability/registry.py`) — never edit existing entries; add by importing a new block.
6. **Is it the bootstrap?** (`persistence/bootstrap.py`, `persistence/constants.py`) — `SYSTEM_ENTITY_ID` never changes; bootstrap is idempotent by contract, don't break that.

---

## What does NOT have a file here (intentionally deferred)

| Gap | Why deferred | When to build |
|-----|-------------|--------------|
| `SupervisorWorkflow` | Seam exists (W6), not built. Second deployment triggers it. | Phase F (second-instance rule). |
| Multi-channel intake adapters | Only webform today. New channels → new adapter file. | When a second channel is needed. |
| Dedicated commissioning task queue | Liquid open. See `docs/LIQUID-RESOLUTIONS.md`. | Phase E deploy hardening or Phase F. |
| Embedding pipeline | Liquid open (no real corpus yet). | When embedding provider resolved. |
| `TAXONOMY-v1.md` | Needs real corpus from first operator. | Phase E completion (operator engagement). |
