# PRINCIPLES.md — HyperadaptivAI Constraint Taxonomy

This document is the source of truth for the `[DEV]` / `[PROD]` tag scheme. Taggers retagging
existing documents (CLAUDE.md files, docs/, memory) use this file as the authority. It defines
the taxonomy; it does not retag anything itself.

## The tag scheme

Every principle or constraint in this project belongs to exactly one of two categories:

- **`[DEV]`** — governs the **development process**: how we plan, build, test, and gate the work
  we are doing *right now*, during the build phases. These rules bind Claude Code, the founder,
  and the dev toolchain. They are never properties of the shipped artifact.
- **`[PROD]`** — defines the **end product**: what the built, shipped, running system must be or
  do. These rules bind the artifact — its code, configuration, deployment bundle, runtime
  behavior, and dependencies. They do not bind the toolchain that builds it.

The categories answer different questions. `[DEV]`: *are we building it correctly?* `[PROD]`:
*is the thing we built correct?* Mixing them is a category error that has caused planning
mistakes (e.g., applying product license rules to the dev toolchain, or applying dev
definition-of-done rituals as if they were runtime properties).

## The Inversion

The two categories optimize for **opposite** targets. This is not a contradiction — it is the
correct strategy: spend maximum intelligence once, at build time, to produce a system that needs
minimum intelligence forever, at run time.

| | `[DEV]` Build process | `[PROD]` End product |
|---|---|---|
| Optimizes for | **MAXIMUM capability** | **MINIMUM sufficient capability** |
| Models | Fable plans / reviews; Sonnet codes — frontier, proprietary, cloud | Cheapest/smallest API model that meets the quality bar per task; small-model-first with escalation |
| Determinism | Agents explore, reason, iterate freely | Deterministic everywhere a model is not strictly required; determinism boundary absolute |
| Licensing | Proprietary toolchain is fine — it is never shipped | MIT/Apache-2.0 (Doc 8 allow-list) only — it IS shipped |
| Locality | Cloud toolchain is fine | API inference via a configured external provider, behind the infer contract; no local model weights, no GPU required |
| Lifetime | Exists only during the build; leaves no trace in the artifact | Runs forever on member-controlled ground |

**The toolchain exemption (explicit).** Claude, Fable, Sonnet, and Claude Code build the system
but are **never shipped, never run at product runtime**, and are therefore **NOT subject to**:
the Doc 8 license rule, the inference-routing rule (all runtime LLM calls via the infer
contract), or the model-agnostic invariant. Those are
`[PROD]` rules; the toolchain lives entirely in `[DEV]`. Nothing in the delivered bundle —
code, config, images, models — depends on or names the dev toolchain.

## [DEV] Development-process principles (operating under right now)

Planning and phase discipline:

- [DEV] Enter plan mode before every phase and every structural change; the approved plan is the spec for execution.
- [DEV] No phase begins implementation until its plan is reviewed and approved by the founder.
- [DEV] One phase per planning cycle, scoped so the plan fits in one reviewable document.
- [DEV] A phase is done when its Doc 13 exit gate passes, not when its code exists.
- [DEV] The acceptance criteria in Doc 12 §9 are the spec of record for the gate tests.
- [DEV] Adversarially stress-test every plan (P0/P1/P2 lens) before presenting it.
- [DEV] Verify SDK and dependency facts against current sources before asserting them in a plan; never plan from memory of an API.
- [DEV] Do not re-litigate or "improve" settled constraints; when a request conflicts with project law, say so before doing it.
- [DEV] Prefer asking over assuming on anything touching settled constraints, liquids, or licensing.

Liquids and the operator-error discipline:

- [DEV] Commit only what evidence authorizes; scaffold thin on anything the first deployment must specify.
- [DEV] Mark deferred internals `TODO(liquid: <what specifies it>)`.
- [DEV] Never resolve a liquid silently: resolving one requires naming the evidence, recording it in `docs/LIQUID-RESOLUTIONS.md`, and founder approval in the plan.
- [DEV] Extract abstractions at the SECOND instance of a pattern, never the first; one occurrence is not a pattern.
- [DEV] Write each in-repo document at its phase, from its phase's evidence — never pre-build documentation.

Definition-of-done discipline (the process half of the block rule — see bundled slogans):

- [DEV] Write golden and property tests for a block before marking it done.
- [DEV] Pin the version of every dependency a block uses before marking it done.
- [DEV] Every dependency choice in a plan cites its license tier per Doc 8 (the citing is process; the allow-list itself is `[PROD]`).
- [DEV] Run the closure check by hand whenever the molecule catalog changes (CI automation is a liquid until the second deployment).
- [DEV] Follow the committed build order: deterministic before adaptive; operations before commissioning; the Phase C hand-authored bundle is the golden target for Phase D.

Dev environment and toolchain:

- [DEV] Our dev/test machine cannot run Docker, so all local container work uses Podman (the dev half of "Podman, not Docker" — see bundled slogans).
- [DEV] Use Fable (`claude-fable-5`) for planning, architecture, and adversarial review agents.
- [DEV] Use Sonnet (`claude-sonnet-4-6`) for coding, implementation, testing, and docs agents.
- [DEV] Never use Haiku for development tasks — it is too weak for this work; "minimum intelligence per task" is a `[PROD]` runtime principle, not a toolchain principle.
- [DEV] The dev toolchain (Claude / Fable / Sonnet / Claude Code) is exempt from the Doc 8 license rule, the inference-routing rule, and the model-agnostic invariant — it is never shipped and never runs at product runtime.

## [PROD] End-product principles (building toward)

The seven invariants (Doc 9/11; breaking one = stop and flag):

- [PROD] Invariant 1 — Config over code: business/moment variation is data, never a branch.
- [PROD] Invariant 2 — Model-agnostic above the inference line: nothing above the infer contract names a model.
- [PROD] Invariant 3 — No closed enumerations on anything that grows (stages, fields, channels, tools, archetypes, switches).
- [PROD] Invariant 4 — Capabilities are additive: new tools register in the catalog; existing workflows are never edited to admit them.
- [PROD] Invariant 5 — Determinism boundary absolute: no model calls, clocks, randomness, or I/O inside workflow code; all nondeterminism lives in activities.
- [PROD] Invariant 6 — Software, configuration, and data stay separate in the package: separate images, mounts, volumes — always.
- [PROD] Invariant 7 — One contract per seam, honoured on both sides, container seams included.

Architecture (settled constraints):

- [PROD] Two modes, one machine: commissioning runs once per business; operations runs forever.
- [PROD] Adaptation happens between instances via configuration and memory — never within an instance via mutation.
- [PROD] Structural change in operations is forbidden; it routes back through commissioning.
- [PROD] Temporal (MIT) is the durable spine of BOTH modes; commissioning is itself a Temporal workflow.
- [PROD] Workflow logic changes ship through Temporal versioning APIs; in-flight executions finish on the code they started with.
- [PROD] Supabase/Postgres + pgvector is the system of record and memory substrate; Temporal gets its OWN Postgres — two databases, two volumes, never co-mingled.
- [PROD] The product deploys on Podman (Quadlet-vs-compose is liquid until first-deployment observation); the deploy bundle is declarative (the product half of "Podman, not Docker" — see bundled slogans).
- [PROD] CRM = five primitives (entity, relationship, event, state, task) and five verbs (create, relate, record, transition, assign); features are config on this spine.
- [PROD] Inference only via the `infer(model_id, messages, tools, policy)` contract; nothing above the contract names a model or provider (Invariant 2).
- [PROD] LiteLLM provides capability-addressed routing to a configured external API provider; no local model weights are required.
- [PROD] Small-model-first: use the cheapest/smallest API model that meets the quality bar for each task.
- [PROD] LLMs only where (1) human chat, or (2) unstructured→structured data the way a human operator would — everything else is deterministic.
- [PROD] Models accessed via API at runtime; never redistributed; API provider chosen per Doc 8 license criteria.
- [PROD] Shipped dependencies are MIT/Apache-2.0 (and equivalently permissive BSD) only, per the Doc 8 allow-list; consume version-pinned, do not fork.
- [PROD] Token discipline is structural, not aspirational: per-loop step and token budgets, structured outputs everywhere, terse tool schemas, hard retrieval budgets, budgeted memory writes.
- [PROD] Memory has four faces — structured, knowledge, episodic, directive — and every agent cycle writes.
- [PROD] Agents are pure configuration (Doc 12 §8 schema); no agent logic in code.
- [PROD] Each shipped block HAS: typed I/O, an idempotency key, a consequence class (reversible / compensable / irreversible), a compensation handler where compensable, a version pin, and zero business assumptions (the artifact half of "every block ships with…" — see bundled slogans).
- [PROD] Channels and intake adapters are an open, config-registered set reducing to one normalized intake event.
- [PROD] Identity resolution lives in the Intake molecule, once, for every channel.

Governance and failure semantics:

- [PROD] The operator holds two levers: promote (one human click, always, absent explicit written policy) and pause (instance, flow class, department, or everything).
- [PROD] Pause is lossless: in-flight atomic actions complete or compensate; the workflow parks at the next step boundary; resume is exact continuation.
- [PROD] Autonomy is graduated and earned per flow (shadow → gated → autonomous), advanced by clean history, demoted by correction.
- [PROD] Gates derive from the consequence taxonomy, not folklore; irreversible actions stay gated longest.
- [PROD] Failure of any kind degrades into a visible, resumable queue — never a silent loss, never confident unrecorded wrongness.
- [PROD] Every decision and action is reconstructable from Temporal event history; inspection never requires trust.
- [PROD] Semantic failure is contained structurally: step/token budgets, stall detection, confidence-routed escalation.
- [PROD] Corrections compound: pause-fix-record in operations (written to episodic memory, never needed twice); rollback-regenerate in commissioning (reset the branch node, regenerate forward, re-certify).
- [PROD] Sovereignty: configuration and data live on ground the member controls; the bundle is declarative and portable.

Non-goals (properties the product must NOT have):

- [PROD] No hosted multi-tenant SaaS — the unit ships onto member-controlled ground.
- [PROD] No self-modifying code of any kind.
- [PROD] No model lock-in — nothing above the inference contract names a model.
- [PROD] No full ERP scope — customer lifecycle only in v1.
- [PROD] No universal memory taxonomy or cross-company document schema in advance.
- [PROD] No heavy forks of upstream dependencies — consume version-pinned, contribute back.
- [PROD] No Attract/marketing department in v1.
- [PROD] No auto-promote — one human click, always, absent explicit written policy.

## The standing rule

The following text is normative and must appear in both CLAUDE.md files (copy-paste verbatim):

> Any reference to a principle or constraint MUST be prefixed with its category tag — [DEV] (development process / operating under now) or [PROD] (end product / building toward). Genuinely-dual slogans must be split into their [DEV] and [PROD] parts before use.

## Known bundled slogans — how to split them

These slogans appeared to belong to "both" categories. None actually does — each bundles two
constraints from different categories. Use the split forms; never cite the bundled form untagged.

1. **"Podman, not Docker"**
   - [DEV] Our dev/test machine cannot run Docker, so all local container work uses Podman.
   - [PROD] The product deploys on Podman (Quadlet stays liquid), as a declarative bundle with software / configuration / data strictly separated.

2. **"Every block ships with typed I/O, idempotency key, consequence class, compensation handler, golden + property tests, version pin, zero business assumptions"**
   - [DEV] We write golden and property tests and pin versions before marking a block done (definition-of-done discipline — acts performed during the build).
   - [PROD] Each shipped block HAS typed I/O, an idempotency key, a consequence class, a compensation handler where compensable, a version pin, and zero business assumptions (artifact properties of the delivered block).

3. **"MIT/Apache-2.0 only (Doc 8)"**
   - [DEV] Every dependency choice in a plan cites its license tier per Doc 8 (the citing is a process step). The dev toolchain itself is exempt from the allow-list — it is proprietary and never shipped.
   - [PROD] Every dependency in the shipped artifact is MIT/Apache-2.0 (Doc 8 allow-list).

4. **"Version pins"**
   - [DEV] We pin versions at plan/build time before marking work done (the act of pinning).
   - [PROD] The release bundle ships with version-pinned images, dependencies, and block versions (the pinned-ness of the artifact).

5. **"Minimum intelligence per task" / "small-model-first"**
   - Not dual, but frequently miscategorized: this is [PROD] only (cheapest/smallest API model that meets the quality bar in the runtime agent loop). Applying it to [DEV] is the exact inversion error — the build toolchain uses maximum capability (Fable plans, Sonnet codes, Haiku never).

6. **"Determinism boundary absolute"**
   - Not dual, but frequently miscategorized: this is [PROD] only (a property of workflow code in the shipped system). Dev-time agents reason nondeterministically by design; the boundary constrains the artifact, not the builders.
