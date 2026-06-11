# ENVIRONMENT.md — Phase A

*Phase A build document per Doc 13.  Records the resolved repo-init liquids,
all dependency pins with license tiers, and host assumptions.  Every entry here
is point-in-time and must be re-verified at each upgrade.*

---

## Resolved liquids (Phase A)

Two liquids from Doc 12 §11 are resolved by the approved Phase A plan.

| Liquid | Resolution | Evidence |
|--------|-----------|----------|
| `TODO(liquid: repo layout — founder specifies at repo init)` | Layout described in the approved Phase A plan; implemented in this commit. See "Repo layout" below. | Plan approval, 2026-06-10 |
| `TODO(liquid: SDK and dependency pins)` | Pins listed in "Dependency pins" below. | Plan approval, 2026-06-10 |
| `TODO(liquid: Temporal Python SDK version)` | Resolved as part of SDK pins below. | Plan approval, 2026-06-10 |

---

## Repo layout

```
hyperadaptivai/
├── CLAUDE.md                     standing law
├── docs/                         reference documents + phase build docs
├── deploy/                       declarative deploy bundle (compose, manifests)
│   ├── compose.yaml              provisional dev compose (Quadlet liquid until Phase E)
│   ├── .env.example              secrets contract template (actual .env never committed)
│   ├── postgres/init.sql         pgvector extension init (CRM schema is Phase B)
│   └── temporal/dynamicconfig/   Temporal dynamic config
├── src/harness/                  Python harness source (the proprietary harness)
│   ├── contracts/                seam interfaces (infer, memory) — serve both modes
│   ├── substrate/                shared CRM layer — Phase B builds here
│   ├── operations/               Operations mode (runs forever)
│   │   ├── workflows/            Temporal workflows (deterministic)
│   │   └── activities/           Temporal activities (nondeterminism permitted)
│   ├── commissioning/            Commissioning mode (runs once) — Phase D builds here
│   └── worker.py                 Temporal worker entry point
├── tests/                        test suite
├── config/                       per-deployment configuration (Phase C: bundle-v0/)
├── Dockerfile                    harness image build
├── pyproject.toml                Python project + pinned deps
└── uv.lock                       committed lockfile
```

**Mode visibility:** `src/harness/operations/` vs. `src/harness/commissioning/`
makes the master distinction (Doc 12 §1) explicit in the filesystem.
`contracts/` and `substrate/` serve both modes with zero business assumptions.

---

## Dependency pins

Confirm each version at integration against the current releases.
Record confirmed versions in the table below.

| Component | Proposed pin | Confirmed pin | License | Doc 8 tier | Notes |
|-----------|-------------|---------------|---------|------------|-------|
| Python | 3.12.x | _confirm_ | PSF (MIT-equiv) | Green | 3.13 verify against temporalio before upgrading |
| `temporalio` (Python SDK) | `>=1.7.0,<2.0` | 1.28.0 (resolved by uv) | MIT | Green | Must pair with Temporal Server — see pairing note |
| Temporal Server | `temporalio/auto-setup:1.25.2` | _confirm at deploy_ | MIT | Green | SDK 1.28.0 verified against server; confirm auto-setup image tag at first `make up` |
| Temporal UI | `temporalio/ui:2.31.2` | _confirm at deploy_ | MIT | Green | Match server release |
| PostgreSQL (business DB) | `pgvector/pgvector:pg17` | _confirm_ | PostgreSQL License | Green | pg17 + pgvector 0.8.x bundled |
| PostgreSQL (Temporal DB) | `postgres:17-alpine` | _confirm_ | PostgreSQL License | Green | Temporal datastore; no pgvector |
| Ollama | `ollama/ollama:0.6.6` | _confirm_ | MIT | Green | Phase A: no model pulled |
| `pytest` | `>=8.0` | _from uv.lock_ | MIT | Green | |
| `pytest-asyncio` | `>=0.23` | _from uv.lock_ | Apache 2.0 | Green | |
| `pip-licenses` | `>=5.0` | _from uv.lock_ | MIT | Green | `make licenses` standing audit |
| `uv` (package manager) | latest stable | _confirm_ | MIT | Green | `uv.lock` committed |
| Podman (runtime) | system 4.7+ | _confirm_ | Apache 2.0 | Green | Not a Python dep; system-installed |
| `podman-compose` (dev deploy tool) | `>=1.2` via pip | _confirm_ | GPL-2.0 | Dev-only | CLI tool; never linked into harness; not distributed in product — "separate process" case per Doc 8 |
| Temporal CLI (host tool) | latest stable | _confirm_ | MIT | Green | Verification tool only (trigger/inspect workflows); not part of the bundle |

**SDK/server pairing note:** Temporal's Python SDK release notes specify the
minimum compatible server version.  At integration, confirm `temporalio 1.7.x`
and `auto-setup:1.25.2` are compatible; if not, adjust upward together and
record the confirmed pair here.

**Model weights:** Pulled at deploy time from Ollama registry; not packaged in
the image (Doc 8: pull-don't-redistribute).  Phase A pulls nothing.
Commercially-clean families for Phase C: Qwen 3.x (Apache 2.0), Gemma 4
(Apache 2.0), Phi-4 (MIT), DeepSeek V4 (MIT).

---

## Host assumptions

- Ubuntu 24.04 LTS (hardened per Doc 5 host-prep playbook; playbook is Phase B+)
- Podman 4.7+, rootless preferred
- `podman-compose` via pip (Podman's `podman compose` subcommand delegates to it)
- Temporal CLI on the host, for triggering/inspecting workflows during verification
- GPU passthrough: **liquid** — rootless-vs-GPU tension resolved per host in
  Phase E.  See `deploy/compose.yaml` GPU block (commented out).

---

## Open liquids inherited from Phase A (not resolved here)

See full ledger in the Phase A plan.  Key items:

- Manifest format (compose vs. Quadlet) — Phase E
- Supabase lean profile under Podman — Phase E
- Memory taxonomy — Phase E (first real corpus)
- Open WebUI branding decision — before interface pod built (Phase C/D)
- Config-table schema — Phase B
