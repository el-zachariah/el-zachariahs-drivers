from __future__ import annotations

import json
from pathlib import Path

import pytest

from el_zachariahs_drivers.cli import main
from el_zachariahs_drivers.models import (
    DriverInput,
    DriverKind,
    EvidenceRef,
    EvidenceType,
    ProgressSignal,
    WorkflowDecision,
    WorkflowRole,
    WorkflowStateRecord,
)
from el_zachariahs_drivers.state_store import JsonWorkflowStore


def state(phase: str = "PLANNING") -> WorkflowStateRecord:
    return WorkflowStateRecord(
        workflow_id="wf-store-1",
        template_id="software_project_driver",
        template_version="1.0.0",
        driver_kind=DriverKind.SOFTWARE_PROJECT,
        phase=phase,
        input=DriverInput(input_digest="sha256:test"),
        role_bindings_version="local-test",
    )


def plan_decision() -> WorkflowDecision:
    return WorkflowDecision(
        decision_id="d-plan-created",
        decided_at="2026-07-31T07:00:00Z",
        from_phase="PLANNING",
        to_phase="PLAN_REVIEW",
        material_progress=True,
        progress_signal=ProgressSignal.PLAN_CREATED,
        evidence_refs=[EvidenceRef(type=EvidenceType.PLAN, uri="file://plan.md")],
    )


def test_json_store_replays_decisions_after_restart(tmp_path: Path):
    store = JsonWorkflowStore(tmp_path)
    store.initialize(state())
    updated = store.append_decision(plan_decision())

    assert updated.phase == "PLAN_REVIEW"
    assert (tmp_path / "initial_state.json").exists()
    assert (tmp_path / "decisions.jsonl").exists()
    assert (tmp_path / "current_state.json").exists()

    restarted = JsonWorkflowStore(tmp_path)
    replayed = restarted.replay()
    assert replayed == updated
    assert restarted.load_current_state() == updated


def test_store_status_names_phase_next_trigger_blocker_and_evidence(tmp_path: Path):
    store = JsonWorkflowStore(tmp_path)
    store.initialize(state())
    store.append_decision(plan_decision())

    status = store.status()
    assert status.workflow_id == "wf-store-1"
    assert status.phase == "PLAN_REVIEW"
    assert status.next_trigger == "event"
    assert status.blocker is None
    assert status.evidence_uris == ["file://plan.md"]


def test_cli_init_append_replay_and_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    initial_path = tmp_path / "initial.json"
    decision_path = tmp_path / "decision.json"
    store_dir = tmp_path / "store"
    initial_path.write_text(state().model_dump_json(indent=2), encoding="utf-8")
    decision_path.write_text(plan_decision().model_dump_json(indent=2), encoding="utf-8")

    assert main(["init", str(store_dir), "--state", str(initial_path)]) == 0
    assert main(["append-decision", str(store_dir), "--decision", str(decision_path)]) == 0
    capsys.readouterr()

    assert main(["replay", str(store_dir)]) == 0
    replay_output = json.loads(capsys.readouterr().out)
    assert replay_output["phase"] == "PLAN_REVIEW"

    assert main(["status", str(store_dir)]) == 0
    status_output = json.loads(capsys.readouterr().out)
    assert status_output == {
        "workflow_id": "wf-store-1",
        "phase": "PLAN_REVIEW",
        "next_trigger": "event",
        "blocker": None,
        "evidence_uris": ["file://plan.md"],
        "terminal": None,
    }


def test_store_rejects_initializing_existing_store(tmp_path: Path):
    store = JsonWorkflowStore(tmp_path)
    store.initialize(state())
    with pytest.raises(FileExistsError, match="workflow store is already initialized"):
        store.initialize(state())
