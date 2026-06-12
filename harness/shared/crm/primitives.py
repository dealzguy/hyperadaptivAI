"""CRM primitive row shapes and verb I/O dataclasses.

All fields are JSON-native (str for IDs/timestamps, dict for jsonb, int for seq).
This allows the Temporal default data converter to serialize/deserialize without
a Pydantic converter or SDK bump — safely crossing activity boundaries.

Row shapes: EntityRow, RelationshipRow, EventRow, StateRow, TaskRow.
Verb I/O:   Create*, Relate*, RecordEvent*, TransitionState*, AssignTask* pairs.

TODO(liquid: Pydantic data converter + temporalio >= 1.11) — Phase C, when typed
money/datetime DTOs land and stricter validation at boundaries is warranted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── Row shapes ────────────────────────────────────────────────────────────────


@dataclass
class EntityRow:
    id: str              # uuid serialized as str
    type: str
    attributes: dict
    idempotency_key: str
    created_at: str      # ISO-8601 from DB


@dataclass
class RelationshipRow:
    id: str
    type: str
    from_entity_id: str
    to_entity_id: str
    attributes: dict
    idempotency_key: str
    created_at: str


@dataclass
class EventRow:
    id: str
    type: str
    entity_id: str
    idempotency_key: str
    occurred_at: str
    created_at: str
    actor: str = ""
    payload: dict = field(default_factory=dict)


@dataclass
class StateRow:
    id: str
    entity_id: str
    machine: str
    position: str
    idempotency_key: str
    created_at: str
    seq: int
    attributes: dict = field(default_factory=dict)


@dataclass
class TaskRow:
    id: str
    type: str
    entity_id: str
    idempotency_key: str
    status: str
    created_at: str
    assignee: str = ""
    attributes: dict = field(default_factory=dict)


# ── Verb I/O dataclasses ─────────────────────────────────────────────────────
# Input/output dataclasses for the five verb activities.
# These are imported by molecules (for type refs) AND by verbs.py (for logic).
# asyncpg is never imported from this module.

@dataclass
class CreateEntityInput:
    entity_type: str
    attributes: dict
    idempotency_key: str


@dataclass
class CreateEntityOutput:
    id: str
    idempotency_key: str
    created: bool          # True = new row; False = pre-existing (idempotent re-run)


@dataclass
class RelateInput:
    relation_type: str
    from_entity_id: str
    to_entity_id: str
    attributes: dict
    idempotency_key: str


@dataclass
class RelateOutput:
    id: str
    idempotency_key: str
    created: bool


@dataclass
class RecordEventInput:
    event_type: str
    entity_id: str
    payload: dict
    occurred_at: str       # ISO-8601 str; supplied by caller, not generated here
    idempotency_key: str
    actor: str = ""


@dataclass
class RecordEventOutput:
    id: str
    idempotency_key: str
    created: bool


@dataclass
class TransitionStateInput:
    entity_id: str
    machine: str
    position: str
    attributes: dict
    idempotency_key: str


@dataclass
class TransitionStateOutput:
    id: str
    idempotency_key: str
    created: bool


@dataclass
class AssignTaskInput:
    task_type: str
    entity_id: str
    attributes: dict
    idempotency_key: str
    assignee: str = ""
    status: str = "open"


@dataclass
class AssignTaskOutput:
    id: str
    idempotency_key: str
    created: bool
