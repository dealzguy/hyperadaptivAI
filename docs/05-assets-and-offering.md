# Document 5 — Assets & Offering in Detail

*This document describes the technical product and the packaged offerings. The product is owned and developed by the IP company and made available to members through the cooperative under the license-and-maintenance agreement. Model names, tooling, and hardware below are point-in-time as of the research recorded in Document 7 and will move; the architecture does not.*

## The platform, component by component

### Hardened base
A security-baselined Ubuntu build: minimal attack surface, locked-down defaults, automatic security patching, and full-disk and at-rest encryption options. Delivered as deployment scripts that take bare hardware or a bare VM to a hardened, ready host with one command or a guided BYO-hardware run. This is the floor the rest of the stack sits on and the first thing the maintenance relationship keeps current.

### The harness (core IP)
The orchestration and control layer, and the single most defensible and most maintenance-hungry asset. It runs and routes to the model layer, manages agents and multi-step workflows, exposes tools to those agents, handles memory and context, and presents a usable interface (chat, API, and management). Crucially, [PROD] it abstracts the model layer so a member is never bound to a single model — when a better or replacement open-weight model ships, the harness adopts it without the member re-architecting. This abstraction is what makes model migration a service the maintenance relationship can deliver. The harness is owned by the IP company and licensed to the cooperative.

### The model layer
> **Superseded (2026-06): API-only inference.** [PROD] All LLM calls go through the infer contract via LiteLLM to a configured external API provider; no local model serving (Ollama/vLLM), no GPU, no model weights on the host. The system targets low-cost VPS or modest-spec machines. The model-agnosticism described below still holds — it now operates across API providers and models behind the same contract, and the API provider is chosen per Doc 8 license criteria. The local-serving description below is retained as the original offering record.

Open-weight models served locally through a standard runtime (Ollama for straightforward single-node deployments; a higher-throughput server such as vLLM for heavier multi-node use). The harness selects and routes among models by task. Commercially-clean choices as of the current research: Qwen 3.5/3.6 (Apache 2.0) for general and agentic work; Gemma 4 (Apache 2.0) for on-device and lighter, multimodal deployments; the Phi-4 family (MIT) for constrained hardware; DeepSeek V4 and larger Qwen coding variants for coding and reasoning on capable hardware; and Mistral families for EU-licensing-sensitive or low-latency single-GPU use. [PROD] The product does not bet on one model; it bets on the harness's ability to run the right current one and to move when the frontier moves.

### Deployment tooling
Ansible playbooks and container tooling (Podman as the system-wide default, Docker where required) that provision the hardened base, install the runtime and harness, load the model and template layers, and verify the result. The same tooling underpins both founder-delivered deployment and the eventual self-serve onboarding path.

### Template and skill library
The pre-built, maintained collection that makes the stack useful immediately: agent configurations, tool integrations, workflow templates, and task-specific skills. Its worth is entirely a function of how current it is, which is why it is a continuously updated paid layer carried by the license rather than a one-time deliverable.

### Integration layer
MCP and connector support that lets the stack reach the member's own data and tools — files, databases, internal services, messaging, and third-party APIs — so the owned stack does real work against real systems rather than running in isolation.

### BYO-hardware path and fungible compute
The documented, supported route for a member to run the entire system on hardware they already own or buy once: a workstation with a capable GPU, a Mac with sufficient unified memory, or a small server. [PROD] Compute providers are fungible by design — the member's own hardware, commodity bare-metal arranged through the co-op, or a mix — swappable so no member is locked to a provider. This is what keeps member-side capital low and makes the sovereignty and ownership claims real.

### Observability, security, and update mechanism
Monitoring, logging, health checks, and the update channel through which the maintenance relationship delivers security patches, model migrations, and template refreshes. This mechanism is the technical embodiment of the recurring relationship and the license.

## The open-core split

Open or low-cost, to build trust and adoption: a usable core harness capable of running a real single-node stack, the basic hardened-base deployment scripts, full documentation, and a starter template set. Paid, because it decays and must be maintained: current maintained harness releases and the control plane, ongoing security hardening, model migration as models are released and deprecated, the premium template and skill library, and the maintenance relationship and support. [PROD] A member or the co-op may fork the open core; doing so transfers the entire maintenance burden onto them — the exact burden they joined to avoid. The open core is genuine and the paid layer is genuinely worth more than forking. That is the design, not a leak in it.

## Packaged offerings

### Deployment service
A fixed-scope engagement: assess the operator's workloads and hardware, deploy and harden the stack, integrate it with their data and tools, load the relevant templates, and hand over with documentation and training. Priced to day rate plus margin. Always sold with membership and maintenance attached. This is the first revenue line and the primary funnel into the cooperative.

### Membership and sovereign access
The ongoing, use-motivated relationship: a patron member pays to use dedicated sovereign access on fungible compute. This is the Forman-clean core of the venture and the relationship that makes maintenance structural rather than a detachable add-on.

### Perpetual license
The stack as a one-time purchase for members who want it, tiered by deployment scale: an operator tier (single-node, one business, BYO-hardware friendly) and a business tier (multi-node or higher-capacity, multiple users, heavier integration). Sold standalone or bundled into a deployment.

### Maintenance tiers
Recurring, tiered, and carried by the license between the co-op and the IP company: a base tier (security updates and model-currency patches), a standard tier (adds template/skill library updates and priority support), and a premium tier (adds hands-on model migration, custom template development, and direct founder access).

### Audits and migrations
A fixed-scope "get off rented inference" engagement: quantify an operator's current API/subscription exposure and risk — what breaks if the account is suspended, what a price increase costs, what confidentiality or residency risk they carry — then scope the owned-stack migration. Sells on its own and funnels directly into membership and maintenance.

### Add-ons
Premium template and skill packs, additional integration connectors, BYO-hardware provisioning blueprints, and extra-capacity or extra-node licensing.

## Delivery model

Phase 0 delivery is hands-on: the founder personally deploys each stack, which simultaneously builds the product against real requirements and establishes the membership and maintenance relationship. Phase 1 standardizes that repeated work into a consistent, repeatable release with defined deployment tooling and a defined maintenance motion. Phase 2 invests revenue into self-serve onboarding and a strengthened control plane so that deployment and routine maintenance no longer require the founder's hands for every member, decoupling revenue from billable hours and making the recurring base scalable.
