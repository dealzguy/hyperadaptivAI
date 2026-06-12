# Document 13 — Build Roadmap: From the Initial Prompt to the Shippable Product

*This document maps the territory between Document 12 and a shippable, reusable product, as a sequence of build phases with exit gates, and names the build documents each phase produces. Its governing decision is where the design conversation stops and the build begins: **it stops here.** Document 12 was the last design artifact this medium should produce; everything that remains is either repository work (Claude Code's domain) or a liquid that only build evidence can specify. Writing further design documents now would be pre-building liquids — the operator-error applied to documentation itself. Accordingly, this roadmap names the documents each phase will produce, writes only the three handoff artifacts (this roadmap, CLAUDE.md, the kickoff prompt), and leaves every in-repo document to be written at its phase, from its phase's evidence. One prior offer is hereby relocated on the same grounds: the Stage 0 interview protocol, previously suggested as the next conversation artifact, is a Phase D in-repo document — it will be implemented as prompts, schemas, and fixtures in the repository, and designing it in chat would only create divergence.*

## The two endpoints, defined

**MVP — first buy-in.** One operator paying for the harness to do real work on their actual data: install, ingestion, one department, minimal operator surface, both correction disciplines exercised in production. This is the venture's own first-buy-in definition and maps exactly to the Phase E exit gate.

**Shippable reusable product.** Document 6's Phase 1 made real: a consistent, repeatable release; a defined maintenance motion that runs the same way for every member; the meta-model's generality *earned* by a second deployment in a second archetype; charter patron members signable against it. Maps to the Phase G exit gate.

## Build-order rationale, stated once

Three ordering decisions shape the sequence, each derived from the architecture rather than convenience:

**Deterministic before adaptive.** [DEV] The two-natures boundary is also a build order: the skeleton (blocks, CRM spine, durable workflows) must exist and pass tests before the nervous system (agent loop, memory) has anything to act through. An agent with no verified tools is a hazard; verified tools with no agent are a working scripted system.

**Operations before commissioning.** [DEV] In runtime order, commissioning precedes operations; in build order it inverts. Commissioning's output — the configuration bundle — is meaningless without a runtime that consumes it, and the factory is itself built from the substrate operations proves out. The bridge between them is built by hand first: **Phase C hand-authors the first configuration bundle** to drive the agent loop, and that hand-authored bundle becomes the golden target Phase D's construction stage must learn to emit. The spec for the factory's output is written by using the output before the factory exists.

**One phase, one plan-mode cycle.** [DEV] Each phase below is scoped to be one Claude Code planning conversation: enter plan mode, produce the phase plan against this roadmap's exit gate, approve, execute, run the gate. Phases are deliberately sized so a plan fits in one reviewable document.

---

## Phase A — Repo bootstrap & walking skeleton

**Objective.** A repository and a declarative deploy bundle that lays the substrate onto a prepared host, with one durable workflow proving the spine.

**Build.** Repo init with layout proposed in plan mode and approved by the founder (this resolves the `TODO(liquid: repo layout)` — at repo init, as Doc 12 specifies). Version pins: Python, Temporal Python SDK, Postgres, pgvector, Ollama. The deploy bundle skeleton: compose manifests (provisional; Quadlet-vs-compose stays liquid until first-deployment observation), pods for persistence (Postgres + pgvector), orchestration (Temporal + its own Postgres), inference (Ollama behind a stub of the infer contract), and a minimal harness pod. *(Historical record as built. Superseded 2026-06: API-only inference — the Ollama pin and inference pod are removed from the target bundle; infer routes via LiteLLM to a configured external API provider. See `docs/PRINCIPLES.md`.)* One hello-world durable workflow with one activity.

**Build documents (in-repo, written this phase).** `docs/ENVIRONMENT.md` — pins, layout, host assumptions, the resolved repo-init liquids with their evidence recorded. `deploy/README.md` — how the bundle lays down and verifies.

**Liquids resolved here.** Repo layout; SDK and dependency pins. **Liquids explicitly not resolved:** manifest format (compose is provisional), monitoring stack, pod packing.

**Exit gate.** [DEV] On a clean prepared host, the bundle lays down from declaration alone; the hello-world workflow runs; a worker killed mid-execution resumes exactly. Software, config, and data demonstrably live in separate places.

---

## Phase B — Capability layer & the CRM spine

**Objective.** The deterministic half complete: five primitives, five verbs as verified blocks, a tool catalog, and one intake channel — drivable by a scripted workflow with no agent anywhere.

**Build.** The five-primitive schema in the business Postgres (JSONB/config flexibility handles on the fixed spine). The five verbs as blocks meeting the full Doc 12 §8 schema: typed I/O, idempotency key, consequence class, golden and property tests, version pin. The tool catalog/registry with typed discovery. The normalized intake event contract and the web-form adapter. A scripted (non-agentic) Temporal workflow: intake event → Intake molecule → entity created → first task opened.

**Build documents.** `docs/BLOCKS.md` — the block schema instantiated, the catalog's registration rules, the additive rule as CI policy. `docs/INTAKE-CONTRACT.md` — the normalized event, the adapter interface, the open-set rule.

**Exit gate.** [DEV] Every block passes golden and property tests. The scripted workflow runs a fixture lead end to end, twice, idempotently. The closure check passes by hand for the molecules this phase touches.

---

## Phase C — The agent loop (operations mode)

**Objective.** The adaptive half: one department agent running situate → decide → act → record over the Phase B blocks, governed, budgeted, and pausable — driven by a **hand-authored configuration bundle**.

**Build.** The infer contract implemented over Ollama with LiteLLM capability-addressed routing and structured outputs. *(Historical record as built. Superseded 2026-06: API-only inference — the contract now routes via LiteLLM to a configured external API provider; no local Ollama.)* The agent loop as a Temporal workflow whose decide step is an inference activity choosing from the tool allowlist; LangGraph/LangMem inside activities, pinned, behind the decision and memory contracts. The memory contract minimally across all four faces: structured (exists from B), knowledge (one ingestion path into pgvector), episodic (every cycle writes act + outcome), directive (one editable priorities object). Budgets and containment: per-loop step and token budgets, stall detection, confidence-routed escalation. The gate as a Temporal signal; pause/park/resume at instance and flow-class scope. The hand-authored configuration bundle: one agent definition (Doc 12 §8 schema), one flow (lead-intake → first-follow-up), vocabulary stubs.

**Build documents.** `docs/AGENT-LOOP.md` — the loop, budgets, stall and escalation semantics as implemented. `docs/MEMORY.md` — the four-face contract as implemented; taxonomy explicitly marked `TODO(liquid: first real corpus)`. `config/bundle-v0/` — the hand-authored bundle, annotated, **promoted to golden target for Phase D**.

**Exit gate.** [DEV] Operations acceptance from Doc 12 §9 on a fixture lead: end-to-end traversal; kill-worker exact resume; instance pause lossless; flow-class pause parks all instances at safe boundaries; one correction recorded as episodic memory and retrieved in the next situate step; replay audit reads true.

---

## Phase D — The commissioning factory

**Objective.** The once-mode: interview → dissection → construction → validation → promote, built as a Temporal workflow with typed branch nodes, whose construction stage emits bundles matching the Phase C golden target.

**Build.** The commissioning workflow with typed branch points (archetype → switches → per-process parameters → rule sets). Stage 0: the interview protocol — agent prompts, the versioned context-frame schema, the consequence-taxonomy schema, the scenario-card schema, the frame read-back. Stage 1: dissection over a fixture corpus — primitive mappings, archetype/switch proposal, calculation rules with test vectors, provenance on every artifact. Stage 2: construction emitting the declarative configuration bundle. Stage 3: Tier 0 of the validation ladder (schema, simulation, exact vector reproduction, scenario cards), with Tier 1/2 implemented as conditional stages that record their own absence. Stage 4: promote as one click; probation policy wired to the consequence taxonomy.

**Build documents.** `docs/INTERVIEW-PROTOCOL.md` (the relocated Stage 0 artifact — prompts, schemas, traversal order). `docs/DISSECTION.md` — extraction targets, provenance format, vector lifting. `docs/CONFIG-BUNDLE-SPEC.md` — the bundle format, reverse-engineered from the Phase C golden bundle and now normative. `docs/VALIDATION.md` — the ladder as implemented, tier conditions, compensation policy.

**Exit gate.** [DEV] Commissioning acceptance from Doc 12 §9 against a fixture of the first operator's business class — including the discipline test: one wrong frame assumption deliberately injected at Stage 1, located by provenance, corrected by branch rollback, regenerated, re-certified. The emitted bundle drives the Phase C loop unmodified.

---

## Phase E — MVP: the first real deployment

**Status (2026-06-12).** Buildable machinery complete and smoke-tested: inference-API refactor (W0), consequence gate + workflow versioning (W1/W2), CRM spine persistence (W3), operator CLI (W4), flow-class pause (W5), docs/liquids (W7). Live operator deployment pending — exit gate requires real operator engagement (see below).

**Objective.** The first warm-network operator commissioned, deployed, in probation, paying. This phase is performed, not just built — and the performing is the evidence-harvest the whole liquid map has been waiting for.

**Build / perform.** Host prep on the operator's ground. Real commissioning: the actual interview, their actual corpus, their archetype (order/delivery, project/milestone, or policy/coverage — whichever contact closes first). Promote, probation with gates on. The minimal operator surface: queue, item viewer, approve/edit/send, pause, digest. Liquids resolved from observation and recorded with their evidence: memory taxonomy v1 from the real corpus; pod packing and the Supabase-under-Podman lean profile per this host; rootless-vs-GPU resolution; manifest format decision (Quadlet vs. compose, now observed); monitoring stack selection. Delegated-expiring authority exercised and visibly transferred at handover.

**Build documents.** `docs/DEPLOYMENT-RUNBOOK.md` — written *as the deployment happens*; per Doc 6, this documentation is the seed of the standardized product and the maintenance motion. `docs/LIQUID-RESOLUTIONS.md` — each resolved liquid, the evidence that resolved it, the date. `docs/TAXONOMY-v1.md` — the memory taxonomy grown from the first corpus, scoped honestly to one business class.

**Exit gate — this is the MVP.** [DEV] The operator is a paying charter-member candidate; real leads run the loop on their real data; both correction disciplines have been exercised in production (at least one pause-fix-record; rollback-regenerate exercised at commissioning); the probation ledger shows graduation movement; recurring revenue exists.

---

## Phase F — Second deployment & abstraction extraction

**Objective.** Generality earned, not claimed. The second operator, in a *different* archetype, commissioned measurably faster — and the second-instance rule finally fires.

**Build.** [DEV] Commission operator two. [DEV] Extract abstractions only where the second instance reveals real duplication: shared molecule refinements, the first cross-archetype switch behaviors, cross-department orchestration (when the second department genuinely arrives). [DEV] Automate the closure check as construction-time CI — its liquid trigger ("second deployment") has now fired. Begin the divergence ledger: what the meta-model absorbed cleanly versus what forced a new switch or archetype, because that ledger *is* the moat's appreciation record.

**Build documents.** `docs/ARCHETYPE-<second>.md` — the second archetype as built. `docs/CLOSURE-CI.md` — the automated check. `docs/DIVERGENCE-LEDGER.md` — fits, forces, and catalog growth per deployment.

**Exit gate.** [DEV] Second deployment live and paying; commissioning wall-clock and correction counts materially below deployment one; closure CI green; at least one abstraction extracted from observed (not anticipated) duplication.

---

## Phase G — Productization: the shippable release

**Objective.** A string of engagements becomes a product: the release is repeatable, the maintenance motion is defined, and the thing the co-op licenses from the IP company exists as an artifact.

**Build.** The versioned release channel for the maintained declarative bundle — current pinned images, model migrations, template/config updates — exercised end-to-end on both live deployments. The maintenance motion as runbook + automation: security currency, model migration drill (swap a model behind the infer contract on a live member with zero re-architecture — the brochure claim, demonstrated), template refresh. Self-serve-leaning onboarding for the third deployment. The deliberate naming pass on meta-model vocabulary (shell, molecules, switches, archetypes) *before* it fossilizes into member-facing IP. Packaging boundaries per Doc 8: open core cut cleanly from the proprietary harness; NOTICES and SBOM in CI; outbound EULA carve-outs verified.

**Build documents.** `docs/RELEASE.md` — versioning, channel, upgrade path, rollback. `docs/MAINTENANCE-MOTION.md` — the recurring motion as run for every member identically. `docs/ONBOARDING.md` — the third-deployment path with founder-hands minimized. A `CHANGELOG` discipline dating from the first tagged release.

**Exit gate — this is the shippable product.** [DEV] A third party of reasonable competence could deploy from the release artifacts without the founder's hands; an update ships to both live members through the channel without touching their data or config; the maintenance motion has run at least one full cycle including a model migration; the open-core/paid boundary survives a Doc 8 audit.

---

## Documents deliberately not written now

[DEV] Every in-repo document above is named with its phase and trigger, and none is written before its phase — the same rule Document 12 applies to code. In particular: no interview protocol before Phase D, no taxonomy before the first corpus, no maintenance motion before a deployment has been maintained, no second-archetype document before a second business. The roadmap commits the *existence and position* of each document; their internals are specified by the evidence of their phase. This is operator-error.md applied to the document series itself.

## Working agreement with Claude Code

[DEV] One phase per planning cycle: enter plan mode, point it at this roadmap's phase section and exit gate, iterate the plan until it is concrete about files, order, and tests, approve, execute, run the gate before the next phase opens. [DEV] CLAUDE.md (repo root) carries the standing law — settled constraints, invariants, conventions, non-goals — so every session starts already disciplined. [DEV] The acceptance tests in Doc 12 §9 are the spec of record; a phase is not done because its code exists, it is done because its gate passed.

*End of Document 13.*
