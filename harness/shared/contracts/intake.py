"""Intake contract — normalized event and adapter interface (Doc 12 §5).

The normalized event is the universal boundary between any source channel
and the CRM spine. All fields that grow (identity_candidates, captured_attributes,
consent_flags) are open-set dicts — never closed enumerations (invariant 3).
source_timestamp is ISO-8601 str captured by the adapter and threaded as data,
never generated inside the workflow (determinism boundary, invariant 5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class NormalizedIntakeEvent:
    """Universal intake event — one shape per channel, all channels."""
    source_channel: str
    raw_payload_ref: str
    identity_candidates: dict   # e.g. {"email": "x@y.com", "phone": "555..."}
    captured_attributes: dict   # all other form/API fields
    source_timestamp: str       # ISO-8601; captured by adapter, threaded as data
    consent_flags: dict = field(default_factory=dict)


@runtime_checkable
class IntakeAdapter(Protocol):
    """Adapter protocol — open set; one implementation per source channel.

    Channels are config-registered; this Protocol is the only seam.
    Identity resolution happens here (once, for all channels).
    """
    def normalize(self, raw: dict) -> NormalizedIntakeEvent:
        ...
