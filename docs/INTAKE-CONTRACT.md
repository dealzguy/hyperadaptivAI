# INTAKE-CONTRACT.md — normalized intake event and adapter interface

*Written at Phase B per Doc 13 §Phase B build documents.*

## Normalized intake event (Doc 12 §5)

The `NormalizedIntakeEvent` is the universal contract between any source channel
and the CRM spine. Defined in `harness/shared/contracts/intake.py`.

| Field | Type | Description |
|---|---|---|
| `source_channel` | `str` | Identifier of the originating channel (e.g. `"web_form"`) |
| `raw_payload_ref` | `str` | Reference to the raw payload (e.g. form ID) — for traceability |
| `identity_candidates` | `dict` | Open set of identity signals (email, phone, etc.) |
| `captured_attributes` | `dict` | All other channel-supplied fields |
| `source_timestamp` | `str` | ISO-8601; captured at the adapter boundary, threaded as data |
| `consent_flags` | `dict` | Open set of consent/compliance signals (default `{}`) |

[PROD] All extensible fields (`identity_candidates`, `captured_attributes`,
`consent_flags`) are open-set dicts — never closed enumerations (invariant 3 — [PROD]).
This means new fields from any channel flow through without a schema change.

[PROD] `source_timestamp` is captured by the adapter (outside the Temporal workflow)
and threaded as data. It is never generated inside the workflow — that would
violate the determinism boundary (invariant 5 — [PROD]). The DB column `occurred_at`
in the event table is set from this value; server-side `now()` is used only
for bookkeeping timestamps (`created_at`).

## Adapter interface

The `IntakeAdapter` Protocol defines one method:

```python
def normalize(self, raw: dict) -> NormalizedIntakeEvent: ...
```

[PROD] Channels are an **open set** of config-registered adapters — new channels
register a new adapter class; the contract and the CRM spine are never
edited to accommodate a new channel (additive rule, invariant 4 — [PROD]).

Phase B ships one adapter: `WebFormAdapter` in `harness/shared/intake/webform.py`.

## Idempotency key derivation discipline

[PROD] The molecule (`harness/shared/molecules/intake.py`) derives all four
idempotency keys from the normalized event. [PROD] **Keys are the only values that
cross activity boundaries** — never raw UUIDs or live timestamps. This
simultaneously kills the cross-boundary UUID serialization hazard, the
match-or-create TOCTOU race, and enables exact-once idempotency across all
four tables on re-run.

| Verb | Key derivation | Stable inputs |
|---|---|---|
| `create_entity` | `sha256(canonical(identity_candidates))[:32]` | identity_candidates |
| `record_event` | `sha256(entity_key + ":" + source_channel + ":" + raw_payload_ref)[:32]` | entity_key, channel, payload ref |
| `transition_state` | `sha256(entity_key + ":" + machine + ":" + position)[:32]` | entity_key, machine name, target position |
| `assign_task` | `sha256(entity_key + ":" + task_type + ":" + event_key)[:32]` | entity_key, task type, event key |

[PROD] None of these keys includes `workflow.now()`, `uuid4()`, or any wall-clock value
generated inside the workflow. The source event's `source_timestamp` is an input
(data), not a workflow-generated timestamp.

[PROD] **Open-set rule:** `identity_candidates` and `captured_attributes` are plain
Python dicts. New identity signals (e.g. a third-party customer ID) are added
as dict entries by the adapter — no code change in the spine or contract.

## Phase B liquid

`TODO(liquid: richer identity resolution — first real corpus, Phase E)`

[PROD] Phase B ships exact-match identity resolution: two events with the same
`identity_candidates` dict resolve to the same entity. Richer resolution
(fuzzy matching, cross-reference lookups, deduplication rules) is deferred
to Phase E when the first real corpus is available. [PROD] This `TODO` is the only
place identity-matching logic will live — the contract seam (`IntakeAdapter`)
ensures it can be upgraded without touching the CRM spine.
