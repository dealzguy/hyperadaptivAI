# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HyperadaptivAI is a Temporal-based distributed system for adaptive AI agents with durable execution guarantees. The project is organized into numbered phases — **no phase may begin implementation until its plan is reviewed and approved**.

## Planned Stack

| Component | Technology |
|-----------|-----------|
| Workflow orchestration | Temporal (Python SDK) |
| Persistence | PostgreSQL + pgvector |
| Inference | Ollama (local LLM execution) |
| LLM gateway | LiteLLM |
| Container runtime | Podman (compose for dev; Quadlet stays liquid until Phase B) |
| Language | Python |

## Phase-Based Workflow

Always **enter plan mode before Phase A work** (`claude --permission-mode plan` or Shift+Tab twice until footer reads "plan mode"). Submit the contents of `claude-code-kickoff-prompt.md` as the first message.

Reference documents live under `docs/`:
- `docs/08-software-licensing-reference.md` — license constraints (MIT/Apache-2.0 preferred; flag anything else)
- `docs/11-stack-architecture.md` — technical stack decisions
- `docs/12-initial-build-prompt.md` — Phase A build specification (read in full before planning)
- `docs/13-build-roadmap.md` — phase gate criteria

## Key Constraints

- **Phase A contains no business logic** — infrastructure and plumbing only.
- **No agent code and no real model calls in Phase A** — only a smoke test through the infer contract stub.
- **Every dependency choice must cite its license tier** per `docs/08`.
- **Temporal's Postgres and the business Postgres are separate instances.**
- Dependency version choices belong in the plan; do not resolve "liquid" (open) decisions without flagging them first.
