"""Unit tests for gate_decision() — consequence-gate pure decision helper.

All tests are pure function calls: no I/O, no fixtures, no mocking.
Run with: python -m pytest tests/test_phase_e_gate.py -v
"""
from __future__ import annotations

import json
import pathlib

import pytest

from harness.operations.molecules.gate import gate_decision

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GATED_FULL = {
    "by_consequence_class": {
        "reversible": "auto",
        "compensable": "approve",
        "irreversible": "approve",
    },
    "by_tool": {},
}

_AUTONOMOUS_FULL = {
    "by_consequence_class": {
        "reversible": "auto",
        "compensable": "auto",
        "irreversible": "approve",
    },
    "by_tool": {},
}


# ---------------------------------------------------------------------------
# 1. Shadow mode — always "auto" regardless of class or config
# ---------------------------------------------------------------------------

class TestShadowMode:
    def test_shadow_reversible(self):
        assert gate_decision("reversible", _GATED_FULL, "shadow") == "auto"

    def test_shadow_compensable(self):
        assert gate_decision("compensable", _GATED_FULL, "shadow") == "auto"

    def test_shadow_irreversible(self):
        assert gate_decision("irreversible", _GATED_FULL, "shadow") == "auto"

    def test_shadow_empty_config(self):
        assert gate_decision("irreversible", {}, "shadow") == "auto"

    def test_shadow_unknown_class(self):
        assert gate_decision("nuclear_launch", {}, "shadow") == "auto"

    def test_shadow_with_by_tool_override(self):
        """by_tool should NOT override shadow mode — shadow wins."""
        config = {"by_tool": {"some_tool": "approve"}}
        assert gate_decision("reversible", config, "shadow", tool_name="some_tool") == "auto"


# ---------------------------------------------------------------------------
# 2. Gated mode — default matrix
# ---------------------------------------------------------------------------

class TestGatedMode:
    def test_gated_reversible(self):
        assert gate_decision("reversible", _GATED_FULL, "gated") == "auto"

    def test_gated_compensable(self):
        assert gate_decision("compensable", _GATED_FULL, "gated") == "approve"

    def test_gated_irreversible(self):
        assert gate_decision("irreversible", _GATED_FULL, "gated") == "approve"

    def test_gated_empty_config_reversible(self):
        """Empty gates_config falls back to built-in gated matrix."""
        assert gate_decision("reversible", {}, "gated") == "auto"

    def test_gated_empty_config_compensable(self):
        assert gate_decision("compensable", {}, "gated") == "approve"

    def test_gated_empty_config_irreversible(self):
        assert gate_decision("irreversible", {}, "gated") == "approve"

    def test_gated_missing_by_consequence_class_key(self):
        """Config has by_tool but no by_consequence_class; falls back to built-in."""
        config = {"by_tool": {"some_tool": "approve"}}
        assert gate_decision("reversible", config, "gated") == "auto"
        assert gate_decision("compensable", config, "gated") == "approve"


# ---------------------------------------------------------------------------
# 3. Autonomous mode
# ---------------------------------------------------------------------------

class TestAutonomousMode:
    def test_autonomous_reversible(self):
        assert gate_decision("reversible", _AUTONOMOUS_FULL, "autonomous") == "auto"

    def test_autonomous_compensable_is_auto_not_approve(self):
        """Compensable is auto in autonomous mode — key difference from gated."""
        assert gate_decision("compensable", _AUTONOMOUS_FULL, "autonomous") == "auto"

    def test_autonomous_irreversible(self):
        assert gate_decision("irreversible", _AUTONOMOUS_FULL, "autonomous") == "approve"

    def test_autonomous_empty_config_compensable(self):
        """Empty config + autonomous: built-in autonomous matrix (compensable=auto)."""
        assert gate_decision("compensable", {}, "autonomous") == "auto"

    def test_autonomous_empty_config_irreversible(self):
        assert gate_decision("irreversible", {}, "autonomous") == "approve"

    def test_autonomous_empty_config_reversible(self):
        assert gate_decision("reversible", {}, "autonomous") == "auto"


# ---------------------------------------------------------------------------
# 4. by_tool overrides
# ---------------------------------------------------------------------------

class TestByToolOverrides:
    def test_by_tool_upgrades_compensable_to_auto(self):
        """by_tool says auto for this tool even though compensable class -> approve."""
        config = {
            "by_consequence_class": {"compensable": "approve"},
            "by_tool": {"cheap_action": "auto"},
        }
        assert gate_decision("compensable", config, "gated", tool_name="cheap_action") == "auto"

    def test_by_tool_downgrades_reversible_to_approve(self):
        """by_tool says approve for this tool even though reversible class -> auto."""
        config = {
            "by_consequence_class": {"reversible": "auto"},
            "by_tool": {"risky_read": "approve"},
        }
        assert gate_decision("reversible", config, "autonomous", tool_name="risky_read") == "approve"

    def test_tool_not_in_by_tool_falls_through(self):
        """Tool name present in call but not in by_tool: falls through to by_consequence_class."""
        config = {
            "by_consequence_class": {"compensable": "approve"},
            "by_tool": {"other_tool": "auto"},
        }
        assert gate_decision("compensable", config, "gated", tool_name="unlisted_tool") == "approve"

    def test_empty_tool_name_does_not_match_by_tool(self):
        """Empty tool_name string should not trigger by_tool lookup."""
        config = {
            "by_consequence_class": {"reversible": "auto"},
            "by_tool": {"": "approve"},  # edge case: empty string key in config
        }
        # tool_name="" should NOT match — guard is `if tool_name and ...`
        assert gate_decision("reversible", config, "gated", tool_name="") == "auto"

    def test_by_tool_overrides_regardless_of_autonomy_level(self):
        """by_tool override applies in both gated and autonomous modes."""
        config = {"by_tool": {"send_email": "approve"}}
        assert gate_decision("reversible", config, "gated", tool_name="send_email") == "approve"
        assert gate_decision("reversible", config, "autonomous", tool_name="send_email") == "approve"


# ---------------------------------------------------------------------------
# 5. Config is authoritative — by_consequence_class overrides built-in
# ---------------------------------------------------------------------------

class TestConfigAuthority:
    def test_config_overrides_gated_compensable_to_auto(self):
        """Config says compensable=auto; built-in gated says approve. Config wins."""
        config = {"by_consequence_class": {"compensable": "auto"}}
        assert gate_decision("compensable", config, "gated") == "auto"

    def test_config_overrides_autonomous_irreversible_to_auto(self):
        """Config says irreversible=auto; built-in autonomous says approve. Config wins."""
        config = {"by_consequence_class": {"irreversible": "auto"}}
        assert gate_decision("irreversible", config, "autonomous") == "auto"

    def test_config_partial_coverage_uses_builtin_for_missing(self):
        """Config covers reversible only; compensable not in config -> uses built-in."""
        config = {"by_consequence_class": {"reversible": "auto"}}
        # compensable not in config, gated fallback -> approve
        assert gate_decision("compensable", config, "gated") == "approve"

    def test_config_can_set_reversible_to_approve(self):
        """Config may choose to be more restrictive than the built-in defaults."""
        config = {"by_consequence_class": {"reversible": "approve"}}
        assert gate_decision("reversible", config, "gated") == "approve"


# ---------------------------------------------------------------------------
# 6. Unknown / open-set values — fail-safe approve
# ---------------------------------------------------------------------------

class TestFailSafe:
    def test_unknown_consequence_class_not_in_config(self):
        """Consequence class unknown to config and built-in -> approve."""
        assert gate_decision("nuclear_launch", {}, "gated") == "approve"

    def test_unknown_consequence_class_in_autonomous_not_in_builtin(self):
        assert gate_decision("quantum_entanglement", {}, "autonomous") == "approve"

    def test_unknown_autonomy_level_treated_as_gated(self):
        """Unrecognised autonomy level falls into the else branch (gated/fail-safe)."""
        # reversible -> auto in default matrix
        assert gate_decision("reversible", {}, "supercharged") == "auto"
        # compensable -> approve in default matrix (fail-safe)
        assert gate_decision("compensable", {}, "supercharged") == "approve"

    def test_unknown_autonomy_level_unknown_class(self):
        """Both autonomy level and consequence class unknown -> approve."""
        assert gate_decision("unknown_class", {}, "unknown_level") == "approve"

    def test_irreversible_unknown_autonomy_level(self):
        """Irreversible with unknown autonomy level -> approve (fail-safe)."""
        assert gate_decision("irreversible", {}, "ultra_trusted") == "approve"


# ---------------------------------------------------------------------------
# 7. Real agent-spec gates block (lead-qualifier-v0.json)
# ---------------------------------------------------------------------------

def _load_agent_gates() -> dict:
    """Load gates block from the real agent spec config file."""
    config_path = (
        pathlib.Path(__file__).parent.parent
        / "config"
        / "bundle-v0"
        / "agents"
        / "lead-qualifier-v0.json"
    )
    with config_path.open() as fh:
        spec = json.load(fh)
    return spec["gates"], spec.get("autonomy_level", "gated")


class TestRealAgentSpec:
    """Integration-style tests using the actual lead-qualifier-v0.json config."""

    def setup_method(self):
        self.gates, self.autonomy_level = _load_agent_gates()

    def test_real_spec_reversible_auto(self):
        assert gate_decision("reversible", self.gates, self.autonomy_level) == "auto"

    def test_real_spec_compensable_approve(self):
        assert gate_decision("compensable", self.gates, self.autonomy_level) == "approve"

    def test_real_spec_irreversible_approve(self):
        assert gate_decision("irreversible", self.gates, self.autonomy_level) == "approve"

    def test_real_spec_transition_state_approve_via_by_tool(self):
        """transition_state is in by_tool -> approve, even if class would be auto."""
        assert (
            gate_decision(
                "reversible",
                self.gates,
                self.autonomy_level,
                tool_name="transition_state",
            )
            == "approve"
        )

    def test_real_spec_transition_state_compensable_approve(self):
        """by_tool takes precedence; compensable + transition_state -> approve."""
        assert (
            gate_decision(
                "compensable",
                self.gates,
                self.autonomy_level,
                tool_name="transition_state",
            )
            == "approve"
        )

    def test_real_spec_record_event_not_in_by_tool(self):
        """record_event is NOT in by_tool; falls through to by_consequence_class."""
        # reversible -> auto from by_consequence_class
        assert (
            gate_decision(
                "reversible",
                self.gates,
                self.autonomy_level,
                tool_name="record_event",
            )
            == "auto"
        )

    def test_real_spec_autonomy_level_is_gated(self):
        """Confirm the loaded autonomy_level is 'gated' as specified in the JSON."""
        assert self.autonomy_level == "gated"
