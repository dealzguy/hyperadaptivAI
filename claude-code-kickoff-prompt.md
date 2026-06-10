# Claude Code Kickoff — Phase A Planning Prompt

*Setup before pasting: create the project directory, drop CLAUDE.md at the repo root, and put Docs 8, 9/11, 12, and 13 in `docs/`. Start Claude Code in the directory and enter plan mode (press Shift+Tab twice until the footer reads plan mode, or launch with `claude --permission-mode plan`). Optional but recommended: connect the official Temporal MCP server so planning can consult Temporal's knowledge base directly. Then paste everything below the line as the first message.*

---

Read CLAUDE.md, then docs/12-initial-build-prompt.md in full, then docs/13-build-roadmap.md §Phase A, then skim docs/11-stack-architecture.md and docs/08-software-licensing-reference.md for constraints. Do not write any files yet — we are in plan mode and I want a reviewable plan for Phase A only.

Produce a Phase A implementation plan containing:

1. **Proposed repo layout** — full tree with one-line purpose per directory. This resolves a known liquid (`TODO(liquid: repo layout — founder specifies at repo init)`), so present it as a proposal for my approval, with alternatives where the choice is genuinely contested.
2. **Dependency pins** — exact versions proposed for Python, Temporal Python SDK, Temporal server, Postgres, pgvector, Ollama, LiteLLM, and Podman-side tooling, each with a one-line rationale and its license tier per Doc 8. Flag anything not plainly MIT/Apache-2.0.
3. **Deploy bundle skeleton** — the compose manifests (compose is provisional; Quadlet stays liquid per Doc 13) for the persistence, orchestration, inference, and minimal harness pods, showing how software/config/data separation is physically realized in mounts and volumes, and how Temporal's own Postgres stays separate from the business Postgres.
4. **Walking skeleton** — the hello-world durable workflow and single activity, plus the exact kill-the-worker test procedure proving exact resume.
5. **Exit-gate test plan** — how each clause of Doc 13's Phase A gate will be demonstrated, as runnable steps.
6. **Open questions** — anything ambiguous, anything where Doc 12/13 underspecifies, and any liquid you were tempted to resolve, listed instead of resolved.

Constraints reminder: nothing in this phase contains business logic; no agent, no model calls except a smoke test through the infer contract stub; every choice that touches a settled constraint cites it. Plan only — I will review, push back, and approve before any execution.
