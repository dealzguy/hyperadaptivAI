"""Web-form intake adapter.

Maps a raw web-form submission dict to a NormalizedIntakeEvent.
identity_candidates are lifted from email/phone fields; all other fields
go into captured_attributes. source_timestamp defaults to the submitted_at
field if present, otherwise falls back to now() — captured here at the
adapter boundary, never inside the workflow (determinism rule).
"""
from __future__ import annotations

from datetime import datetime, timezone

from harness.shared.contracts.intake import IntakeAdapter, NormalizedIntakeEvent


class WebFormAdapter:
    """Adapter for web-form submissions. Implements IntakeAdapter."""

    def normalize(self, raw: dict) -> NormalizedIntakeEvent:
        identity: dict = {}
        if "email" in raw:
            identity["email"] = str(raw["email"]).strip().lower()
        if "phone" in raw:
            identity["phone"] = str(raw["phone"]).strip()

        captured = {k: v for k, v in raw.items() if k not in ("email", "phone", "submitted_at", "form_id", "consent")}

        return NormalizedIntakeEvent(
            source_channel="web_form",
            raw_payload_ref=str(raw.get("form_id", "")),
            identity_candidates=identity,
            captured_attributes=captured,
            source_timestamp=raw.get(
                "submitted_at",
                datetime.now(timezone.utc).isoformat(),
            ),
            consent_flags=dict(raw.get("consent", {})),
        )
