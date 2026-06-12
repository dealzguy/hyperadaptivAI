"""promote_activity — Stage 4 of commissioning: write the certified BundleSpec
to the config directory on disk.

Consequence class: COMPENSABLE (writes files; can be compensated by deleting
or overwriting the bundle directory).
Idempotent: True — deterministic content, overwrite-in-place; re-running with
the same inputs produces bit-for-bit identical output.

Compensation handler: remove or overwrite the bundle directory
({output_root}/bundle-{operator_id}/).

Invariant 6: config stays config — bundle written under config/, NEVER into
harness/.  The output_root parameter defaults to "config" but the caller is
responsible for providing an absolute or project-relative path.

Invariant 3: no closed enumerations — all file keys (agents/, flows/, vocab/)
are derived from BundleSpec contents, not from a hardcoded list.

Uses bundle_spec_to_files() from commission contracts to decouple file-layout
logic from the write loop.

See docs/CONFIG-BUNDLE-SPEC.md for the normative on-disk layout.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from temporalio import activity

from harness.shared.capability.registry import register
from harness.shared.contracts.block import Block, ConsequenceClass
from harness.shared.contracts.commission import (
    BundleSpec,
    PromoteActivityResult,
    ValidateActivityResult,
    bundle_spec_to_files,
)

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


@dataclass
class PromoteActivityInput:
    bundle: BundleSpec
    validation: ValidateActivityResult
    output_root: str
    operator_id: str
    idempotency_key: str = ""


@activity.defn(name="commission_promote")
async def promote_activity(inp: PromoteActivityInput) -> PromoteActivityResult:
    """Stage 4: write certified bundle files to {output_root}/bundle-{operator_id}/.

    Raises ApplicationError(non_retryable=True) if the bundle failed validation
    (validation.passed is False).  A failed-cert bundle must never be promoted.

    On success returns the absolute bundle_path.

    Compensation: caller can remove the bundle directory if the commissioning
    workflow is rolled back.  File writes are deterministic so re-running is
    always safe (Invariant idempotent=True).
    """
    from temporalio.exceptions import ApplicationError

    if not inp.validation.passed:
        raise ApplicationError(
            f"promote_activity: refusing to promote uncertified bundle "
            f"'{inp.bundle.bundle_id}' — validation failures: "
            f"{inp.validation.failures}",
            non_retryable=True,
        )

    bundle_dir = os.path.join(inp.output_root, f"bundle-{inp.operator_id}")

    # Expand BundleSpec to file layout (relative_path -> dict).
    file_map: dict[str, dict[str, Any]] = bundle_spec_to_files(inp.bundle)

    # Write each file, creating parent directories as needed.
    written: list[str] = []
    for rel_path, content in file_map.items():
        abs_path = os.path.join(bundle_dir, rel_path)
        parent = os.path.dirname(abs_path)
        os.makedirs(parent, exist_ok=True)
        with open(abs_path, "w") as fh:
            json.dump(content, fh, indent=2)
            fh.write("\n")   # POSIX newline at EOF
        written.append(rel_path)

    # Write a richer manifest that includes validation metadata and corrections.
    # The bundle_spec_to_files() call above writes a minimal manifest.json;
    # we overwrite it here with the full promote-time record.
    manifest_path = os.path.join(bundle_dir, "manifest.json")
    manifest: dict[str, Any] = {
        "bundle_id": inp.bundle.bundle_id,
        "operator_id": inp.operator_id,
        "tiers_run": inp.validation.tiers_run,
        "tiers_skipped": inp.validation.tiers_skipped,
        "provenance": inp.bundle.provenance,
        "validation_report": inp.validation.report,
    }
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    abs_bundle_dir = os.path.abspath(bundle_dir)

    logger.info(
        "promote_activity operator=%s bundle_dir=%s files_written=%d",
        inp.operator_id,
        abs_bundle_dir,
        len(written) + 1,   # +1 for enriched manifest
    )

    return PromoteActivityResult(bundle_path=abs_bundle_dir)


register(Block(
    name="commission_promote",
    input_type="harness.commissioning.activities.promote.PromoteActivityInput",
    output_type="harness.shared.contracts.commission.PromoteActivityResult",
    idempotent=True,
    consequence_class=ConsequenceClass.COMPENSABLE,
    version=_VERSION,
))
