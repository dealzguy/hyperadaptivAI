"""Consequence-gate decision helper.

gate_decision(consequence_class, gates_config, autonomy_level, tool_name) -> "auto" | "approve"

Pure, deterministic, workflow-side safe: no I/O, no model calls, no randomness.
Drives the human-approval gate between DECIDE and ACT in AgentLoopWorkflow.

Decision matrix (gates_config takes precedence; by_tool overrides by_consequence_class):

  autonomy_level="shadow":     always "auto" (record-only mode; ACT is skipped by caller)
  autonomy_level="gated":      reversible=auto, compensable=approve, irreversible=approve
  autonomy_level="autonomous": reversible=auto, compensable=auto, irreversible=approve

  by_tool override: if gates_config["by_tool"][tool_name] exists, it overrides the class-level decision.

  If gates_config is empty or missing keys, defaults to the gated-mode matrix above.

[PROD] Config over code: the matrix comes from gates_config (agent spec's gates block), not hardcoded here.
[PROD] No closed enumerations: autonomy levels and consequence classes are open sets.
"""
from __future__ import annotations

_DEFAULT_BY_CLASS = {
    "reversible": "auto",
    "compensable": "approve",
    "irreversible": "approve",
}

_AUTONOMOUS_BY_CLASS = {
    "reversible": "auto",
    "compensable": "auto",
    "irreversible": "approve",
}


def gate_decision(
    consequence_class: str,
    gates_config: dict,
    autonomy_level: str,
    tool_name: str = "",
) -> str:
    """Return "auto" or "approve" for a proposed action.

    Args:
        consequence_class: "reversible", "compensable", "irreversible", or any open-set value
        gates_config: agent spec gates block {"by_consequence_class": {...}, "by_tool": {...}}
        autonomy_level: "shadow", "gated", "autonomous", or any open-set value
        tool_name: optional tool/action name for by_tool override lookup

    Returns:
        "auto"    — proceed immediately
        "approve" — pause and await human resolution

    [PROD] Config over code: gates_config is authoritative; this function is a router.
    [PROD] Unknown consequence_class or autonomy_level defaults to "approve" (fail-safe).
    """
    # Shadow: record-only mode; caller skips ACT entirely; gate is moot but return "auto"
    if autonomy_level == "shadow":
        return "auto"

    by_class = gates_config.get("by_consequence_class", {})
    by_tool = gates_config.get("by_tool", {})

    # by_tool override takes highest precedence
    if tool_name and tool_name in by_tool:
        return by_tool[tool_name]

    # by_consequence_class from config; fall back to built-in matrix
    if consequence_class in by_class:
        return by_class[consequence_class]

    # Built-in fallback matrix (fail-safe: unknown class -> approve)
    if autonomy_level == "autonomous":
        return _AUTONOMOUS_BY_CLASS.get(consequence_class, "approve")
    else:
        # "gated" or any unrecognised autonomy level — fail safe
        return _DEFAULT_BY_CLASS.get(consequence_class, "approve")
