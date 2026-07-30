import pytest
from pydantic import ValidationError

from el_zachariahs_drivers.models import (
    ActivityFailurePolicy,
    ActivityRequest,
    ActivitySideEffect,
    Blocker,
    DriverInput,
    DriverKind,
    EvidenceRef,
    EvidenceType,
    ProgressSignal,
    ResumeDecisionOption,
    ResumeTarget,
    RetryPolicy,
    TerminalOutcome,
    TimeoutPolicy,
    WaitPolicy,
    WaitThresholdResponse,
    WorkflowDecision,
    WorkflowEvent,
    WorkflowRole,
    WorkflowStateRecord,
)
from el_zachariahs_drivers.policies.replay import apply_decision, evidence_digest, replay_events


def state(phase: str = "PLANNING") -> WorkflowStateRecord:
    return WorkflowStateRecord(
        workflow_id="wf-1",
        template_id="software-project",
        template_version="0.1.0",
        driver_kind=DriverKind.SOFTWARE_PROJECT,
        phase=phase,
        input=DriverInput(project_id="project-1", input_digest="sha256:input"),
        role_bindings_version="profiles/test@1",
    )


def evidence(uri: str = "git:abc123") -> EvidenceRef:
    return EvidenceRef(type=EvidenceType.COMMIT, uri=uri, digest="sha256:evidence")


def blocker() -> Blocker:
    return Blocker(
        reason="approval required before proof run",
        category="human_authority",
        owner_role=WorkflowRole.HUMAN_APPROVER,
        required_decision="approve proof run or skip proof",
        evidence_refs=[evidence("proof-plan:1")],
        resume_target=ResumeTarget(
            blocked_phase="PROOF_AUTH_WAIT",
            resume_phase_if_unblocked="PROOF_RUNNING",
            resume_activity="run_proof_packet",
            decision_options=[
                ResumeDecisionOption(
                    decision="approve",
                    resulting_phase="PROOF_RUNNING",
                    notes="run proof packet",
                ),
                ResumeDecisionOption(
                    decision="deny",
                    resulting_phase="FINAL_REPORT",
                    notes="report skipped proof gate",
                ),
            ],
        ),
    )


def activity() -> ActivityRequest:
    return ActivityRequest(
        activity_id="act-1",
        activity_type="write_plan",
        role=WorkflowRole.PROJECT_INTAKE_OWNER,
        purpose="write implementation plan",
        input_refs=[evidence("input:plan")],
        acceptance_criteria=["plan records next executable task"],
        allowed_side_effects=[ActivitySideEffect.CHANGE_ARTIFACT],
        required_evidence=["plan file"],
        idempotency_key="wf-1:write-plan",
        timeout_policy=TimeoutPolicy(start_to_close="10m", schedule_to_close="30m"),
        retry_policy=RetryPolicy(max_attempts=2, backoff="exponential"),
        on_failure=ActivityFailurePolicy(
            rescope_allowed=True,
            blocker_owner_role=WorkflowRole.PROCESS_STEWARD,
        ),
    )


def test_state_record_serializes_and_rehydrates():
    original = state()
    round_tripped = WorkflowStateRecord.model_validate_json(original.model_dump_json())
    assert round_tripped == original


def test_blocker_requires_resume_target_with_decision_options():
    with pytest.raises(ValidationError):
        Blocker(
            reason="missing replay path",
            category="process",
            owner_role=WorkflowRole.PROCESS_STEWARD,
            required_decision="decide what next",
            resume_target={
                "blocked_phase": "TESTING",
                "resume_phase_if_unblocked": "TESTING",
                "decision_options": [],
            },
        )


def test_decision_cannot_carry_resume_target_outside_blocker():
    with pytest.raises(ValidationError):
        WorkflowDecision(
            decision_id="d-bad",
            from_phase="TESTING",
            to_phase="BLOCKED_NEEDS_EL_LE",
            blocker_to_record=blocker(),
            resume_target={"blocked_phase": "TESTING"},
        )


def test_same_phase_decision_without_signal_or_wait_is_invalid():
    with pytest.raises(ValidationError):
        WorkflowDecision(decision_id="d0", from_phase="PLANNING", to_phase="PLANNING")


def test_apply_decision_records_progress_evidence_and_activity():
    decision = WorkflowDecision(
        decision_id="d1",
        from_phase="PLANNING",
        to_phase="PLAN_REVIEW",
        material_progress=True,
        progress_signal=ProgressSignal.PLAN_CREATED,
        activities_to_schedule=[activity()],
        evidence_refs=[evidence()],
    )
    updated = apply_decision(state(), decision)
    assert updated.phase == "PLAN_REVIEW"
    assert updated.current_activity is not None
    assert updated.current_activity.role == WorkflowRole.PROJECT_INTAKE_OWNER
    assert updated.progress_ledger.last_progress_signal == ProgressSignal.PLAN_CREATED
    assert evidence_digest(updated.evidence_refs) == (("commit", "git:abc123", "sha256:evidence"),)


def test_apply_decision_records_blocker_and_clears_wait():
    initial = state("PROOF_AUTH_WAIT")
    initial.wait = WaitPolicy(
        awaited_signal="proof_authorized",
        started_at="t0",
        threshold_at="t1",
        retry_policy="none",
        threshold_response=WaitThresholdResponse.BLOCKED_NEEDS_ZO_EL,
    )
    decision = WorkflowDecision(
        decision_id="d2",
        from_phase="PROOF_AUTH_WAIT",
        to_phase="BLOCKED_NEEDS_ZO_EL",
        blocker_to_record=blocker(),
    )
    updated = apply_decision(initial, decision)
    assert updated.blocker is not None
    assert updated.blocker.resume_target.resume_phase_if_unblocked == "PROOF_RUNNING"
    assert updated.wait is None


def test_replay_events_is_deterministic():
    events = [
        WorkflowEvent(
            event_id="e1",
            type="plan_created",
            emitted_at="t0",
            source_role=WorkflowRole.PROJECT_INTAKE_OWNER,
            correlation_id="wf-1",
            payload={"evidence_uri": "plan:1"},
        )
    ]

    def decide(current: WorkflowStateRecord, event: WorkflowEvent) -> WorkflowDecision:
        return WorkflowDecision(
            decision_id=f"decision-for-{event.event_id}",
            from_phase=current.phase,
            to_phase="PLAN_REVIEW",
            material_progress=True,
            progress_signal=ProgressSignal.PLAN_CREATED,
            evidence_refs=[EvidenceRef(type=EvidenceType.PLAN, uri=event.payload["evidence_uri"])],
        )

    first = replay_events(state(), events, decide)
    second = replay_events(state(), events, decide)
    assert first == second
    assert first.phase == "PLAN_REVIEW"


def test_terminal_decision_records_terminal_state():
    decision = WorkflowDecision(
        decision_id="d3",
        from_phase="FINAL_REPORT",
        to_phase="DONE",
        terminal_outcome=TerminalOutcome.DONE,
    )
    updated = apply_decision(state("FINAL_REPORT"), decision)
    assert updated.terminal is not None
    assert updated.terminal.outcome == TerminalOutcome.DONE
