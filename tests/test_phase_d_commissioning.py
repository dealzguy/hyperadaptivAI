"""Phase D exit-gate tests — commissioning workflow (interview → dissect → construct
→ validate → promote) and discipline-test (fault injection + branch rollback).

Gate clauses (Doc 13 §Phase D):
  1. End-to-end: CommissioningWorkflow runs interview→dissect→construct→validate→promote
     with auto_advance_dissect=True; emitted bundle written to disk.
  2. Emitted bundle schema valid: all 13 agent fields, 8 flow fields, vocab _note prefix.
  3. Discipline test: inject_fault=True + auto_advance_dissect=False → provenance locates
     fault at dissect:round0 → submit_correction → round-1 re-run → validate re-certifies
     → promoted bundle has correct gates.
  4. Promoted bundle drives AgentLoopWorkflow: AgentLoopInput constructable from emitted
     bundle; model_policy values pass guard (no cloud prefix).
  5. Phase C regression: all existing tests remain green (run separately).

Unit tests (no live stack required, INFER_STUB=1):
  - test_interview_stub_card_count_bounds
  - test_dissect_fault_injection_round0_only
  - test_dissect_applies_correction
  - test_construct_gates_derived_from_taxonomy
  - test_validate_vector_reproduction_exact
  - test_validate_fails_on_wrong_consequence_class
  - test_guard_accepts_ollama_chat
  - test_guard_rejects_cloud_prefixes
  - test_guard_change_does_not_break_existing_ollama_prefix

Stack required for integration tests:
  temporal server start-dev
  podman compose -f deploy/compose.yaml -f deploy/compose.dev.yaml up -d postgres-business
  python -m harness.shared.persistence.bootstrap
  python -m harness.worker  (separate terminal, INFER_STUB=1 set)

  INFER_STUB=1 TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=5433 \\
    pytest tests/test_phase_d_commissioning.py -m integration -v
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

# ── Env ───────────────────────────────────────────────────────────────────────

os.environ.setdefault("INFER_STUB", "1")

_BASE = Path(__file__).parent.parent   # version1/
_FIXTURE_PATH = str(_BASE / "fixtures" / "commission_fixture_01.json")
_GOLDEN_PATH = str(_BASE / "config" / "bundle-v0")
_TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
_TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "skeleton-queue")


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS — no Temporal, no DB, INFER_STUB=1
# ═══════════════════════════════════════════════════════════════════════════════


def test_guard_accepts_ollama_chat():
    """Guard updated to accept ollama_chat/ prefix (Step 1 fix, now committed)."""
    from harness.shared.contracts.infer import _guard_model_id
    # Should not raise
    _guard_model_id("ollama_chat/llama3.2:3b")
    _guard_model_id("ollama_chat/llama3.1:8b")


def test_guard_change_does_not_break_existing_ollama_prefix():
    """Guard still accepts ollama/ (completion endpoint) after the prefix fix."""
    from harness.shared.contracts.infer import _guard_model_id
    _guard_model_id("ollama/llama3.2:3b")


@pytest.mark.parametrize("bad_model_id", [
    "openai/gpt-4o",
    "anthropic/claude-3",
    "gpt-4",
    "ollama-evil/x",
])
def test_guard_rejects_cloud_prefixes(bad_model_id: str):
    """Guard rejects every cloud provider prefix without enumerating them."""
    from harness.shared.contracts.infer import _guard_model_id
    with pytest.raises(ValueError, match="model_id"):
        _guard_model_id(bad_model_id)


def test_interview_stub_card_count_bounds():
    """interview_activity stub: card count < 5 raises non_retryable ApplicationError."""
    import asyncio as _asyncio
    from temporalio.exceptions import ApplicationError
    from harness.commissioning.activities.interview import (
        InterviewActivityInput,
        interview_activity,
    )

    # Build a minimal fixture with only 2 cards — should fail validation.
    import tempfile
    minimal_fixture = {
        "operator_id": "test-unit",
        "business": {
            "name": "Test Co",
            "what_is_sold": "widgets",
            "sold_to_whom": "buyers",
            "revenue_concentration": "even",
            "exceptions": [],
        },
        "lifecycle": {"stages": ["new", "done"]},
        "channels": ["web_form"],
        "task_types": ["follow_up"],
        "tools": [{"name": "record_event", "consequence_class": "reversible"}],
        "calculations": [],
        "scenarios": [
            {
                "card_id": "card-01",
                "title": "T1",
                "narrative": "N1",
                "expected_stages": ["new"],
                "expected_outcome": "done",
            },
            {
                "card_id": "card-02",
                "title": "T2",
                "narrative": "N2",
                "expected_stages": ["new"],
                "expected_outcome": "done",
            },
        ],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        json.dump(minimal_fixture, tmp)
        tmp_path = tmp.name

    try:
        with pytest.raises(ApplicationError) as exc_info:
            _asyncio.get_event_loop().run_until_complete(
                interview_activity(
                    InterviewActivityInput(
                        operator_id="test-unit",
                        fixture_path=tmp_path,
                        idempotency_key="unit:interview:bounds",
                    )
                )
            )
        assert exc_info.value.non_retryable is True
        assert "5" in str(exc_info.value)
    finally:
        os.unlink(tmp_path)


def test_dissect_fault_injection_round0_only():
    """dissect_activity stub: inject_fault=True, round=0 → by_tool.transition_state
    set to 'reversible' and provenance.fault locates the branch node."""
    import asyncio as _asyncio
    from harness.commissioning.activities.interview import (
        InterviewActivityInput,
        interview_activity,
    )
    from harness.commissioning.activities.dissect import (
        DissectActivityInput,
        dissect_activity,
    )

    loop = _asyncio.get_event_loop()
    interview = loop.run_until_complete(
        interview_activity(
            InterviewActivityInput(
                operator_id="meridian-realty-v0",
                fixture_path=_FIXTURE_PATH,
                idempotency_key="unit:interview:fault",
            )
        )
    )
    dissection = loop.run_until_complete(
        dissect_activity(
            DissectActivityInput(
                interview=interview,
                round=0,
                inject_fault=True,
                correction=None,
                idempotency_key="unit:dissect:fault:r0",
            )
        )
    )
    # Fault should be injected
    assert dissection.fault_injected is True
    assert dissection.consequence_taxonomy.by_tool["transition_state"] == "reversible"
    fault_prov = dissection.consequence_taxonomy.provenance.get("fault", {})
    assert fault_prov.get("injected_at") == "dissect:round0"
    assert fault_prov.get("field") == "by_tool.transition_state"

    # Fault should NOT persist into round 1 without inject_fault flag
    dissection_r1 = loop.run_until_complete(
        dissect_activity(
            DissectActivityInput(
                interview=interview,
                round=1,
                inject_fault=True,   # ignored on round != 0
                correction=None,
                idempotency_key="unit:dissect:fault:r1",
            )
        )
    )
    # Round 1 should NOT inject fault (only round 0 is eligible)
    assert dissection_r1.fault_injected is False
    assert dissection_r1.consequence_taxonomy.by_tool["transition_state"] == "compensable"


def test_dissect_applies_correction():
    """dissect_activity stub: submit_correction updates taxonomy and records provenance."""
    import asyncio as _asyncio
    from harness.commissioning.activities.interview import (
        InterviewActivityInput,
        interview_activity,
    )
    from harness.commissioning.activities.dissect import (
        DissectActivityInput,
        dissect_activity,
    )

    loop = _asyncio.get_event_loop()
    interview = loop.run_until_complete(
        interview_activity(
            InterviewActivityInput(
                operator_id="meridian-realty-v0",
                fixture_path=_FIXTURE_PATH,
                idempotency_key="unit:interview:corr",
            )
        )
    )
    correction = {
        "target": "consequence_taxonomy.by_tool.transition_state",
        "value": "compensable",
        "evidence": "fixture $.tools[1].consequence_class",
    }
    dissection = loop.run_until_complete(
        dissect_activity(
            DissectActivityInput(
                interview=interview,
                round=1,
                inject_fault=False,
                correction=correction,
                idempotency_key="unit:dissect:corr:r1",
            )
        )
    )
    assert dissection.consequence_taxonomy.by_tool["transition_state"] == "compensable"
    corr_prov = dissection.consequence_taxonomy.provenance.get("correction", {})
    assert corr_prov.get("new_value") == "compensable"
    assert corr_prov.get("evidence") == correction["evidence"]
    assert dissection.round == 1


def test_construct_gates_derived_from_taxonomy():
    """construct_activity: gates.by_tool only contains non-reversible tools."""
    import asyncio as _asyncio
    from harness.commissioning.activities.interview import (
        InterviewActivityInput,
        interview_activity,
    )
    from harness.commissioning.activities.dissect import (
        DissectActivityInput,
        dissect_activity,
    )
    from harness.commissioning.activities.construct import (
        ConstructActivityInput,
        construct_activity,
    )

    loop = _asyncio.get_event_loop()
    interview = loop.run_until_complete(
        interview_activity(
            InterviewActivityInput(
                operator_id="meridian-realty-v0",
                fixture_path=_FIXTURE_PATH,
                idempotency_key="unit:interview:gates",
            )
        )
    )
    dissection = loop.run_until_complete(
        dissect_activity(
            DissectActivityInput(
                interview=interview,
                round=0,
                inject_fault=False,
                idempotency_key="unit:dissect:gates",
            )
        )
    )
    bundle = loop.run_until_complete(
        construct_activity(
            ConstructActivityInput(
                operator_id="meridian-realty-v0",
                dissection=dissection,
                idempotency_key="unit:construct:gates",
            )
        )
    )
    agent_stems = list(bundle.agents.keys())
    assert len(agent_stems) == 1
    agent_obj = bundle.agents[agent_stems[0]]
    by_tool = agent_obj["gates"]["by_tool"]

    # record_event is reversible → must NOT appear in by_tool
    assert "record_event" not in by_tool, (
        "reversible tool record_event must not appear in gates.by_tool"
    )
    # transition_state is compensable → must appear in by_tool
    assert "transition_state" in by_tool, (
        "compensable tool transition_state must appear in gates.by_tool"
    )
    # assign_task is compensable → must appear in by_tool
    assert "assign_task" in by_tool, (
        "compensable tool assign_task must appear in gates.by_tool"
    )

    # Fault path: inject wrong class → transition_state becomes reversible → excluded
    interview_f = loop.run_until_complete(
        interview_activity(
            InterviewActivityInput(
                operator_id="meridian-realty-v0",
                fixture_path=_FIXTURE_PATH,
                idempotency_key="unit:interview:gates:fault",
            )
        )
    )
    dissection_f = loop.run_until_complete(
        dissect_activity(
            DissectActivityInput(
                interview=interview_f,
                round=0,
                inject_fault=True,
                idempotency_key="unit:dissect:gates:fault",
            )
        )
    )
    bundle_f = loop.run_until_complete(
        construct_activity(
            ConstructActivityInput(
                operator_id="meridian-realty-v0",
                dissection=dissection_f,
                idempotency_key="unit:construct:gates:fault",
            )
        )
    )
    agent_f = bundle_f.agents[list(bundle_f.agents.keys())[0]]
    by_tool_f = agent_f["gates"]["by_tool"]
    assert "transition_state" not in by_tool_f, (
        "Fault path: reversible transition_state must be excluded from by_tool"
    )


def test_validate_vector_reproduction_exact():
    """validate_activity: all CalculationRule test vectors pass exactly."""
    import asyncio as _asyncio
    from harness.commissioning.activities.interview import (
        InterviewActivityInput,
        interview_activity,
    )
    from harness.commissioning.activities.dissect import (
        DissectActivityInput,
        dissect_activity,
    )
    from harness.commissioning.activities.construct import (
        ConstructActivityInput,
        construct_activity,
    )
    from harness.commissioning.activities.validate import (
        ValidateActivityInput,
        validate_activity,
    )

    loop = _asyncio.get_event_loop()
    interview = loop.run_until_complete(
        interview_activity(
            InterviewActivityInput(
                operator_id="meridian-realty-v0",
                fixture_path=_FIXTURE_PATH,
                idempotency_key="unit:interview:vec",
            )
        )
    )
    dissection = loop.run_until_complete(
        dissect_activity(
            DissectActivityInput(
                interview=interview,
                round=0,
                inject_fault=False,
                idempotency_key="unit:dissect:vec",
            )
        )
    )
    bundle = loop.run_until_complete(
        construct_activity(
            ConstructActivityInput(
                operator_id="meridian-realty-v0",
                dissection=dissection,
                idempotency_key="unit:construct:vec",
            )
        )
    )
    vresult = loop.run_until_complete(
        validate_activity(
            ValidateActivityInput(
                bundle=bundle,
                interview=interview,
                dissection=dissection,
                golden_bundle_path=_GOLDEN_PATH,
                idempotency_key="unit:validate:vec",
            )
        )
    )
    vector_check = vresult.report["tier0"]["vector_reproduction"]
    assert vector_check["passed"] is True, (
        f"Vector reproduction failures: {vector_check['failures']}"
    )
    assert vector_check["rules_checked"] >= 1


def test_validate_fails_on_wrong_consequence_class():
    """validate_activity: fault-injected bundle (transition_state=reversible) fails
    Tier 0 golden comparison — golden by_tool key is missing from emitted bundle."""
    import asyncio as _asyncio
    from harness.commissioning.activities.interview import (
        InterviewActivityInput,
        interview_activity,
    )
    from harness.commissioning.activities.dissect import (
        DissectActivityInput,
        dissect_activity,
    )
    from harness.commissioning.activities.construct import (
        ConstructActivityInput,
        construct_activity,
    )
    from harness.commissioning.activities.validate import (
        ValidateActivityInput,
        validate_activity,
    )

    loop = _asyncio.get_event_loop()
    interview = loop.run_until_complete(
        interview_activity(
            InterviewActivityInput(
                operator_id="meridian-realty-v0",
                fixture_path=_FIXTURE_PATH,
                idempotency_key="unit:interview:fault-val",
            )
        )
    )
    dissection_f = loop.run_until_complete(
        dissect_activity(
            DissectActivityInput(
                interview=interview,
                round=0,
                inject_fault=True,
                idempotency_key="unit:dissect:fault-val",
            )
        )
    )
    bundle_f = loop.run_until_complete(
        construct_activity(
            ConstructActivityInput(
                operator_id="meridian-realty-v0",
                dissection=dissection_f,
                idempotency_key="unit:construct:fault-val",
            )
        )
    )
    vresult = loop.run_until_complete(
        validate_activity(
            ValidateActivityInput(
                bundle=bundle_f,
                interview=interview,
                dissection=dissection_f,
                golden_bundle_path=_GOLDEN_PATH,
                idempotency_key="unit:validate:fault-val",
            )
        )
    )
    assert vresult.passed is False
    # Failure message must mention transition_state
    assert any("transition_state" in f for f in vresult.failures), (
        f"Expected 'transition_state' in failures, got: {vresult.failures}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — require live Temporal + worker (INFER_STUB=1)
# ═══════════════════════════════════════════════════════════════════════════════


async def _connect() -> "temporalio.client.Client":
    from temporalio.client import Client
    return await Client.connect(_TEMPORAL_HOST)


@pytest.mark.integration
async def test_commissioning_end_to_end(test_key_prefix, tmp_path):
    """Gate clause 1: CommissioningWorkflow runs full pipeline; bundle written to disk."""
    from harness.commissioning.workflows.commission import CommissioningWorkflow
    from harness.shared.contracts.commission import CommissioningInput, CommissioningResult

    client = await _connect()
    operator_id = f"test-e2e-{test_key_prefix}"
    output_root = str(tmp_path)

    inp = CommissioningInput(
        operator_id=operator_id,
        fixture_path=_FIXTURE_PATH,
        golden_bundle_path=_GOLDEN_PATH,
        auto_advance_dissect=True,
        inject_fault=False,
        auto_promote=True,           # explicit written policy for test
        output_root=output_root,
        idempotency_key=f"{test_key_prefix}:commission:e2e",
    )

    result: CommissioningResult = await client.execute_workflow(
        CommissioningWorkflow.run,
        inp,
        id=f"{test_key_prefix}-commission-e2e",
        task_queue=_TASK_QUEUE,
        execution_timeout=timedelta(minutes=5),
    )

    assert result.final_stage == "promoted"
    assert result.dissect_rounds == 1
    assert result.tiers_run == ["tier0"]

    # Bundle directory written on disk
    bundle_dir = Path(result.bundle_path)
    assert bundle_dir.is_dir(), f"Bundle dir not found: {bundle_dir}"
    assert (bundle_dir / "agents").is_dir()
    assert (bundle_dir / "flows").is_dir()
    assert (bundle_dir / "vocab").is_dir()
    assert (bundle_dir / "manifest.json").is_file()

    # Stage artifacts recorded
    # (CommissioningResult does not expose artifacts — we verified stage via final_stage)


@pytest.mark.integration
async def test_promoted_bundle_schema_valid(test_key_prefix, tmp_path):
    """Gate clause 2: emitted bundle passes full schema check (13 agent fields,
    8 flow fields, vocab _note prefix, model_policy values pass guard)."""
    from harness.commissioning.workflows.commission import CommissioningWorkflow
    from harness.shared.contracts.commission import CommissioningInput, load_bundle_dir
    from harness.shared.contracts.infer import _guard_model_id

    client = await _connect()
    operator_id = f"test-schema-{test_key_prefix}"
    output_root = str(tmp_path)

    inp = CommissioningInput(
        operator_id=operator_id,
        fixture_path=_FIXTURE_PATH,
        golden_bundle_path=_GOLDEN_PATH,
        auto_advance_dissect=True,
        auto_promote=True,
        output_root=output_root,
        idempotency_key=f"{test_key_prefix}:commission:schema",
    )

    result = await client.execute_workflow(
        CommissioningWorkflow.run,
        inp,
        id=f"{test_key_prefix}-commission-schema",
        task_queue=_TASK_QUEUE,
        execution_timeout=timedelta(minutes=5),
    )
    assert result.final_stage == "promoted"

    spec = load_bundle_dir(result.bundle_path)

    # Every agent must have the 13 required fields
    _REQUIRED_AGENT_FIELDS = {
        "id", "department", "role", "objectives", "tool_allowlist",
        "autonomy_level", "gates", "escalation_rules", "model_policy",
        "retrieval_budget", "step_budget", "token_budget", "version",
    }
    for stem, agent_obj in spec.agents.items():
        missing = _REQUIRED_AGENT_FIELDS - agent_obj.keys()
        assert not missing, f"agents/{stem}: missing fields {missing}"
        # model_policy values must pass the guard
        for role_key, model_id in agent_obj["model_policy"].items():
            _guard_model_id(str(model_id))   # raises if cloud prefix

    # Every flow must have the 8 required fields
    _REQUIRED_FLOW_FIELDS = {
        "id", "version", "description", "trigger", "workflow_type",
        "agent_id", "workflow_id_template", "goal_payload_template",
    }
    for stem, flow_obj in spec.flows.items():
        missing = _REQUIRED_FLOW_FIELDS - flow_obj.keys()
        assert not missing, f"flows/{stem}: missing fields {missing}"

    # Every vocab file must have _note with correct prefix + a list-valued key
    _NOTE_PREFIX = "Open set — append never edit."
    for vocab_key, vocab_obj in spec.vocab.items():
        note = vocab_obj.get("_note", "")
        assert isinstance(note, str) and note.startswith(_NOTE_PREFIX), (
            f"vocab/{vocab_key}: _note must start with '{_NOTE_PREFIX}', got {note!r}"
        )
        list_keys = [k for k, v in vocab_obj.items() if k != "_note" and isinstance(v, list)]
        assert list_keys, f"vocab/{vocab_key}: no list-valued payload key"


@pytest.mark.integration
async def test_discipline_correction(test_key_prefix, tmp_path):
    """Gate clause 3: inject_fault=True + auto_advance_dissect=False.

    Round 0: dissect emits wrong consequence_class → provenance locates fault.
    Correction signal sent → round 1 re-runs with corrected taxonomy.
    advance_stage sent → construct/validate run; promoted bundle has correct gates.
    """
    from harness.commissioning.workflows.commission import CommissioningWorkflow
    from harness.shared.contracts.commission import CommissioningInput

    client = await _connect()
    operator_id = f"test-disc-{test_key_prefix}"
    output_root = str(tmp_path)

    inp = CommissioningInput(
        operator_id=operator_id,
        fixture_path=_FIXTURE_PATH,
        golden_bundle_path=_GOLDEN_PATH,
        auto_advance_dissect=False,   # manual review gate
        inject_fault=True,            # wrong taxonomy injected in round 0
        auto_promote=True,            # skip approve_promote gate for test
        output_root=output_root,
        idempotency_key=f"{test_key_prefix}:commission:disc",
    )

    wf_id = f"{test_key_prefix}-commission-disc"
    handle = await client.start_workflow(
        CommissioningWorkflow.run,
        inp,
        id=wf_id,
        task_queue=_TASK_QUEUE,
        execution_timeout=timedelta(minutes=5),
    )

    # Wait for workflow to enter dissect_review
    deadline = 60  # seconds
    elapsed = 0
    stage = ""
    while elapsed < deadline:
        await asyncio.sleep(1)
        elapsed += 1
        stage = await handle.query(CommissioningWorkflow.get_stage)
        if stage == "dissect_review":
            break
    assert stage == "dissect_review", (
        f"Expected stage 'dissect_review', got {stage!r} after {elapsed}s"
    )

    # Inspect round-0 artifact: fault must be present
    artifacts = await handle.query(CommissioningWorkflow.get_artifacts)
    assert "dissect:0" in artifacts, f"dissect:0 artifact missing; keys={list(artifacts)}"

    dissect_r0 = artifacts["dissect:0"]
    by_tool_r0 = dissect_r0["consequence_taxonomy"]["by_tool"]
    assert by_tool_r0.get("transition_state") == "reversible", (
        f"Fault not injected — transition_state={by_tool_r0.get('transition_state')!r}"
    )

    # Provenance must locate the branch node
    fault_prov = dissect_r0["consequence_taxonomy"]["provenance"].get("fault", {})
    assert fault_prov.get("injected_at") == "dissect:round0", (
        f"Provenance does not locate fault at dissect:round0: {fault_prov}"
    )

    # Send correction: fix consequence_class
    correction = {
        "target": "consequence_taxonomy.by_tool.transition_state",
        "value": "compensable",
        "evidence": "fixture $.tools[1].consequence_class",
    }
    await handle.signal(CommissioningWorkflow.submit_correction, correction)

    # Wait for second dissect_review (round 1 complete)
    elapsed = 0
    round1_appeared = False
    while elapsed < deadline:
        await asyncio.sleep(1)
        elapsed += 1
        stage = await handle.query(CommissioningWorkflow.get_stage)
        if stage == "dissect_review":
            artifacts = await handle.query(CommissioningWorkflow.get_artifacts)
            if "dissect:1" in artifacts:
                round1_appeared = True
                break
    assert round1_appeared, (
        f"dissect:1 artifact never appeared; stage={stage!r}, "
        f"artifacts={list(artifacts)}"
    )

    # Verify correction applied in round 1
    dissect_r1 = artifacts["dissect:1"]
    by_tool_r1 = dissect_r1["consequence_taxonomy"]["by_tool"]
    assert by_tool_r1.get("transition_state") == "compensable", (
        f"Correction not applied in round 1: by_tool={by_tool_r1}"
    )
    corr_prov = dissect_r1["consequence_taxonomy"]["provenance"].get("correction", {})
    assert corr_prov.get("new_value") == "compensable", (
        f"Correction provenance missing: {corr_prov}"
    )

    # Advance past review → construct / validate / promote
    await handle.signal(CommissioningWorkflow.advance_stage)

    result = await handle.result()

    assert result.final_stage == "promoted"
    assert result.dissect_rounds == 2, (
        f"Expected 2 dissect rounds (0 + 1), got {result.dissect_rounds}"
    )
    assert len(result.corrections_applied) == 1
    assert result.corrections_applied[0]["correction"]["target"] == (
        "consequence_taxonomy.by_tool.transition_state"
    )

    # Promoted bundle must have transition_state in gates.by_tool (compensable → approve)
    bundle_dir = Path(result.bundle_path)
    agent_files = sorted((bundle_dir / "agents").glob("*.json"))
    assert agent_files, "No agent files in promoted bundle"
    with open(agent_files[0]) as fh:
        agent_obj = json.load(fh)
    by_tool_final = agent_obj["gates"]["by_tool"]
    assert "transition_state" in by_tool_final, (
        f"Promoted bundle gates.by_tool missing 'transition_state': {by_tool_final}"
    )
    assert by_tool_final["transition_state"] == "approve"


@pytest.mark.integration
async def test_promoted_bundle_drives_agent_loop(test_key_prefix, tmp_path):
    """Gate clause 4: promoted bundle fields are compatible with AgentLoopInput;
    model_policy values pass the guard (no cloud prefix)."""
    from harness.commissioning.workflows.commission import CommissioningWorkflow
    from harness.shared.contracts.commission import CommissioningInput
    from harness.operations.workflows.agent_loop import AgentLoopInput
    from harness.shared.contracts.infer import _guard_model_id

    client = await _connect()
    operator_id = f"test-compat-{test_key_prefix}"
    output_root = str(tmp_path)

    inp = CommissioningInput(
        operator_id=operator_id,
        fixture_path=_FIXTURE_PATH,
        golden_bundle_path=_GOLDEN_PATH,
        auto_advance_dissect=True,
        auto_promote=True,
        output_root=output_root,
        idempotency_key=f"{test_key_prefix}:commission:compat",
    )

    result = await client.execute_workflow(
        CommissioningWorkflow.run,
        inp,
        id=f"{test_key_prefix}-commission-compat",
        task_queue=_TASK_QUEUE,
        execution_timeout=timedelta(minutes=5),
    )
    assert result.final_stage == "promoted"

    # Read emitted agent and flow specs
    bundle_dir = Path(result.bundle_path)
    agent_files = sorted((bundle_dir / "agents").glob("*.json"))
    flow_files = sorted((bundle_dir / "flows").glob("*.json"))
    assert agent_files, "No agent files"
    assert flow_files, "No flow files"

    with open(agent_files[0]) as fh:
        agent_spec = json.load(fh)
    with open(flow_files[0]) as fh:
        flow_spec = json.load(fh)

    # All model_policy values must pass the guard
    for role_key, model_id in agent_spec["model_policy"].items():
        _guard_model_id(str(model_id))

    # Verify AgentLoopInput construction succeeds with the emitted fields
    loop_inp = AgentLoopInput(
        agent_id=agent_spec["id"],
        entity_id=str(uuid.uuid4()),
        flow_id=flow_spec["id"],
        model_id=agent_spec["model_policy"]["decide"],
        max_steps=agent_spec["step_budget"],
        token_budget=agent_spec["token_budget"],
        stall_threshold=agent_spec["escalation_rules"]["stall_after"],
        tool_allowlist=agent_spec["tool_allowlist"],
        idempotency_key=f"{test_key_prefix}:loop:compat",
    )
    assert loop_inp.agent_id == agent_spec["id"]
    assert loop_inp.model_id.startswith(("ollama/", "ollama_chat/")), (
        f"model_id must not be a cloud model: {loop_inp.model_id!r}"
    )
    assert isinstance(loop_inp.tool_allowlist, list)
    assert len(loop_inp.tool_allowlist) >= 1

    # The agent_id field in the flow must match the agent id
    assert flow_spec["agent_id"] == agent_spec["id"], (
        f"flow.agent_id {flow_spec['agent_id']!r} != agent.id {agent_spec['id']!r}"
    )
