# CONFIG-BUNDLE-SPEC.md — Normative Bundle Schema

**Status:** NORMATIVE. This document defines the authoritative on-disk layout and
field schema for config bundles produced by the commissioning workflow. The golden
reference implementation is `config/bundle-v0/`. All new bundles produced by
`promote_activity` must satisfy the schema defined here.

---

## 1. On-Disk Layout

```
config/bundle-{operator_id}/
  agents/
    {agent-id}.json          # one file per agent (see §2)
  flows/
    {flow-id}.json           # one file per flow (see §3)
  vocab/
    stages.json              # lifecycle state names (see §4)
    task_types.json
    channels.json
    ...                      # open set — append never edit
  manifest.json              # promote-time record (see §5)
```

Software, config, and data stay separate (Invariant 6). Bundle files are written
exclusively under `config/`, never under `harness/`.

---

## 2. Agent Object — 13 Required Fields

Every file under `agents/` must contain exactly these fields (plus any operator-
specific extensions, which are permitted as additional keys):

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique agent identifier, e.g. `"lead-qualifier-v0"`. Must equal the filename stem. Must equal `flow.agent_id` in the corresponding flow. |
| `department` | `str` | Functional department the agent belongs to, e.g. `"engage"`. |
| `role` | `str` | Human-readable role description sentence. |
| `objectives` | `list[str]` | Ordered list of behavioural objectives the agent pursues per run. |
| `tool_allowlist` | `list[str]` | Open set of tool names the agent may call. New tools register via the capability registry; this list is updated in config, never by editing workflow code (Invariant 4). |
| `autonomy_level` | `str` | Open string: `"gated"` requires gate evaluation before consequence-bearing actions; others may be added. |
| `gates` | `dict` | Gate configuration object — see §2.1. |
| `escalation_rules` | `dict` | Keys: `confidence_threshold` (float), `stall_after` (int steps), `escalate_to` (str). |
| `model_policy` | `dict` | Role → model_id mapping — see §model_policy below. Values are opaque strings; no code above the infer contract names a model (Invariant 2). |
| `retrieval_budget` | `int` | Maximum context-retrieval operations per run. |
| `step_budget` | `int` | Maximum agent loop steps per run. |
| `token_budget` | `int` | Maximum tokens consumed per run. |
| `version` | `str` or `int` | Bundle-v0 uses string `"0"`. New bundles may use int. |

### 2.1 gates Object

```json
{
  "by_consequence_class": {
    "reversible":   "auto",
    "compensable":  "approve",
    "irreversible": "approve"
  },
  "by_tool": {
    "transition_state": "approve"
  }
}
```

Derivation rules (implemented in `construct_activity`):

- `by_consequence_class` maps all three standard consequence classes. The mapping
  is fixed: `reversible → "auto"`, `compensable → "approve"`, `irreversible → "approve"`.
- `by_tool` contains **only tools whose consequence class is not "reversible"**.
  `record_event` (reversible) is governed solely by `by_consequence_class` and does
  not appear in `by_tool`. This prevents redundancy and matches the bundle-v0 structure
  where only `transition_state` (compensable) appears.
- During validation (Tier 0 golden comparison), all keys present in the golden
  `by_tool` must appear in the emitted bundle's `by_tool`. The emitted bundle may be a
  superset (more restrictive gating is acceptable; less restrictive is not).

### model_policy

```json
{
  "decide":   "ollama_chat/llama3.2:3b",
  "escalate": "ollama_chat/llama3.1:8b"
}
```

**Grammar:** `model_id = "ollama/<name>" | "ollama_chat/<name>"`

- `ollama/<name>` — Ollama text-completion endpoint (legacy completions).
- `ollama_chat/<name>` — Ollama chat-completions endpoint. Required for structured
  outputs and tool-calling models. This is the prefix used by bundle-v0 and all
  new bundles produced by commissioning.

Both prefixes route exclusively to local Ollama via LiteLLM. No cloud provider
prefix is ever permitted. The `_guard_model_id()` function in
`harness/shared/contracts/infer.py` enforces this allowlist at runtime.

**Small-model-first policy (CLAUDE.md):** `decide` tasks use the smallest reliable
model (`llama3.2:3b`); escalation uses a larger model (`llama3.1:8b`) only when
human-level judgment is required. Model choices are data (config), never code.

**Liquid resolution:** The addition of `ollama_chat/` to the guard allowlist was a
liquid that required founder approval. Resolution is recorded in
`docs/LIQUID-RESOLUTIONS.md` ("infer guard prefix set").

---

## 3. Flow Object — 8 Required Fields

Every file under `flows/` must contain exactly these fields:

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique flow identifier, e.g. `"lead-intake-first-follow-up"`. Must equal the filename stem. |
| `version` | `str` | Semver string, e.g. `"0.1.0"`. |
| `description` | `str` | Human-readable one-line description of the flow. |
| `trigger` | `dict` | Must contain `event_type` (str). Additional trigger keys permitted (open). |
| `workflow_type` | `str` | Temporal workflow class to instantiate, e.g. `"AgentLoopWorkflow"`. |
| `agent_id` | `str` | Must exactly match the `id` field of the agent this flow invokes. |
| `workflow_id_template` | `str` | Template for constructing a deterministic Temporal workflow ID, e.g. `"agent-loop-{flow_id}-{entity_key}"`. |
| `goal_payload_template` | `dict` | Goal payload sent to the workflow. Must include `flow_class` (str), `objective` (str), and `tool_arg_schemas` (dict — one entry per allowed tool). |

---

## 4. Vocab Files

Every file under `vocab/` must follow this schema:

```json
{
  "_note": "Open set — append never edit. <optional clarification>",
  "<payload-key>": ["value1", "value2", "..."]
}
```

Rules:

- `_note` is mandatory and must start with the prefix `"Open set — append never edit."`.
  Additional clarification may follow (e.g. `"States used in lead_lifecycle state machine."`).
  Validation uses prefix-match, not exact-match.
- At least one additional list-valued key must be present.
- The key name for the list should match the vocab category (e.g. `stages`, `task_types`,
  `channels`).
- The vocab key set itself is open: new categories are added as new files, never by editing
  existing files (Invariant 3).

### Standard Vocab Categories (bundle-v0 baseline)

| File | Payload Key | Content |
|---|---|---|
| `stages.json` | `stages` | Lifecycle state names for the lead state machine |
| `task_types.json` | `task_types` | CRM task type names the agent may assign |
| `channels.json` | `channels` | Intake channel identifiers |

---

## 5. manifest.json

Written by `promote_activity`. Not present in bundle-v0 (backfill not required;
the golden comparison in Tier 0 explicitly excludes manifest.json). New bundles
always include it.

```json
{
  "bundle_id": "bundle-meridian-realty-v0",
  "operator_id": "meridian-realty-v0",
  "tiers_run": ["tier0"],
  "tiers_skipped": {
    "tier1": "no linked intake→outcome history in fixture (Phase E requires real corpus)",
    "tier2": "no comparable live process available (Phase E requires live telemetry)"
  },
  "provenance": {
    "dissect_round": 0,
    "archetype": "lead_qualification",
    "operator_id": "meridian-realty-v0"
  },
  "validation_report": { ... }
}
```

| Field | Type | Description |
|---|---|---|
| `bundle_id` | `str` | Same as `BundleSpec.bundle_id`. |
| `operator_id` | `str` | Operator identifier. |
| `tiers_run` | `list[str]` | Validation tiers that passed, e.g. `["tier0"]`. |
| `tiers_skipped` | `dict[str,str]` | Absent tiers with human-readable reason. Absent tiers imply longer probation and more gates (see `docs/VALIDATION.md`). |
| `provenance` | `dict` | Which dissect round produced this bundle; archetype used. |
| `validation_report` | `dict` | Full Tier 0 report from `validate_activity`. |

---

## 6. policy Keys (infer contract)

The `policy` field of `InferInput` accepts the following known keys. Unknown keys
are warned about but not rejected (open-set invariant, Invariant 3).

| Key | Type | Constraint | Default |
|---|---|---|---|
| `max_tokens` | `int` | Must be > 0 | Provider default |
| `temperature` | `float` | Must be in `[0.0, 2.0]` | Provider default |

This resolves the `TODO(liquid: policy schema)` markers previously in
`harness/shared/contracts/infer.py`. The set is open for append; unknown keys
produce a warning log entry from `validate_policy()`.

---

## 7. Archetype Catalogue

Archetype names are registered in the `_ARCHETYPE_TEMPLATES` dict in
`harness/commissioning/activities/construct.py`. The dict is an open set;
new archetypes are appended, existing entries are never edited.

| Archetype | Description |
|---|---|
| `lead_qualification` | Intake → qualify/disqualify → first follow-up assignment. Default for residential sales operators. |

---

## 8. Versioning and Promotion

- A bundle produced by commissioning always has `version: "0"` in its agent object.
  Version bumps are made by re-commissioning (config change → re-run the workflow).
- `promote_activity` writes to `{output_root}/bundle-{operator_id}/`. If a bundle
  already exists it is overwritten in-place (idempotent).
- Auto-promote (`CommissioningInput.auto_promote=True`) is only used in test fixtures
  as a stand-in for "explicit written policy". Production workflows wait for the
  `approve_promote` signal (one human click, per CLAUDE.md).
