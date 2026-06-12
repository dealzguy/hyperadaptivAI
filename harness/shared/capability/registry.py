"""Tool registry — typed block catalog (Doc 12 §8, invariant 4).

Module singleton dict keyed by block name. Holds Block METADATA only —
no asyncpg, no activity callables — so it is safe to reference from
workflow-side code without sandbox contamination.

register() is idempotent and reentrant: Temporal sandbox module reload
re-executes import-time code, so registration must tolerate re-registration
with identical metadata silently and raise only on conflicting metadata
(additive rule: existing blocks are never redefined).
"""
from __future__ import annotations

from harness.shared.contracts.block import Block

_registry: dict[str, Block] = {}


def register(block: Block) -> None:
    """Register a block. Idempotent for same metadata; raises on conflict."""
    existing = _registry.setdefault(block.name, block)
    if existing is not block and (
        existing.input_type != block.input_type
        or existing.output_type != block.output_type
        or existing.consequence_class != block.consequence_class
        or existing.version != block.version
    ):
        raise ValueError(
            f"Block {block.name!r} is already registered with different metadata. "
            "The additive rule forbids redefining an existing block — "
            "introduce a versioned block instead."
        )


def get(name: str) -> Block:
    """Retrieve block metadata by name."""
    try:
        return _registry[name]
    except KeyError:
        raise KeyError(
            f"Block {name!r} not registered. "
            "Ensure its module is imported before calling get()."
        ) from None


def list_blocks() -> list[Block]:
    """Return all registered blocks (snapshot)."""
    return list(_registry.values())
