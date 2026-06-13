# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HyperadaptivAI is a Temporal-based distributed system for adaptive AI agents with durable execution guarantees. The project is organized into numbered phases — **no phase may begin implementation until its plan is reviewed and approved**.

## Current phase

Phase E — buildable machinery complete (smoke-tested 2026-06-12); live operator deployment pending (exit gate requires real operator engagement). See `docs/13-build-roadmap.md` §Phase E for exit gates.

## Planned Stack

| Component | Technology |
|-----------|-----------|
| Workflow orchestration | Temporal (Python SDK) |
| Persistence | PostgreSQL + pgvector |
| Inference | External API provider (no local inference; no GPU required) |
| LLM gateway | LiteLLM (capability-addressed routing to the configured API provider) |
| Container runtime | Podman (compose for dev; Quadlet stays liquid until Phase B) |
| Language | Python |

## Phase-Based Workflow

Always **enter plan mode before Phase A work** (`claude --permission-mode plan` or Shift+Tab twice until footer reads "plan mode"). Submit the contents of `claude-code-kickoff-prompt.md` as the first message.

Reference documents live under `docs/`:
- `docs/CODEBASE-MAP.md` — **read this first in any new session** — every file's purpose, what to touch vs. not, anti-overwrite checklist
- `docs/13-build-roadmap.md` — phase gate criteria and current phase status
- `docs/ALPHA-DEPLOYMENT.md` — VPS dev-server deployment: topology, access, restart runbook, open items
- `docs/08-software-licensing-reference.md` — license constraints (MIT/Apache-2.0 preferred; flag anything else)
- `docs/11-stack-architecture.md` — technical stack decisions
- `docs/12-initial-build-prompt.md` — Phase A build specification (read in full before planning)
- `docs/LIQUID-RESOLUTIONS.md` — open and resolved decisions; resolve none silently
- `docs/GATE.md` — consequence gate design, signal protocol, operator CLI args
- `docs/VERSIONING.md` — Temporal patched() discipline; read before touching agent_loop.py
- `docs/BLOCKS.md` — capability registry; add new blocks here when registering activities

## Key Constraints

- [DEV] **Phase A contains no business logic** — infrastructure and plumbing only.
- [DEV] **No agent code and no real model calls in Phase A** — only a smoke test through the infer contract stub.
- [DEV] **Every dependency choice must cite its license tier** per `docs/08`.
- [PROD] **Temporal's Postgres and the business Postgres are separate instances.**
- [DEV] Dependency version choices belong in the plan; do not resolve "liquid" (open) decisions without flagging them first.

## Constraint tagging — the standing rule

Any reference to a principle or constraint MUST be prefixed with its category tag — [DEV] (development process / operating under now) or [PROD] (end product / building toward). Genuinely-dual slogans must be split into their [DEV] and [PROD] parts before use.

The taxonomy lives in `docs/PRINCIPLES.md` (version1 repo) — it is the source of truth for which tag a principle carries and for how known bundled slogans split. Key consequence: the dev toolchain (Claude / Fable / Sonnet / Claude Code) is [DEV] — never shipped, never run at product runtime, and exempt from the Doc 8 license rule, the inference-routing rule (all runtime LLM calls via the infer contract to a configured API provider), and the model-agnostic invariant, which are [PROD] rules.
