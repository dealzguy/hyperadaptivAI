# Harness Comparison: Temporal Harness vs Claude Code

*Purpose: juxtapose componentry and process to identify artful exclusions and genuine gaps.*

---

## 1. Component Layer

```
┌─────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│         TEMPORAL HARNESS                │   │           CLAUDE CODE HARNESS           │
│         (HyperadaptivAI)                │   │           (this tool)                   │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  OPERATOR SURFACE                       │   │  USER SURFACE                           │
│  Queue · Approve/Reject · Pause/Resume  │   │  Terminal · IDE · Web · modal prompt    │
│  (Phase E — not yet built)              │   │  (built in)                             │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  INSTRUCTIONS / DIRECTIVES              │   │  INSTRUCTIONS / DIRECTIVES              │
│  Config bundle  (agent-spec.json,       │   │  CLAUDE.md  (project law, hierarchy)    │
│  flow-spec.json, vocab.json)            │   │  memory/ files  (persistent, typed)     │
│  Human-approved, version-pinned         │   │  Hand-authored, no approval gate        │
│  Produced by commissioning              │   │  No commissioning step                  │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  PLANNING / COMMISSIONING LAYER         │   │  PLANNING / SKILL LAYER                 │
│  CommissioningWorkflow                  │   │  Plan mode  (Shift+Tab toggle)          │
│  interview → dissect → construct        │   │  Skills / plugins  (/slash commands)    │
│  → validate → await_promote → promote  │   │  No execution layer of its own          │
│  Durable, replayable, correctable       │   │  Generates a plan; model then follows   │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  AGENT LOOP WORKFLOW  (explicit)        │   │  AGENT LOOP  (implicit)                 │
│  SITUATE → DECIDE → ACT → RECORD       │   │  Read context → Generate →              │
│  Temporal workflow, durable             │   │  Tool call → Observe → repeat           │
│  Signals: pause / resume / stop         │   │  No explicit state machine              │
│  Queries: get_state()                   │   │  Loop terminates on final text output   │
│  Budget + stall detection               │   │  or context exhaustion                  │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  TOOL / ACTIVITY REGISTRY              │   │  TOOL REGISTRY                          │
│  Typed I/O dataclasses                  │   │  Read · Write · Edit · Bash             │
│  Idempotency key on every activity      │   │  WebFetch · WebSearch                   │
│  Consequence class  (R / C / I)         │   │  Agent · Workflow                       │
│  Compensation handler where C          │   │  No consequence classification          │
│  Gate check before C or I acts         │   │  No idempotency key                     │
│  Activities: situate, decide, act,      │   │  No compensation concept                │
│  record, interview, dissect, construct, │   │  Permission mode = coarse gate only     │
│  validate, promote, + all CRM verbs     │   │                                         │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  SUBAGENT / MULTI-AGENT LAYER          │   │  SUBAGENT REGISTRY                      │
│  Not yet built (Phase E)               │   │  Explore · Plan · general-purpose       │
│                                         │   │  code-reviewer · claude-code-guide      │
│                                         │   │  Workflow (deterministic fan-out)       │
│                                         │   │  Typed by capability, not consequence   │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  INFERENCE LAYER                        │   │  MODEL LAYER                            │
│  Infer contract  infer(model_id,…)      │   │  Direct API call (Anthropic)            │
│  Model-id allowlist guard (config)      │   │  Model named at session start           │
│  LiteLLM router → configured API        │   │  Fast mode toggle (Opus)                │
│  provider (no local weights, no GPU)    │   │  No routing layer                       │
│  Small-model-first: cheapest/smallest   │   │  No allowlist guard                     │
│  API model meeting the quality bar      │   │  Cloud-only                             │
│  INFER_STUB=1 for deterministic tests  │   │                                         │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  MEMORY LAYER  (four faces)             │   │  MEMORY LAYER                           │
│  Episodic   — agent_episodic table      │   │  Context window  (ephemeral, ~200k tok) │
│  Directive  — agent_directive table     │   │  CLAUDE.md       (directive, durable)   │
│  Knowledge  — knowledge_doc + pgvector  │   │  memory/ files   (typed, persistent)    │
│  Structured — CRM tables               │   │  Auto-summarised on context overflow    │
│  Durable, queryable, searchable (cos)  │   │  No vector search                       │
│  Survives worker restart               │   │  Context lost on session end            │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  CRM SPINE                              │   │  TASK LAYER  (in-session only)          │
│  entity · relationship · event          │   │  TaskCreate / TaskUpdate                │
│  state · task  (five primitives)        │   │  No entity/relationship model           │
│  Five verbs: create relate record       │   │  No event/state machine                 │
│  transition assign                      │   │  Linear checklist only                  │
│  All features are config on this spine  │   │                                         │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  EXTERNAL INTEGRATIONS                  │   │  MCP SERVER LAYER                       │
│  None yet (Phase E)                     │   │  Playwright · temporal-docs             │
│                                         │   │  Gmail · Google Drive · Calendar        │
│                                         │   │  Extensible via server config           │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  PERSISTENCE                            │   │  SESSION STORE                          │
│  Postgres Business  (port 5433)         │   │  JSONL transcript  (~/.claude/…)        │
│  + pgvector  (vector(768))              │   │  Not queryable by the agent itself      │
│  Postgres Temporal  (event history)     │   │  No structured schema                   │
│  Two databases, never co-mingled        │   │                                         │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  DURABLE EXECUTION ENGINE               │   │  EXECUTION MODEL                        │
│  Temporal Server                        │   │  Stateless per turn                     │
│  Task queues · Event history            │   │  No replay on failure                   │
│  Visibility (search workflows)          │   │  Workflow tool adds partial durability  │
│  Full replay on worker restart          │   │  (deterministic script, not full ES)    │
│  Determinism boundary enforced          │   │  No determinism boundary concept        │
│                                         │   │                                         │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│                                         │   │                                         │
│  CONTAINER RUNTIME                      │   │  HOST                                   │
│  Podman  (rootless)                     │   │  Bare process on user's OS              │
│  Declarative compose                    │   │  No containerization                    │
│  Software / config / data separated     │   │                                         │
│                                         │   │                                         │
└─────────────────────────────────────────┘   └─────────────────────────────────────────┘
```

---

## 2. Process Layer

```
TEMPORAL HARNESS — OPERATIONS CYCLE           CLAUDE CODE — AGENT LOOP
─────────────────────────────────────         ─────────────────────────────────────

  trigger: intake event                          trigger: user message
       │                                               │
       ▼                                               ▼
  ┌──────────────────────────┐               ┌──────────────────────────┐
  │  SITUATE  activity        │               │  READ CONTEXT             │
  │  Read CRM entity          │               │  Conversation history     │
  │  Read episodic memory     │               │  CLAUDE.md (directives)   │
  │  Read active directives   │               │  memory/ files            │
  │  Build context frame      │               │  Task list (if any)       │
  └────────────┬─────────────┘               └────────────┬─────────────┘
               │                                           │
               ▼                                           ▼
  ┌──────────────────────────┐               ┌──────────────────────────┐
  │  DECIDE  activity         │               │  GENERATE                 │
  │  infer(model_id from      │               │  claude-sonnet-4-6        │
  │   config bundle, via API) │               │                           │
  │  model picks tool from    │               │  model decides: text OR   │
  │  allowlist                │               │  which tool to call       │
  │  or escalates             │               │  (free choice — no        │
  │                           │               │   explicit allowlist)     │
  └────────────┬─────────────┘               └────────────┬─────────────┘
               │                                           │
               ▼                                           ▼
  ┌──────────────────────────┐               ┌──────────────────────────┐
  │  ACT  activity            │               │  TOOL EXECUTION           │
  │  Consequence check        │               │  Permission check:        │
  │  R → execute immediately  │               │  auto / prompt / plan     │
  │  C → wait for gate signal │               │  (coarse — no R/C/I       │
  │  I → wait for gate signal │               │   classification)         │
  │  Compensation if C fails  │               │  No compensation          │
  └────────────┬─────────────┘               └────────────┬─────────────┘
               │                                           │
               ▼                                           ▼
  ┌──────────────────────────┐               ┌──────────────────────────┐
  │  RECORD  activity         │               │  OBSERVE                  │
  │  Write episodic entry     │               │  Tool result appended     │
  │  Update CRM state         │               │  to context window        │
  │  idempotency key          │               │  No structured write-back │
  │  Durable in Postgres      │               │  Lost on session end      │
  └────────────┬─────────────┘               └────────────┬─────────────┘
               │                                           │
               ▼                                           ▼
  budget / stall / goal?  ──NO──►  loop       final text? ──NO──►  loop
               │                                           │
              YES                                         YES
               │                                           │
               ▼                                           ▼
  escalate to human task                     output text to user
  OR mark complete                           session ends / continues


─────────────────────────────────────────────────────────────────────────

TEMPORAL HARNESS — COMMISSIONING CYCLE        CLAUDE CODE — "COMMISSIONING"
─────────────────────────────────────         ─────────────────────────────────────

  trigger: operator submits business            trigger: human writes CLAUDE.md
           description (fixture JSON)
       │                                               │
       ▼                                               ▼
  INTERVIEW activity                           Hand-author project instructions
  Extract: stages, vocab, scenarios            No structured extraction
  Typed output: InterviewResult                No typed schema
       │                                               │
       ▼                                               ▼
  DISSECT activity                             (none)
  Map to consequence taxonomy                  Operator decides consequence
  inject_fault support for testing             rules manually (if at all)
  Correction loop if wrong                     No correction signal
       │                                               │
       ▼                                               ▼
  CONSTRUCT activity                           (none)
  Build agent-spec.json                        No config bundle generated
  Build flow-spec.json                         No versioned artifact
  Build vocab.json                             No tool allowlist derived
       │                                               │
       ▼                                               ▼
  VALIDATE activity                            (none)
  Schema check + invariant check               No validation step
  Returns ValidationResult                     CLAUDE.md is trusted as-is
       │                                               │
       ▼                                               ▼
  await_promote  (human signal)                Human edits CLAUDE.md directly
  Operator reviews, corrects, approves         (no approval gate, no signal)
       │                                               │
       ▼                                               ▼
  PROMOTE activity                             CLAUDE.md takes effect on
  Writes bundle to config store                next conversation turn
  One-click, audited, version-pinned           No versioning, no audit trail
```

---

## 3. Gap Analysis

```
┌─────────────────────────────────────┬──────────────────────────────────┬──────────────────────────────────┐
│ Dimension                           │ Temporal Harness                 │ Claude Code                      │
├─────────────────────────────────────┼──────────────────────────────────┼──────────────────────────────────┤
│ Durability                          │ Full event sourcing + replay     │ Stateless; Workflow tool is       │
│                                     │ Survives any failure             │ partial (script, not full ES)    │
│                                     │                                  │                                  │
│ Loop termination                    │ Explicit: budget / stall /       │ Implicit: final text output or   │
│                                     │ goal / signal                    │ context exhaustion               │
│                                     │                                  │                                  │
│ Tool consequence model              │ R / C / I classification         │ None — permission mode is        │
│                                     │ Gate + compensation built in     │ coarse (auto/prompt/plan)        │
│                                     │                                  │                                  │
│ Commissioning                       │ Explicit durable workflow        │ None — CLAUDE.md is              │
│                                     │ Human-approved bundle            │ hand-authored                    │
│                                     │                                  │                                  │
│ Config / instructions               │ Versioned JSON bundle            │ CLAUDE.md + memory files         │
│                                     │ Derived from business interview  │ Written by human directly        │
│                                     │                                  │                                  │
│ Memory                              │ Four faces, DB-backed, durable   │ Three layers, context ephemeral  │
│                                     │ Vector search (cosine)           │ No vector search                 │
│                                     │                                  │                                  │
│ Inference / model routing           │ [PROD] Allowlisted, API via LiteLLM     │ [DEV] Direct Anthropic API             │
│                                     │ [PROD] Model-agnostic above contract    │ No routing / no guard            │
│                                     │ [PROD] Small-model-first (cheapest API) │ [DEV] No routing layer                 │
│                                     │                                  │                                  │
│ Multi-agent fan-out                 │ Not yet (Phase E)                │ Agent tool + Workflow tool       │
│                                     │                                  │ Rich subagent type registry      │
│                                     │                                  │                                  │
│ External integrations               │ Not yet (Phase E)                │ MCP server layer                 │
│                                     │                                  │ Playwright, Gmail, Drive, etc.   │
│                                     │                                  │                                  │
│ Plan-before-act                     │ Plan mode in CLAUDE.md law       │ Plan mode (Shift+Tab)            │
│                                     │ (process discipline)             │ (enforced by tool)               │
│                                     │                                  │                                  │
│ Versioning / safe change            │ Temporal versioning APIs         │ None                             │
│                                     │ (patched determinism)            │                                  │
│                                     │                                  │                                  │
│ Operator / user surface             │ Not yet (Phase E)                │ Terminal + IDE + modal           │
│                                     │ Gate approval via signal         │ (built in)                       │
│                                     │                                  │                                  │
│ Observability                       │ Temporal UI (workflows, history) │ /workflows task progress         │
│                                     │ No custom queue viewer yet       │ No business-level metrics        │
│                                     │                                  │                                  │
│ CRM / entity model                  │ Five primitives, five verbs      │ None — free-form tasks only      │
│                                     │                                  │                                  │
│ Hooks / pre-post execution          │ None                             │ User-configurable hooks          │
│                                     │                                  │ (PreToolUse / PostToolUse)       │
└─────────────────────────────────────┴──────────────────────────────────┴──────────────────────────────────┘
```

---

## 4. Artfully Excluded vs Genuinely Missing

### Artfully excluded from the Temporal harness (by design — do not add)

| Excluded | Why it was excluded |
|----------|---------------------|
| Stochastic orchestration (model freely picks next workflow step) | [PROD] Determinism boundary: workflow logic must be replay-safe. Model lives in activities only. |
| Ephemeral context as the memory | [PROD] Business data must survive worker restarts and process death. |
| Arbitrary shell execution (Bash equivalent) | [PROD] Activities are typed, idempotent, consequence-classified. An open shell escapes all three. |
| Direct provider SDK calls in activities (naming a model or provider above the contract) | [PROD] All inference goes through `infer()` → LiteLLM → the configured external API provider. The guard enforces the configured model-id allowlist at the seam; no activity names a provider SDK directly (Invariant 2). |
| Self-modifying config or workflow code | [PROD] Invariants 1 and 5. Adaptation is config data, not code mutation. |
| General-purpose tool registry (tools registered by the model) | [PROD] Invariant 4: tools register; existing workflows never edited to admit them. Allowlist owns the gate. |

### Artfully excluded from Claude Code (by design — do not expect it)

| Excluded | Why |
|----------|-----|
| Durable execution / full event sourcing | [DEV] General-purpose coding assistant — stateless simplicity is correct for the use case. |
| Business entity model | [DEV] Not a CRM. Tasks and files cover 99% of software engineering work. |
| Commissioning workflow | [DEV] CLAUDE.md and memory files are the human's direct expression of intent — no mediation needed. |
| Consequence-class gating | [DEV] Permission modes serve the purpose at the right granularity for a dev tool. |
| Local inference | [DEV] The assistant IS the model — routing to a local model server would be incoherent. (The product harness is also API-only now; neither side runs local inference.) |

### Genuinely missing from the Temporal harness (gaps to close in Phase E+)

| Missing | Phase |
|---------|-------|
| [PROD] Multi-agent fan-out (supervisor / worker agent teams) | Phase E |
| [PROD] External integrations (email, calendar, phone connectors) | Phase E |
| [PROD] Operator queue UI (approve/reject/pause without raw signal calls) | Phase E |
| [PROD] Hooks / pre-post activity execution callbacks | Phase F (TBD) |
| [PROD] Custom observability dashboard (business metrics, not just Temporal UI) | Phase F (TBD) |
| [PROD] Versioning discipline on activities (Temporal version API usage) | Phase E (needed before any live workflow migration) |

### Genuinely missing from Claude Code that the Temporal harness has

| Missing from CC | What it would enable |
|-----------------|---------------------|
| Consequence-class tool classification | Prevent irreversible actions without explicit user approval per action type |
<!-- [NOTE] dev-tool feature, not a product gap -->
| Durable loop state (survives context compaction) | Long-running autonomous tasks that survive session boundaries |
<!-- [NOTE] dev-tool feature, not a product gap -->
| Commissioning — deriving config from a business description | Reproducible, audited agent instructions instead of hand-authored CLAUDE.md |
<!-- [NOTE] dev-tool feature, not a product gap -->
| Vector knowledge search | Retrieval-augmented decision making from a large knowledge corpus |
<!-- [NOTE] dev-tool feature, not a product gap -->
| Idempotency on tool execution | Safe retry without duplicate side effects |
<!-- [NOTE] dev-tool feature, not a product gap -->

---

## 5. One-Line Summary

> **Temporal harness**: durable, typed, consequence-aware, business-encoded, with all inference routed through a guarded contract to a configured API provider — built for a process that runs forever without a human watching.
>
> **Claude Code**: flexible, ephemeral, model-centric, general-purpose — built for a human who is watching and can redirect at any turn.
>
> The core architectural difference is **who holds the loop**. In the Temporal harness, Temporal holds the loop and the model is a narrow tool inside an activity. In Claude Code, the model holds the loop and everything else is a tool it can call.
