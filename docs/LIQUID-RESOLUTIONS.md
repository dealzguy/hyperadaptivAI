# Liquid Resolutions

This file records all resolved and open liquids — `TODO(liquid: ...)` markers in the codebase.

[DEV] NEVER resolve a liquid silently. Resolving a liquid requires: naming the evidence,
recording it here, and founder approval in the plan.

Last updated: 2026-06-12.

---

## infer-guard prefix set

**Status:** RESOLVED  
**Phase:** E  
**Date:** 2026-06-12  
**Recorded by:** Phase E (Coder-E, W7)

**What was open:** The `_guard_model_id()` function in `harness/shared/contracts/infer.py`
had a hardcoded Ollama-only allowlist: `("ollama/", "ollama_chat/")`. This blocked API-based
model IDs (e.g. `anthropic/claude-sonnet-4-6`) and was inconsistent with the settled
[PROD] constraint that all product inference is API-only via LiteLLM.

**Resolution:** Replaced the hardcoded tuple with `INFER_ALLOWED_PREFIXES` env var
(comma-separated string), defaulting to `("anthropic/",)`. The set is open: operators add
providers by setting the env var — no code change required.

**Evidence:**
- `harness/shared/contracts/infer.py` — `_guard_model_id()` and `_get_allowed_prefixes()`
- Phase E plan approved by founder 2026-06-12

**Founder approval:** Granted in Phase E plan (2026-06-12).

---

## embedding provider

**Status:** OPEN  
**Phase:** E  
**Date:** 2026-06-12  
**Recorded by:** Phase E (Coder-E, W7)

**Why open:** Anthropic has no embeddings API. `SITUATE` returns `knowledge: []` today
(no real corpus). Embedding provider selection requires a real corpus to evaluate the
right model and vector dimension; choosing in advance would be speculation.

**Liquid marker:** `harness/shared/inference/embed_provider.py` — `TODO(liquid: embedding provider)`

**What it gates:**
- Selecting an API embedding provider (e.g. OpenAI `text-embedding-3-small`, Cohere, etc.)
- Possibly changing `schema.sql vector(768)` dimension to match chosen model
- Wiring `query_knowledge` into the SITUATE step

**Blocked by:** A real corpus to select against. Unblock by: operator selects a provider
during commissioning; update `INFER_ALLOWED_PREFIXES`, update `embed_provider.py`, update
`schema.sql` vector dimension if needed, re-run bootstrap.

---

## commissioning task queue

**Status:** OPEN  
**Phase:** E  
**Date:** 2026-06-12  
**Recorded by:** Phase E (Coder-E, W7)

**Why open:** `harness/worker.py` line ~52 has `TODO(liquid: dedicated commissioning task
queue)`. Currently commissioning and operations workflows share the same Temporal task queue.
Separating them would allow independent resource allocation and worker scaling.

**Liquid marker:** `harness/worker.py` — `TODO(liquid: dedicated commissioning task queue)`

**What it gates:**
- Defining a `COMMISSIONING_TASK_QUEUE` constant separate from `OPERATIONS_TASK_QUEUE`
- Registering the commissioning workflow on a dedicated worker pool
- Updating `deploy/compose.yaml` to run a separate commissioning worker container

**Blocked by:** Phase E deploy hardening specification. Unblock by: founder decision on
whether the first real deployment warrants queue separation.

---

## Phase-A SDK pins

**Status:** OPEN (litellm)  
**Phase:** A  
**Date:** 2026-06-11  
**Recorded by:** Phase E (Coder-E, W7)  
**Updated:** 2026-06-12 (supervisor doc review — corrected versions from pyproject.toml)

**Resolution (partial):** Core SDK dependencies in `pyproject.toml`:
- `temporalio==1.9.0` — pinned
- `asyncpg==0.30.0` — pinned
- `litellm>=1.0,<2` — range, not a pin
- `httpx==0.25.2` — pinned

**Note on litellm:** litellm is currently specified as a range (`>=1.0,<2`), not an exact pin.
[DEV] The version-pin convention (CLAUDE.md) requires pinning before production deployment.
Resolve by: selecting and pinning the specific version used in the first live deployment
(e.g. `litellm==<version>`), then updating this entry to RESOLVED.

**Evidence:** `pyproject.toml` dependencies block.

**Founder approval:** Phase A plan approved pinned deps; litellm range requires a follow-up
pin decision before production deployment.

---

## construct golden-bundle model_policy

**Status:** OPEN  
**Phase:** E  
**Date:** 2026-06-12  
**Recorded by:** supervisor doc review (2026-06-12)

**Evidence:** `harness/commissioning/activities/construct.py` hardcodes
`anthropic/claude-sonnet-4-6` as Phase E initial-testing values in the
`_ARCHETYPE_TEMPLATES["lead_qualification"]["agent"]["model_policy"]` block.
Final form: `model_policy` read from operator-approved config rather than a
code template.

**Liquid marker:** `harness/commissioning/activities/construct.py` —
`TODO(liquid: construct golden-bundle model_policy)`

**What it gates:**
- Moving model IDs out of the archetype template table and into operator config
- Allowing different deployments to use different models without a code change
- Full adherence to Invariant 2 (model-agnostic above the inference line)

**Phase:** Phase E (acceptable for testing; resolve in Phase F)

---

## policy schema

**Status:** RESOLVED  
**Phase:** D  
**Date:** 2026-06-11  
**Recorded by:** Phase E (Coder-E, W7)

**Resolution:** Policy schema documented in `docs/CONFIG-BUNDLE-SPEC.md §policy`. Known
keys: `max_tokens` (int > 0), `temperature` (float [0, 2]); schema is open for append
(new keys added by config, no code change required — invariant 3).

**Evidence:** `docs/CONFIG-BUNDLE-SPEC.md` §policy section.

**Founder approval:** Granted in Phase D plan.
