# BLOCKS.md — Phase B block schema, registry rules, and closure check

*Written at Phase B per Doc 13 §Phase B build documents.*

## Block schema (Doc 12 §8)

Each block in the harness carries the following metadata fields, defined in
`harness/shared/contracts/block.py::Block`:

| Field | Type | Purpose |
|---|---|---|
| `name` | `str` | Registered Temporal activity name (matches `@activity.defn` name) |
| `input_type` | `str` | Qualified name of the input dataclass |
| `output_type` | `str` | Qualified name of the output dataclass |
| `idempotent` | `bool` | `True` for all Phase B blocks — write via ON CONFLICT DO NOTHING |
| `consequence_class` | `str` | Reversibility classification (see below) |
| `version` | `str` | SemVer pin for this block definition |

[PROD] `compensation_handler` is deliberately absent in Phase B. Doc 12 §8 requires
a handler **only "where compensable"** — no Phase B block is compensable (all
are `reversible`), so the clause is not triggered. This field is a Phase C
liquid, arriving with the first block that performs external/irreversible
actuation (send-message, charge).
`TODO(liquid: compensation_handler field on Block + reversing-transition blocks)`

## Consequence classes

[PROD] All five Phase B verbs are `consequence_class = reversible`. This is the honest
classification: every verb is a side-effect-free INSERT into the business
Postgres with **no external actuation** (no email, payment, or irreversible
outside effect). The effect is cleanly undoable — nothing in the world has
consumed it. [PROD] Consequence class classifies the **reversibility of the effect**,
not the storage auditability of the write.

[PROD] Note on `transition_state`: the state table is **append-only** (each transition
inserts a new row; no UPDATE-in-place). This is an **audit discipline** choice,
not a consequence-class signal. Append-only preserves history so Phase C's
"replay audit reads true" gate (Doc 12 §9) can be satisfied. But the effect of
the transition is still reversible — a compensating row could undo it. In Phase B
nothing external has consumed the state transition, so `reversible` is correct.

Phase C will bring the first `compensable` class block (send-message,
charge) and with it the compensation handler obligation.

## Phase B block catalog

| Block name | Activity | Input / Output | Consequence |
|---|---|---|---|
| `create_entity` | `crm/verbs.py::create_entity` | `CreateEntityInput` / `CreateEntityOutput` | reversible |
| `relate` | `crm/verbs.py::relate` | `RelateInput` / `RelateOutput` | reversible |
| `record_event` | `crm/verbs.py::record_event` | `RecordEventInput` / `RecordEventOutput` | reversible |
| `transition_state` | `crm/verbs.py::transition_state` | `TransitionStateInput` / `TransitionStateOutput` | reversible |
| `assign_task` | `crm/verbs.py::assign_task` | `AssignTaskInput` / `AssignTaskOutput` | reversible |

All I/O dataclasses are defined in `harness/shared/crm/primitives.py` with
JSON-native field types (str for IDs/timestamps, dict for jsonb) so they cross
Temporal's default data converter without a Pydantic converter or SDK bump.

## Registry rules

The tool registry (`harness/shared/capability/registry.py`) is a module-level
singleton dict keyed by block name. Rules:

1. [PROD] **Additive only.** A registered block is never edited or deleted; new
   capabilities register new blocks. The registry name is permanent.
2. [PROD] **Idempotent re-registration.** `register(block)` is reentrant: re-importing
   a block module (e.g. during Temporal sandbox reload) is a no-op if the
   metadata is identical. Registering the same name with different metadata raises.
3. [PROD] **Metadata only.** The registry holds `Block` metadata objects — never the
   activity callables, never asyncpg. It is safe to reference from workflow-side
   code without sandbox contamination.
4. [PROD] **Populated in worker scope.** Block registration happens at import time in
   `verbs.py`, which is imported by `worker.py`. The workflow discovers blocks by
   string name; it is never edited to add a new block.

[DEV] **Additive rule as CI policy:** any PR that modifies an existing entry in
`_registry` (changes block name, I/O type, consequence class) fails review.
[PROD] New blocks extend the catalog; existing blocks are immutable.

## By-hand closure check — Intake molecule

**Closure claim:** Intake decomposes into `create_entity + record_event +
transition_state + assign_task` with no remainder, and each verb traces to
the Engage-entry shell process (Doc 12 §9). No orphan (no verb whose effect
is unreachable from the shell stage map).

Decomposition trace:
- `create_entity` → match-or-create the entity. Traces to Engage stage entry:
  an entity must exist before it can be engaged.
- `record_event` → record the source intake event as an immutable fact. Traces
  to Engage: the event is evidence that this entity entered the funnel.
- `transition_state` → open the lifecycle state (`position = engage_open`).
  Directly instantiates the Engage stage in the entity's state machine.
- `assign_task` → open the first follow-up task (`first_follow_up`). Justified
  by Doc 12 §9 Operations loop "lead-intake to first-follow-up": the intake
  molecule is the entry point of the first Operations cycle, and opening a
  follow-up task is the minimal handoff to the agent loop.

The `relate` verb is NOT in the Intake molecule — relationship creation is a
separate concern (inter-entity linking) not required at first-touch intake.
`relate` is built, registered, and property-tested in isolation; it is correctly
absent from the Intake molecule's closure, not a remainder.

**No remainder:** every act traces to a stage in the Engage-entry process.
**No orphan:** no act in the molecule is unreachable from the Attract→Engage
entry in the meta-model shell (Doc 12 §3 shell process, v1 entry at Engage).
