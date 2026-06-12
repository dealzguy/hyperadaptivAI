"""Block schema contract — Doc 12 §8.

A Block is pure metadata describing an activity/tool in the harness.
It does NOT hold the callable — keeping this module free of asyncpg and
safe to reference from workflow-side code without sandbox contamination.

compensation_handler is a Phase C liquid: Doc 12 §8 requires a handler only
"where compensable." All Phase B blocks are consequence_class=reversible
(side-effect-free internal DB appends, no external actuation), so the
compensable clause is not triggered and no field is added yet.
TODO(liquid: compensation_handler field on Block + reversing-transition blocks)
— Phase C, arriving with the first compensable block.
"""
from __future__ import annotations

from dataclasses import dataclass


class ConsequenceClass:
    """Three-value taxonomy per Doc 12 §8. Drives Phase C gate placement."""
    REVERSIBLE = "reversible"
    COMPENSABLE = "compensable"
    IRREVERSIBLE = "irreversible"


@dataclass(frozen=True)
class Block:
    """Block metadata per Doc 12 §8.

    Fields:
        name             Registered activity name (matches @activity.defn name).
        input_type       Qualified name of the input dataclass.
        output_type      Qualified name of the output dataclass.
        idempotent       True — all Phase B blocks write via ON CONFLICT DO NOTHING.
        consequence_class ConsequenceClass constant.
        version          SemVer pin for this block definition.
    """
    name: str
    input_type: str
    output_type: str
    idempotent: bool
    consequence_class: str
    version: str
