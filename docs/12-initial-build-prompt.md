# Document 12 — Goals, Approach, Context & the Initial Build Prompt

*This document consolidates the harness design line into one canonical statement: the goals, the approach, the context a builder must hold, and the assembled initial prompt. Its organizing distinction is the one that keeps every other decision honest — **Commissioning runs once; Operations runs forever.** The one-time intake factory that learns a business and the infinite, adaptive, replay-durable execution of that business's lifecycle are two modes of one machine, built from the same material, governed by different correction disciplines. Confusing the two is how patch-over-patch systems get built; separating them is how this one stays clean. Where prior decision points went unanswered, this draft takes recorded defaults rather than silent assumptions — see "Defaults taken" at the end of Part III.*

## Terminology — "replay," used precisely

One word carries two load-bearing meanings, so they are separated here once and used distinctly everywhere after.

**Replay, the mechanism,** is Temporal's deterministic re-execution of a workflow from its event history. It is what makes execution durable (a crashed worker resumes exactly where it died), auditable (event history is evidence, not logging), and pausable (parked state is recoverable state).

**Recurrence, the operation,** is the unbounded repetition of lifecycle patterns across instances — every new lead runs the same proven shape, forever.

"Infinite adaptive replay operations" therefore means, precisely: **unbounded recurrence of finite, replay-durable workflow instances, adapting *between* instances through configuration and memory, never *within* an instance through mutation.** Each instance is deterministic and replayable; the population of instances learns. This is the venture's standing rule — adaptation is configuration selection, not code mutation — located at exactly the point where it applies.

---

## Part I — Goals

### The terminal goal

A business whose customer lifecycle runs without the operator's hands in it. Every lead — web form, phone call arriving as a VAPI-style transcript, webchat with a human or another AI agent, walk-in entered by staff — enters one system and is qualified, worked, quoted, fulfilled, billed, and renewed by it. Every step is durable, auditable, and visible. The operator watches a reporting surface instead of working a task list, intervenes only to correct, and holds two levers: **promote** (a constructed flow goes live) and **pause** (any single instance, any flow class, any department, or everything — instantly, safely, losslessly). The operator's job changes from doing the work to supervising the worker.

### The two lifecycles that deliver it

**Commissioning — runs once per business.** The system learns the business. An agent-led clarification interview frames it; dissection extracts its data, its processes, and its calculations; construction compiles them into configuration; validation certifies the result against the strongest evidence the business can offer; promote puts it live. Its output is a configuration bundle. Its correction discipline is **rollback-regenerate**: locate the construction branch where the flawed assumption entered, reset to that node, regenerate forward, re-certify. When commissioning ends, it ends — re-entered only when a structural correction demands it.

**Operations — runs forever.** The system executes the lifecycle as infinite recurrence of finite durable workflows. Its output is business outcomes plus accumulated memory. Its correction discipline is **pause-fix-record**: stop the instance, correct it in place, resume, and write the correction into memory so it compounds — no correction is ever needed twice. Operations never restructures itself; a structural problem is not patched live, it routes back through commissioning. This is what makes "adaptive" safe: the live system adapts by selecting among validated configurations and by remembering, never by rewriting itself.

### Subordinate goals, each derived from the terminal goal

- **Durability.** Failure is non-fatal, not impossible: a crash degrades into a visible, resumable queue, never into a loss.
- **Auditability.** Every decision and action is reconstructable from event history; inspection never requires trust.
- **Sovereignty.** Software, configuration, and data stay separate; configuration and data live on ground the member controls; the bundle is declarative and portable.
- **Economy.** Token discipline is structural — small-model-first routing, structured outputs, hard retrieval budgets, terse tool schemas, budgeted memory writes — not aspirational.
- **Compounding.** Corrections, memory, and the archetype/switch catalog all appreciate with use. Operations also *manufactures the evidence commissioning lacked*: every cycle writes linked intake→outcome history, so a business commissioned on thin evidence can be re-certified on rich evidence later. Certification strengthens over time by construction.

### Scope, declared

Customer lifecycle now. ERP-adjacent functions — inventory, procurement, ledger — arrive later as additive departments and tool families under the additive rule, never as v1 scope. "Any business, any source" is the architecture's aim; the *certified claim* at v1 is scoped to the first deployment's business class, with generality earned at the second instance, per the operator-error discipline.

---

## Part II — Approach

### The shared substrate

Both modes are built from the same material and obey the same physics. The **two-natures boundary**: adaptive components read context and choose; deterministic components are the only things that act. The **legoblock hierarchy**: verified blocks (typed, idempotent, deterministic, individually tested) compose into molecules (recurring cross-industry compositions — Intake, Touch, Qualification, Commitment, Handoff, Settlement, Escalation, Renewal), which compose into the commercial shell. The **closure check** runs in both directions: every shell process must decompose into molecules with no remainder; every molecule must trace to a shell process. A remainder falsifies the irreducibility claim; an orphan is anticipated duplication and gets deleted. **Temporal is the spine of both modes** — commissioning itself runs as a Temporal workflow, so its construction commitments are events, its branch points are history, and rollback is a native workflow reset rather than invented machinery. The **memory substrate** is one Postgres with four faces (structured, knowledge, episodic, directive). And the master rule throughout: **config over code** — all business specificity lives in configuration composed from verified blocks, which quarantines all deployment-specific wrongness in the one layer that is cheap and safe to regenerate.

### The meta-model: grammar committed, dictionaries liquid

Every business is the same machine — it acquires commitments from customers and discharges them profitably — unrolled as a seven-stage commercial shell: **Attract → Engage → Qualify → Commit → Fulfill → Settle → Retain** (v1 enters at Engage; Attract is a future department). The decisive observation is where variance lives: businesses engage, qualify, commit, settle, and retain in nearly identical shapes under different vocabulary; they genuinely differ in **Fulfill**. So the shape is a universal shell wrapped around a pluggable fulfillment core, and all business-to-business difference is expressed through exactly three configuration mechanisms — **archetype** sub-workflows in the Fulfill slot, **characteristic switches** that gate molecules and departments on or off, and **parameters** (vocabulary, thresholds, stage names, deterministic calculation rules). The 80% is the most-replicated pattern in commercial history, which is what authorizes committing the grammar; every individual business's content stays liquid.

### Commissioning is selection, not generation

The meta-model converts extraction from open-ended authorship into **locating a business in a known space** — choose the archetype, set the switches, fill the parameters, lift the rules. The interview becomes a structured traversal rather than open discovery; construction-tree branch points become typed, enumerable choices; rollback becomes precise; validation becomes mechanically checkable in a way free-form process authorship never was. This is what makes fully agentic commissioning an acceptable risk: the generation target is a constrained, declarative, mechanically validatable artifact, not open code. The pipeline is staged — interview → dissection → construction → validation → promote — with an evidence-relative validation ladder and one external anchor (operator-authored scenario cards) so certification is never measured purely against the loop's own outputs.

### Operations is recurrence under supervision

The agent loop is *situate → decide → act → record*: retrieve the relevant slice of company memory, choose the next tool from the catalog, act through a deterministic block, write the outcome back as new memory. Agents are defined entirely in configuration — role, objectives, tool allowlist, autonomy level, model policy, budgets. The human is **on** the loop: continuous reporting, intervention by exception, the pause lever always live. In-the-loop gates exist only as configuration deployed by exception — actions the business's own consequence taxonomy marks irreversible, and the probation period of any newly promoted flow. Autonomy is graduated and earned per flow (shadow → gated → autonomous), advanced by clean history, demoted by correction. Semantic failure — confident wrongness and non-progress, the agent loop's true modal failure — is contained structurally: step and token budgets, stall detection, confidence-routed escalation.

### The bridge between the modes

Forward, exactly one thing crosses: the **promoted configuration bundle**, transferred by the operator's one click (automatable only by explicit written policy). Backward, two things cross: **structural corrections**, which re-enter commissioning at the typed branch node where the flaw lives; and **evidence**, because accumulated operational history raises the achievable validation tier — a business commissioned at Tier 0 can be re-certified at Tier 1 a quarter later from its own records. The ladder is climbable, and operations builds the rungs.

---

## Part III — Context

### Venture context

The harness is the core IP of a two-entity venture: a founder-owned IP company that owns and licenses the platform, and a member-owned Colorado cooperative that provides members sovereign stack access and pays the IP company a license-and-maintenance fee (Docs 1–4). The commercial wedge is ownership and continuity — sovereign AI, sovereign stack, sovereign data — sold to operators from solo through mid-market. Phase 0 is services-first: hands-on deployment for one to three warm-network operators who become charter patron members; their real requirements specify the product. The warm network maps directly onto the first archetype catalog — industrial racking (order/delivery), SEO/audit (project/milestone), insurance (policy/coverage). The meta-model is the venture's moat made formal: the owned layer above commodity orchestration, appreciating with every deployment that either fits it or grows it. Licensing discipline is firm MIT/Apache-2.0 (Doc 8); patron-facing copy never implies financial return.

### Technical context — settled, not re-litigated

Temporal (MIT) is the durable orchestration spine. Supabase/Postgres (Apache 2.0) with pgvector is the system of record and the memory substrate; Temporal runs its **own** Postgres, never co-mingled. Podman (Apache 2.0) is the runtime; the deployable unit is a declarative bundle with a strict three-way separation of software, configuration, and data; golden images are generated conveniences, never sources of truth. Inference sits behind a provider contract (`infer(model_id, messages, tools, policy)`) with LiteLLM capability-addressed routing; nothing above the line names a model; models are pulled at deploy time, not redistributed. The CRM domain is five primitives — entity, relationship, event, state, task — with five verbs: create, relate, record, transition, assign. The determinism boundary is absolute: no model calls, clocks, randomness, or I/O inside workflows; all nondeterminism lives in activities. The seven flexibility invariants of Doc 9/11 govern every change.

### The governing discipline

Operator-error.md is the meta-rule of the whole build: commit only what evidence authorizes; scaffold thin on anything the first deployment must specify; mark deferred internals `TODO(liquid: <what specifies it>)`; extract abstractions at the second instance of a pattern, never the first. The resolution map in the prompt below is this discipline applied.

### Authority in Phase 0

During deployment and probation, promote and pause are held by the founder-as-deployer as an explicitly **delegated and expiring** authority that transfers to the member at handover. Sovereignty is preserved by making the delegation visible, not by pretending it isn't happening.

### Defaults taken in this draft (recorded, not silent)

Adopted pending objection: the evidence-relative validation ladder with operator-authored scenario cards as the external anchor; semantic failure containment (budgets, stall detection, consequence-derived gates); the scope narrowing declared in Part I; delegated-expiring Phase-0 authority; the meta-model embedded in this prompt (a standalone Doc 13 extraction remains optional); archetype catalog v1 = the three warm-network archetypes with appointment/visit named-not-built; switch set v1 = entity model, revenue shape, pricing mode committed, with inventory, compliance, and channel shape named-not-built; closure check as design-time discipline with CI automation left liquid; working names (shell, molecules, switches, archetypes) retained pending one deliberate naming pass.

---

## Part IV — The Initial Build Prompt

*This part is self-contained and written to the build agent; Parts I–III are its rationale. Hand it over with Documents 8 and 9/11 attached.*

### 0. Mission and non-goals

You are building a deployable agentic harness with two modes. **Commissioning** runs once per business: an agentic pipeline that interviews, dissects, constructs, validates, and promotes a configuration bundle that locates the business within a committed business meta-model. **Operations** runs forever: durable Temporal workflows executing that business's customer lifecycle as unbounded recurrence of finite, replay-durable instances, supervised by a human on the loop, adapting between instances through configuration and memory and never within an instance through mutation.

Non-goals — do not build: a hosted multi-tenant SaaS (the unit ships onto member-controlled ground); self-modifying code of any kind; model lock-in (nothing above the inference contract names a model); full ERP scope (customer lifecycle only in v1); a universal memory taxonomy or cross-company document schema in advance; heavy forks of upstream dependencies (consume version-pinned, contribute back); the Attract/marketing department; autonomous promotion of constructed flows except by explicit written policy.

### 1. The master distinction

Every artifact you create declares which mode it serves. Anything serving both lives in the shared substrate and carries zero business assumptions.

| | Commissioning (once) | Operations (forever) |
|---|---|---|
| Purpose | Learn the business; compile configuration | Execute the customer lifecycle |
| Runs | Once per business; re-entered only for structural change | Continuously; unbounded instances |
| Built as | A Temporal workflow whose events are construction commitments | Temporal workflows per lifecycle process |
| Output | The promoted configuration bundle | Business outcomes + memory |
| Adaptation | Rollback to a typed branch node; regenerate forward | Configuration selection + memory accumulation |
| Correction | Re-certify against scenario cards and the validation ladder | Pause → fix in place → record; structural issues route to commissioning |
| Human role | Interview subject, scenario-card author, promote authority | On-the-loop supervisor; pause authority |
| Wrongness lives in | The construction tree (cheap to regenerate) | Config and memory (correctable; corrections compound) |
| Never happens | Patching artifacts downstream of the flaw | Code mutation; silent structural drift |

### 2. Settled constraints — do not re-litigate

Temporal spine for both modes. Supabase/Postgres + pgvector as system of record and memory; separate Temporal Postgres; two databases, two volumes. Podman runtime; declarative bundle delivery; software/config/data never fuse. Five CRM primitives and five verbs. Determinism boundary absolute (nondeterminism only in activities). Inference behind the provider contract with LiteLLM capability routing; pull-don't-redistribute model weights; MIT/Apache-2.0 sourcing only (Doc 8 allow-list governs). The seven invariants: config over code; model-agnostic above the inference line; no closed enumerations on anything that grows; capabilities are additive; determinism boundary absolute; software/config/data separate; one contract per seam, honoured on both sides — including container seams.

### 3. The business meta-model

**Shell (committed):** Attract → Engage → Qualify → Commit → Fulfill → Settle → Retain. V1 enters at Engage. Each stage is a state machine over the five primitives, parameterized per business.

**Molecules (committed as a starter set, grown by closure):** Intake (match-or-create entity, record source event, open lifecycle state — identity resolution lives here once, for every channel); Touch (task → communication act → outcome → next task or transition); Qualification (gather attributes, evaluate deterministic rule, transition); Commitment (generate document entity, relate, await response, transition — quote, proposal, booking, application, and estimate are this one molecule under different vocabulary and rules); Handoff (close one state machine, open the next, transfer context); Settlement (invoice entity, payment events, reconciliation; dunning as its exception path); Escalation (detect condition, park, notify, await signal); Renewal (timer, evaluate, re-open Commitment). Molecules are compositions of verified blocks only, carry no business assumptions, and are individually testable.

**Closure check (design-time discipline):** every shell process decomposes into molecules with no remainder; every molecule traces to at least one shell process. Run it whenever the catalog changes. A remainder means a missing verb or primitive; an orphan means anticipated duplication — delete it. `TODO(liquid: automate as construction-time CI once the catalog is exercised by a second deployment)`.

**Variance mechanisms (committed as mechanisms; catalogs open):** the Fulfill **archetype slot** — v1 catalog: order/delivery (source, ship or install, confirm), project/milestone (scope, deliver, accept, retainer loop), policy/coverage (apply, underwrite, issue, service); appointment/visit is named, not built. **Switches** — v1 committed: entity model (B2B / B2C / both), revenue shape (one-time / recurring; gates Renewal and dunning), pricing mode (listed / quoted; gates Commitment's generation step); named-not-built: inventory, compliance, channel shape. A switch selects which verified compositions are active; it never branches code. **Parameters** — vocabulary maps, stage names, thresholds, retention windows, and the deterministic calculation rules lifted by commissioning.

### 4. Commissioning specification (runs once)

Build the pipeline itself as a Temporal workflow whose events are the construction commitments and whose branch points are typed: archetype → switches → per-process parameters → rule sets.

**Stage 0 — clarification interview.** Agent-led, adaptive, before any document is read. Captures intent in the operator's own vocabulary: what is sold, to whom, the real lifecycle stages, where revenue concentrates, which exceptions matter. Produces three artifacts: the **context frame** (versioned; the root node of the construction tree; read by every later stage); the **consequence taxonomy** (every action class marked reversible / compensable / irreversible — a required output, because gate placement derives from it, not from folklore); and **5–10 operator-authored scenario cards** ("given this lead, this is what should happen"), ideally walked from the operator's last few real deals, closed with a frame read-back in their vocabulary. The cards are the external anchor: acceptance tests authored by the one party who knows ground truth.

**Stage 1 — dissection.** Inventory and classify the corpus (documents, spreadsheets, legacy CRM export, interview transcript), then three frame-contextualized extractions: **data** mapped into the five primitives; **process** mapped onto the shell — archetype proposal, switch settings, per-stage definitions; **calculations** lifted as deterministic rule candidates, each with test vectors from real artifacts (this actual invoice, that actual quote) the rule must later reproduce exactly. Every extracted artifact carries provenance: which document or interview answer authorized it.

**Stage 2 — construction.** Compile the artifacts into the declarative configuration bundle: workflow configs, agent definitions, tool bindings, rules, vocabulary maps. Selection-plus-parameterization against the meta-model — never free-form process authorship.

**Stage 3 — validation ladder (evidence-relative).** Tier 0, always: schema checks, simulation, exact reproduction of every calculation test vector, every scenario card passing. Tier 1, only if linked intake→outcome history exists: historical replay of last quarter's real intake, divergence scored. Tier 2, only if a comparable live process exists: shadow mode beside current operations, touching nothing, until divergence goes quiet. Record which tiers ran inside the bundle; missing tiers are compensated post-promote with longer probation and more gates. The certification claim is always exactly as strong as the evidence behind it.

**Stage 4 — promote and probation.** Promote is one human click (auto-promote only by explicit written policy). The flow runs gated through probation; graduation to autonomy follows clean execution history; correction demotes.

**Correction discipline — rollback-regenerate, never patch.** When validation fails or a structural correction arrives from operations: provenance locates the branch node where the flawed assumption entered; the construction workflow resets to that node; everything downstream regenerates; the same ladder re-certifies. Branch depth is blast radius, and that is acceptable because generation is cheap and certification is mechanical.

### 5. Operations specification (runs forever)

**Intake contract.** Channels are an open set of config-registered adapters — v1: web form, VAPI-style call transcript, webchat (human or AI), manual walk-in entry. Every channel reduces to one normalized intake event: source channel, raw payload reference, identity candidates, captured attributes, timestamp, consent/compliance flags — extensible, never a closed enumeration. The Intake molecule consumes it; identity resolution happens there, once, for all channels.

**The agent loop.** Each department agent is a workflow loop: *situate* (retrieve the relevant memory slice within budget), *decide* (inference activity chooses the next tool from the allowlist), *act* (the deterministic block executes), *record* (act and outcome written back as memory), repeat until goal, gate, budget, or stall. Reasoning libraries (LangGraph/LangMem) run inside activities behind the decision and memory contracts — bounded per activity; Temporal supplies durability around them.

**Memory contract.** Four faces: structured (the primitives), knowledge (ingested documents, pgvector), episodic (decisions paired with outcomes, consolidated from live interactions), directive (the editable priorities object — the operator's steering wheel between corrections). Every cycle writes. Retrieval policy is configuration: relevance plus a recency window. **Write-path economy:** episodic consolidation runs on batch windows with explicit budgets; embedding throughput is capped; retrieval budgets are enforced config, not convention.

**Token discipline (structural).** LiteLLM capability-addressed routing, small-model-first with escalation on uncertainty; structured outputs everywhere; terse tool schemas (short names, flat arguments, enums); per-loop step and token budgets.

**What operations may change, and what it may not.** May: parameter edits within validated bounds, directive memory edits, memory accumulation, autonomy-level movement per policy. May not: structural change of any flow — that is a commissioning re-entry, full stop. This line is what prevents patch-over-patch in the live system.

### 6. Governance and the reporting surface

**Two levers.** Promote: the single transfer of authority from shadow to primary. Pause: scoped to one instance, one flow class, one department, or everything. Pause semantics: an in-flight atomic action completes or compensates; the workflow parks at the next step boundary; resume is exact continuation, nothing lost. A paused flow is held, not killed.

**Graduated autonomy.** Per flow: shadow → gated → autonomous. Advanced by clean history, demoted by correction. Gates derive from the consequence taxonomy (irreversible actions stay gated longest) plus probation policy.

**The reporting surface is the product.** Three attention bands with assignment derived from the consequence taxonomy: interrupt-now (irreversible-class events, stalls, escalations, budget breaches), today's digest (state transitions, completions, gated items waiting), queryable archive (everything, via event history). The correction log feeds interrupt priors so the surface learns what this operator considers worth seeing. "Anomaly detection" in v1 is honest threshold rules, nothing more.

**Corrections.** Operational (this lead mishandled): pause, fix in place, resume, record as episodic memory. Structural (the flow is wrong): route to commissioning as a rollback at the responsible branch node. Both share one discipline: locate where the wrongness entered; fix at that point; never paper over it downstream.

### 7. Reliability and failure semantics

Infrastructure failure: idempotent activities with retry-and-backoff; heartbeats on long activities; compensation/saga for external side effects; escalation to human on retry exhaustion; workflow versioning so in-flight executions finish on the code they started with; pause/park/resume as specified; workflow reset as the commissioning rollback mechanism. Semantic failure: per-loop step and token budgets; stall detection (N iterations without a state-transitioning tool call → park and escalate); confidence-routed escalation to a larger model or a human. Failure of either kind degrades into a visible queue — never into a silent loss, never into confident unrecorded wrongness.

### 8. Capability-layer schemas

**Block (activity/tool) schema:** name; typed input/output; idempotency key; deterministic effect; consequence class (reversible / compensable / irreversible); compensation handler where compensable; golden and property tests; version pin. Blocks carry no business assumptions. New blocks register in the catalog; existing workflows are never edited to accommodate them.

**Agent definition schema (pure configuration):** id; department; role; objectives; tool allowlist; autonomy level (shadow / gated / autonomous); gates (derived from consequence taxonomy); escalation rules; model policy (capability-tier mapping); retrieval budget; step budget; token budget.

**Tool families (seed):** CRM verbs over the five primitives; communication (behind provider interfaces); inference; document/file; integration (MCP/connectors, vetted per Doc 8).

### 9. Acceptance — the thin first cut, both modes exercised

**Commissioning acceptance.** Run Stage 0→4 against the first warm-network operator (or a faithful fixture of their business class): interview produces frame, taxonomy, and cards; dissection produces mappings, an archetype/switch proposal, and at least one calculation rule with real test vectors; construction emits the bundle; Tier 0 passes including every scenario card. Then the discipline test: deliberately inject one wrong frame assumption at Stage 1, demonstrate that provenance locates it, that branch rollback regenerates downstream, and that the regenerated bundle re-certifies.

**Operations acceptance.** Deploy the bundle as the thin loop — one channel (web form), one agent, four CRM verbs, gate on, flow: lead-intake to first-follow-up. A real lead traverses it end to end. Kill a worker mid-run: exact resume. Pause the instance: lossless resume. Pause the flow class: every instance parks at a safe boundary. Make one correction: it is recorded as episodic memory and retrievable in the next situate step. The replay audit of the full journey reads true.

The system is accepted only when **both correction disciplines have been exercised** — rollback-regenerate in commissioning, pause-fix-record in operations.

### 10. The liquid map — do not pre-build

Marked `TODO(liquid: <what specifies it>)` throughout: internal decision logic of each department agent (first deployment specifies); memory taxonomy inside each face (first real corpus specifies); LangGraph/LangMem internals (pinned, watched, replaceable behind contracts); exact pod packing, Supabase-under-Podman lean profile, rootless-vs-GPU resolution (settled per host); cross-department orchestration (second department specifies); closure-check CI automation (second deployment specifies); attention-band tuning and anything beyond threshold rules (operational evidence specifies); archetypes and switches beyond the v1 sets (each arriving deployment specifies); manifest format, Quadlet vs. compose, and the monitoring aggregation stack (first deployment observation specifies); the naming pass on meta-model vocabulary (before it fossilizes into member-facing IP).

### 11. Environment facts

Host: hardened Ubuntu per Doc 5, prepared by the host-prep playbook; Podman runtime, rootless preferred with the GPU-passthrough tension resolved per host. Language: Python; Temporal Python SDK `TODO(liquid: founder pins version at repo init)`. Persistence: self-hosted Supabase lean profile (PostgREST always; Auth/Realtime/Storage/Studio as required) plus pgvector; separate Temporal Postgres. Inference: Ollama behind the infer contract at operator tier; LiteLLM routing; Apache/MIT model families pulled at deploy. Secrets: delivered through the committed secrets-contract seam; implementation per host. Repo layout and config-table schema: `TODO(liquid: founder specifies at repo init)`. Configuration mounts into the harness pod and persists in config tables per Doc 9/11.

---

*End of Document 12. The next artifact, when wanted, is the Stage 0 interview protocol — the first commissioning component the first deployment will actually exercise.*
