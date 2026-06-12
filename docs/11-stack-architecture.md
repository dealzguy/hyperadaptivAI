# Document 9 — Stack Architecture & the Deployable Unit

*This document defines the technical architecture of the owned AI stack as a thing that ships: a deployable package that lands on a prepared host and runs. Where Document 5 describes the product by component and Document 8 governs which software may be folded in, this document governs how the pieces connect and how they are delivered — and, deliberately, at what resolution each piece is committed versus left liquid. The CRM domain and the layer contracts are committed because they are known quantities; the agent internals, the memory taxonomy, and the exact container packing are scaffolded and marked liquid, to be filled in by the first real deployment.*

## Settled decisions this document assumes

- [PROD] **CRM is owned, not rented.** The CRM domain is the venture's own schema in Supabase/Postgres. A legacy CRM is a one-time extraction-and-migration source, never a runtime dependency. This keeps the layer permissive (PostgreSQL / Apache 2.0) and clear of the AGPL/GPL trap every self-hostable open CRM carries.
- [PROD] **Three roles that never trade jobs.** Temporal (MIT) holds *process state*; Supabase/Postgres (Apache 2.0) holds *business data and memory*; the model layer holds *no durable state at all*.
- [PROD] **Memory is the main feature; the libraries that implement it are not.** Context-first operation over company memory is the feature. LangGraph/LangMem (both MIT) are one implementation behind a memory contract — swappable, exactly as models sit behind the inference contract. Elevating any single library to load-bearing-and-irreplaceable would re-create the lock-in the venture exists to remove.
- [PROD] **The unit of delivery is a declarative package, not a disk image.** Podman (Apache 2.0) is the runtime. The package is reproducible from a declaration; a partition/golden image is a generated convenience, never the source of truth (see "Delivery mechanisms").
- [PROD] **Adaptation is configuration selection, not self-modifying code.**

## The one principle, now with a corollary

[PROD] Every layer connects to its neighbours through a **stable contract**, and nothing reaches past a layer to touch another's internals. A contract that holds lets the thing behind it be replaced or upgraded without forcing change anywhere else — this is the whole of the flexibility requirement, paid for once. [PROD] **The deployment corollary: the container seams are the contract seams.** Each pod boundary is a network boundary, and each network boundary is one of the architectural contracts made physical. This is why the package topology and the layer diagram are the same diagram.

## The two natures

Everything in the system is one of two kinds, and the design *is* the boundary between them:

- **Deterministic / irreducible** — behaves identically every time, is replayable and auditable: the CRM primitives, the tools, the durable workflow spine. The skeleton. Committed, version-pinned, shipped as images.
- **Adaptive / contextual** — the memory an agent reasons over and the decisions it makes. Grown, learned, company-specific. The nervous system. Shipped as config and accumulated as data.

[PROD] The governing rule, which is Point 1 stated structurally: **the adaptive layer reads context and chooses; the deterministic layer is the only thing that acts.** An agent never acts directly — it selects among irreducible tools, and the tools, being deterministic and idempotent, do the acting. That single boundary marries flexibility (decisions adapt freely) to reliability (actions are replayable). In deployment terms, the deterministic spine is the stable, slowly-versioned core; the adaptive layer is the part that updates often, as config and model swaps.

## The operating cycle is context-first

The loop is *situate → decide → act → record → loop.* The agent first retrieves the relevant slice of company memory, then decides, then acts through a deterministic tool, then the act and its outcome **become new memory.** Memory is both input to and output of every cycle. That recording step — not an oversized context window — is what makes the company "aware of everything in the window": everything done becomes *retrievable*. The honest verb is *retrieve anything relevant within the window*; the window length is configuration.

## The architecture, by layer

### Persistence & memory (Supabase / Postgres)
The system of record for all business data **and** the home of company memory. Supabase fits Temporal precisely because they don't overlap. Company memory is one substrate with four faces, all living in or beside this Postgres:

- **Structured memory** — the CRM's irreducible facts. Queryable.
- **Knowledge memory** — ingested company documents, embedded (pgvector, permissive) and retrieved by relevance + recency. This is **RAG — offline document ingestion**, a different mechanism from the others. Onboarding does a one-time bulk ingest of existing documents; steady-state ingests on a rolling window.
- **Episodic memory** — what was done over time, decisions paired with outcomes; extracted and consolidated from live interactions. The part that learns. A different mechanism again from RAG.
- **Directive memory** — the editable current-priorities object: what to optimize for now. Editing it is how the company refocuses on its best revenue stream without redeveloping anything.

[PROD] **Hard rule:** Temporal runs its *own* Postgres for its event store. Never co-mingle it with the business/memory database. Two databases, two jobs, two volumes.

### The irreducible CRM
CRM reduces to five primitives: **entity** (an identified, attributed record), **relationship** (a typed link between entities), **event** (a timestamped, actored occurrence attached to entities), **state** (an entity's position in a configurable process), and **task** (a future intended action, assignable to a human or an agent). Every CRM feature ever shipped is a composition of these five plus configuration; the "infinite expression" is the JSONB/config layer on a fixed spine. The irreducible verbs follow directly — *create, relate, record, transition, assign* — and those verbs are the tools. Thin universal tools; rich company-specific data. This layer is committed because it is the known quantity.

### Inference (behind a provider contract)
[PROD] One interface — roughly `infer(model_id, messages, tools, policy) → result` — with LiteLLM behind it providing capability-addressed routing to a configured external API provider; no local model weights are required (API-only inference, 2026-06 — supersedes the original Ollama/vLLM local-serving wording). [PROD] Nothing above this line names a model or provider. Model choice is policy expressed in config: by task, capability tier, and cost — small-model-first: the cheapest/smallest API model that meets the quality bar. New API models and providers register here and are selected by policy; the rest of the stack is untouched. This is how "agents run on different inference sources" costs configuration, not redevelopment.

### Capability (the tool catalog)
[PROD] Activities are the verbs — the only code allowed to touch the world (DB, APIs, models, files, messages). Idempotent, auto-retried, registered in a catalog with typed I/O so workflows and agents can discover them. Families: CRM verbs over the five primitives, communication (behind provider interfaces), inference, integration (MCP/connectors, vetted per Doc 8), document/file. [PROD] **Additive by rule:** a new tool registers itself; it never requires editing an existing workflow to exist.

### Process (Temporal workflows)
[PROD] The durable, stateful sequences — lead-to-close, onboarding, dunning, renewal. [PROD] Deterministic code: no model calls, clocks, randomness, or I/O inside a workflow; all of that lives in activities. This is what makes execution replayable and crash-safe, and it is the line that keeps "self-adapting" honest — the workflow does not mutate itself; the agent inside it chooses among options. [PROD] Logic changes ship through Temporal's versioning APIs so in-flight executions finish on the code they started with.

### Decision (the department agents)
An agent is a workflow loop that calls the inference activity to choose the next tool from the catalog, invokes it, records the outcome, and loops until the goal is met or a human-in-loop gate stops it. Everything that makes an agent *this* agent is configuration: role, allowed tools, objectives, autonomy level. The reasoning engine (LangGraph/LangMem) runs **inside activities**, behind the decision and memory contracts — bounded per activity, because that reasoning is not individually crash-durable on its own; Temporal supplies the durability around it. *Committed only at the contract; the internal shape of each department's agent stays liquid.*

### Interface & human-in-the-loop
The same workflow runs autonomously or supervised depending on one config value per process per department, via Temporal signals: block at an approval gate for a human signal, or advance past a timer if none comes. "A solo operator running like a ten-person team" is this dial, set per department. Plus a management/chat UI and API entry points.

## The deployable unit

This is the centre of the redo: what actually ships onto a member's hardware.

### Three things that must stay separate
[PROD] The package is built so these never fuse:

1. [PROD] **Software** — OCI images, version-pinned: the proprietary harness (IP-company-owned, outbound EULA) plus permissive dependencies (Temporal, Supabase, LiteLLM, Podman). Shippable and updatable. (2026-06: Ollama/vLLM removed — no local model serving ships.)
2. [PROD] **Configuration** — the flexibility surface: business-type config, model policy, agent definitions, autonomy gates, the directive/priorities object, retention window. Per-member; mounted in and stored in config tables.
3. [PROD] **Data** — Postgres volumes (business and Temporal-internal, kept separate), the document store, embeddings, memory. The member's sovereign data. **Never in an image.**

[PROD] This three-way separation is what makes updates clean (new images, data untouched), makes sovereignty real (data in member-controlled volumes), and makes the partition-copy approach the wrong default (it fuses all three).

### Two artifacts: the host, then the package
- **The hardened base (host prep).** Ansible/scripts that take bare Ubuntu to a ready host: Podman installed, NVIDIA Container Toolkit and CDI for GPU passthrough, the security baseline from Document 5, and the storage layout for the data volumes. This is the floor; it is maintained separately from the stack.
- **The package.** The OCI images + pod/compose manifests + a config template that lay the stack onto the prepared host. This is the stack; it is what the license-and-maintenance relationship keeps current.

### Pod topology (mirrors the contracts)
On a single host the pods can collapse into one compose; at business scale they split across nodes. The seams are committed; the packing is scale-dependent and liquid.

- **persistence pod** — Postgres + pgvector (structured + knowledge + episodic memory), plus the lean Supabase services actually needed (PostgREST always; Auth, Realtime, Storage, Studio as required). Volumes: business data, document store, embeddings.
- **orchestration pod** — Temporal server (auto-setup at operator tier; split services at business tier), its *own* Postgres, the Temporal Web UI (the audit/report surface).
- **inference seam** — no local inference pod (superseded 2026-06: API-only inference; previously Ollama/vLLM with GPU via CDI and deploy-time model pulls). LiteLLM routes `infer()` calls from the harness pod to the configured external API provider; no GPU, no model-cache volume, no model weights on the host. The provider endpoint and credentials arrive through the secrets-contract seam.
- **harness pod** — the proprietary harness/control plane, the Temporal workers running workflow + activity code, the LangGraph/LangMem reasoning inside activities, and the memory-contract implementation talking to the persistence pod. Config mounted in.
- **interface pod** — the management/chat UI (Open WebUI, with the branding caveat from Doc 8, or a permissive substitute) and the member-facing API.

### Podman, specifically
<!-- "Podman, not Docker" split: [DEV] our dev/test machine cannot run Docker, so all local container work uses Podman; [PROD] the product deploys on Podman as a declarative bundle, software/config/data strictly separated. -->
[PROD] Apache 2.0, no commercial-use restriction, ships unmodified as a green-tier dependency. [PROD] Use `podman play kube` / `podman generate kube` (or compose) so the topology is declarative. [DEV] Two integration realities to resolve at the first deployment rather than assume away: Supabase's self-hosted stack is authored for Docker and runs under Podman with some friction (rootless socket path, a few Docker-isms) — verify the lean profile end-to-end; and GPU passthrough is simplest rootful while the security baseline prefers rootless, a genuine tension to settle per host, not a solved problem.

### Delivery mechanisms
- [PROD] **Primary — the declarative bundle.** Pinned image references (or a `podman save` image tarball for air-gapped installs) + the pod manifests + the config template + the host-prep playbook. Reproducible from declaration. The maintenance relationship ships updated manifests and images; data and config are untouched. This is the sovereignty-consistent, maintainable, Doc-8-clean path.
- **Fallback — a golden snapshot.** A VM disk image or partition clone **generated from** the declarative bundle on a reference host, for fast field provisioning or disaster recovery. Honest trade-offs: fast and foolproof to restore, but opaque, drift-prone, fuses software+config+data, carries machine-specific cruft, and — per Doc 8 — redistributing a customized Ubuntu image drags in GPL notices and source-offer obligations plus Canonical's trademark restriction on modified images under the "Ubuntu" name. [PROD] If used, it is generated and internal, never hand-authored and never the canonical artifact. Document 8's own guidance applies: prefer deployment scripts over image redistribution.

### How the maintenance relationship lives here
The product the co-op licenses from the IP company is, concretely, **the maintained declarative bundle**: current pinned images, current model migrations, current templates, current patches to the hardened base. A member who forks inherits the entire pin-patch-migrate burden — the divergence tax of Documents 1–5, now literal: the cost of owning every image pin, security backport, and model-compatibility fix forever. The fork is legal and self-defeating by design, expressed in the deployment artifact itself.

## The flexibility invariants

The design laws that keep "no pigeonholing" true over time. A change that breaks one is the warning sign.

1. [PROD] **Config over code.** Business- and moment-specific variation is data, never a branch.
2. [PROD] **Model-agnostic above the inference line.** No layer above it names a model.
3. [PROD] **No closed enumerations on anything that grows** — stages, fields, entity types, departments, tools, models: all data, extensible at runtime.
4. [PROD] **Capabilities are additive.** New tools register; existing workflows are never edited to accommodate them.
5. [PROD] **Determinism boundary is absolute.** Nondeterminism only in activities; workflows stay pure.
6. [PROD] **Software, config, and data stay separate** in the package, always.
7. [PROD] **One contract per seam, honoured on both sides** — including the container seams.

## Resolution map — committed vs. liquid

**Committed (evidence authorizes it now):**
- [PROD] The layer set and the contracts between them, and the rule that container seams are contract seams.
- [PROD] The CRM five-primitive schema and its flexibility handles — known quantity.
- [PROD] The inference provider contract and the memory contract (as contracts).
- [PROD] The determinism boundary, the three-way software/config/data separation, and the seven invariants.
- [PROD] Temporal-as-durable-spine, Supabase-as-system-of-record-and-memory, separate databases, Podman as runtime, declarative-bundle-as-primary-delivery.

**Scaffolded thin (exists, internals deferred to the first deployment):**
- The internal decision logic of each department agent.
- The **memory taxonomy inside each of the four faces.** Commit the four faces and the normalization contract; [PROD] do *not* commit a universal cross-company document taxonomy in advance — there is no universal memory schema, and a taxonomy designed before any real corpus is observed is anticipated, not observed, duplication. Grow it from the first company's actual documents.
- The **LangGraph/LangMem internals** — held behind the memory and decision contracts, replaceable; the integration is real but experimental, so pin it and watch it.
- The exact pod packing, the Supabase-under-Podman lean profile, and the rootless-vs-GPU resolution — settled per host, not assumed.
- Cross-department orchestration (how sales hands to ops hands to finance).

## The thin first cut

Build the smallest deployable unit that exercises every seam once. On one prepared host: the persistence pod (Postgres + pgvector with the five-primitive CRM schema and a single document-ingestion path), the orchestration pod (Temporal + its own Postgres), the inference pod (one model behind the infer contract), and a minimal harness pod running **one** workflow — lead-intake-to-first-follow-up — with one agent whose tools are four CRM verbs and whose human-in-loop gate is on. Lay it down from the declarative bundle, not by hand. Run it against the first warm-network operator's real leads and real documents. That one loop touches persistence, memory, inference, capability, process, decision, interface, and the package itself — and what it teaches is what specifies every internal currently marked liquid. Everything else grows from the duplication that first deployment reveals, not from anticipation.
