"""Commission contracts — typed I/O dataclasses for the commissioning workflow.

All dataclasses are JSON-serializable (str/int/float/bool/list/dict fields only)
for Temporal default converter safety.  No model names appear in this file —
model_id values are opaque strings that live inside BundleSpec/AgentSpec data
only (Invariant 2).

Stages: interview → dissect → construct → validate → promote

See also:
  docs/CONFIG-BUNDLE-SPEC.md   — normative agent/flow/vocab/manifest field tables
  docs/INTERVIEW-PROTOCOL.md   — Stage 0 traversal order and stub mapping rules
  docs/DISSECTION.md           — primitive mapping, archetype/switches, rule lifting
  docs/VALIDATION.md           — tier ladder, compensation policy
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Stage 0: Interview ────────────────────────────────────────────────────────

@dataclass
class ContextFrame:
    """Business context extracted during the interview stage.

    Provenance format: {"source": "fixture:<path>", "path": "$.<json-path>"}
    """
    operator_id: str                        # e.g. "meridian-realty-v0"
    business_name: str
    what_is_sold: str
    sold_to_whom: str
    lifecycle_stages: list[str]             # open set — append never edit
    revenue_concentration: str
    exceptions_that_matter: list[str]
    version: int = 0                        # bumped on correction
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsequenceTaxonomy:
    """Maps tool names to consequence classes.

    consequence_class values are open strings: "reversible" | "compensable" |
    "irreversible" — NOT a Python enum (Invariant 3).
    """
    by_tool: dict[str, str]                 # tool_name -> consequence_class string
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioCard:
    """A single business scenario walked from a real deal shape."""
    card_id: str                            # "card-01" … "card-05" (min 5, max 10)
    title: str
    narrative: str
    expected_stages: list[str]              # stage path the card must traverse
    expected_outcome: str                   # must be a value in vocab stages (open set)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class InterviewResult:
    """Output of the interview activity (Stage 0)."""
    context_frame: ContextFrame
    consequence_taxonomy: ConsequenceTaxonomy
    scenario_cards: list[ScenarioCard]      # 5–10 cards; enforced by validate stage
    frame_readback: str                     # read-back in operator vocabulary


# ── Stage 1: Dissect ──────────────────────────────────────────────────────────

@dataclass
class CalculationRule:
    """A deterministic scoring/calculation rule lifted from real fixture artifacts."""
    rule_id: str
    description: str
    expression: str                         # e.g. "score = 2*budget_match + 1*timeline_match"
    test_vectors: list[dict[str, Any]]      # [{"inputs": {...}, "expected": <value>}]
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class PrimitiveMapping:
    """Maps an operator-vocabulary concept to one of the five CRM primitives."""
    source_concept: str                     # operator vocab, e.g. "buyer enquiry"
    primitive: str                          # open string: "entity"|"relationship"|"event"|"state"|"task"
    target_name: str                        # e.g. "lead", "lead_lifecycle", "first_follow_up"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class DissectionResult:
    """Output of the dissect activity (Stage 1)."""
    primitive_mappings: list[PrimitiveMapping]
    archetype: str                          # e.g. "lead_qualification"
    switches: dict[str, Any]                # {"autonomy_level": "gated", "escalate_to": "human_task", ...}
    calculation_rules: list[CalculationRule]    # >= 1, with real test vectors from fixture
    consequence_taxonomy: ConsequenceTaxonomy   # frame taxonomy, possibly corrected
    round: int = 0                          # dissect round: 0 = first pass; bumped on correction
    fault_injected: bool = False            # discipline-test marker, recorded in provenance trail
    provenance: dict[str, Any] = field(default_factory=dict)


# ── Stage 2: Construct ────────────────────────────────────────────────────────

@dataclass
class BundleSpec:
    """Normative bundle schema — reverse-engineered from config/bundle-v0/.

    See docs/CONFIG-BUNDLE-SPEC.md for full field tables.
    model_id values inside agents/flows are DATA (opaque strings); this dataclass
    never imports or names any model (Invariant 2).
    """
    bundle_id: str                          # "bundle-{operator_id}"
    agents: dict[str, dict[str, Any]]       # filename-stem -> agent JSON object (13 fields per bundle-v0)
    flows: dict[str, dict[str, Any]]        # filename-stem -> flow JSON object (8 fields per bundle-v0)
    vocab: dict[str, dict[str, Any]]        # "stages"/"task_types"/"channels"/... ->
                                            #   {"_note": "Open set …", "<key>": [...]}
    tiers_run: list[str] = field(default_factory=list)      # e.g. ["tier0"]
    provenance: dict[str, Any] = field(default_factory=dict)  # which dissect round produced it


# ── Stage 3: Validate ─────────────────────────────────────────────────────────

@dataclass
class ValidateActivityResult:
    """Output of the validate activity (Stage 3)."""
    passed: bool
    tiers_run: list[str]                    # ["tier0"]; higher tiers recorded absent with reason
    tiers_skipped: dict[str, str]           # {"tier1": "no linked intake→outcome history", ...}
    failures: list[str]                     # empty when passed; includes offending field path when not
    report: dict[str, Any]


# ── Stage 4: Promote ─────────────────────────────────────────────────────────

@dataclass
class PromoteActivityResult:
    """Output of the promote activity (Stage 4)."""
    bundle_path: str                        # absolute: {output_root}/bundle-{operator_id}


# ── Top-level workflow I/O ────────────────────────────────────────────────────

@dataclass
class CommissioningInput:
    """Input to CommissioningWorkflow."""
    operator_id: str                        # e.g. "meridian-realty-v0"
    fixture_path: str                       # "fixtures/commission_fixture_01.json"
    auto_advance_dissect: bool = True       # False => wait for advance_stage/submit_correction signal
    inject_fault: bool = False              # discipline test: dissect round 0 emits wrong consequence_class
    golden_bundle_path: str = "config/bundle-v0"    # validate compares structure against this
    output_root: str = "config"             # promote writes to {output_root}/bundle-{operator_id}/
    auto_promote: bool = False              # absent explicit policy, promote waits for approve_promote signal
    idempotency_key: str = ""


@dataclass
class CommissioningResult:
    """Result returned by CommissioningWorkflow.run()."""
    operator_id: str
    final_stage: str                        # "promoted"
    bundle_path: str                        # absolute path written by promote
    dissect_rounds: int
    corrections_applied: list[dict[str, Any]]   # [{"stage": "dissect", "correction": {...}, "round": 1}]
    tiers_run: list[str]
    validation_report: dict[str, Any]


# ── Serialization helpers ─────────────────────────────────────────────────────

def bundle_spec_to_files(spec: BundleSpec) -> dict[str, dict[str, Any]]:
    """Expand a BundleSpec into the file layout written by promote.

    Returns a mapping: relative_path -> JSON-serializable dict.

    Layout:
      agents/<stem>.json
      flows/<stem>.json
      vocab/<key>.json
      manifest.json
    """
    files: dict[str, dict[str, Any]] = {}

    for stem, agent_obj in spec.agents.items():
        files[f"agents/{stem}.json"] = agent_obj

    for stem, flow_obj in spec.flows.items():
        files[f"flows/{stem}.json"] = flow_obj

    for key, vocab_obj in spec.vocab.items():
        files[f"vocab/{key}.json"] = vocab_obj

    files["manifest.json"] = {
        "bundle_id": spec.bundle_id,
        "tiers_run": spec.tiers_run,
        "provenance": spec.provenance,
    }

    return files


def load_bundle_dir(path: str) -> BundleSpec:
    """Load a bundle from an on-disk directory written by promote.

    Reads agents/*.json, flows/*.json, vocab/*.json, manifest.json and
    reconstructs a BundleSpec.  Used by validate, promote, and tests.
    """
    import json
    import os

    agents: dict[str, dict[str, Any]] = {}
    flows: dict[str, dict[str, Any]] = {}
    vocab: dict[str, dict[str, Any]] = {}

    agents_dir = os.path.join(path, "agents")
    if os.path.isdir(agents_dir):
        for fname in sorted(os.listdir(agents_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(agents_dir, fname)) as fh:
                    agents[fname[:-5]] = json.load(fh)

    flows_dir = os.path.join(path, "flows")
    if os.path.isdir(flows_dir):
        for fname in sorted(os.listdir(flows_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(flows_dir, fname)) as fh:
                    flows[fname[:-5]] = json.load(fh)

    vocab_dir = os.path.join(path, "vocab")
    if os.path.isdir(vocab_dir):
        for fname in sorted(os.listdir(vocab_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(vocab_dir, fname)) as fh:
                    vocab[fname[:-5]] = json.load(fh)

    manifest: dict[str, Any] = {}
    manifest_path = os.path.join(path, "manifest.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path) as fh:
            manifest = json.load(fh)

    return BundleSpec(
        bundle_id=manifest.get("bundle_id", ""),
        agents=agents,
        flows=flows,
        vocab=vocab,
        tiers_run=manifest.get("tiers_run", []),
        provenance=manifest.get("provenance", {}),
    )
