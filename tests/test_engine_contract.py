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


def activity_two() -> ActivityRequest:
    second = activity().model_copy(deep=True)
    second.activity_id = "act-2"
    second.idempotency_key = "wf-1:write-plan-2"
    return second


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
            decided_at="2026-07-30T23:55:00Z",
            from_phase="TESTING",
            to_phase="BLOCKED_NEEDS_EL_LE",
            blocker_to_record=blocker(),
            resume_target={"blocked_phase": "TESTING"},
        )


def test_same_phase_decision_without_signal_or_wait_is_invalid():
    with pytest.raises(ValidationError):
        WorkflowDecision(
            decision_id="d0",
            decided_at="2026-07-30T23:55:01Z",
            from_phase="PLANNING",
            to_phase="PLANNING",
        )


def test_apply_decision_records_progress_evidence_and_activity():
    decision = WorkflowDecision(
        decision_id="d1",
        decided_at="2026-07-30T23:55:02Z",
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
    assert updated.current_activity.requested_at == "2026-07-30T23:55:02Z"
    assert updated.progress_ledger.last_progress_signal == ProgressSignal.PLAN_CREATED
    assert updated.progress_ledger.last_material_progress_at == "2026-07-30T23:55:02Z"
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
        decided_at="2026-07-30T23:55:03Z",
        from_phase="PROOF_AUTH_WAIT",
        to_phase="BLOCKED_NEEDS_ZO_EL",
        blocker_to_record=blocker(),
    )
    updated = apply_decision(initial, decision)
    assert updated.blocker is not None
    assert updated.blocker.resume_target.resume_phase_if_unblocked == "PROOF_RUNNING"
    assert updated.wait is None


def test_controlled_wait_signal_does_not_require_material_progress():
    wait = WaitPolicy(
        awaited_signal="review_completed",
        started_at="2026-07-30T23:55:05Z",
        threshold_at="2026-07-31T00:25:05Z",
        retry_policy="single-reminder",
        threshold_response=WaitThresholdResponse.BLOCKED_NEEDS_EL_LE,
    )
    decision = WorkflowDecision(
        decision_id="d-wait",
        decided_at="2026-07-30T23:55:05Z",
        from_phase="REVIEW_WAIT",
        to_phase="REVIEW_WAIT",
        material_progress=False,
        progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
        wait_to_start=wait,
    )
    updated = apply_decision(state("REVIEW_WAIT"), decision)
    assert updated.wait == wait
    assert updated.progress_ledger.last_material_progress_at is None
    assert updated.progress_ledger.no_op_observation_count == 0


def test_controlled_wait_signal_requires_durable_wait_policy():
    with pytest.raises(ValidationError, match="controlled wait signals require wait_to_start"):
        WorkflowDecision(
            decision_id="d-wait-missing-policy",
            decided_at="2026-07-30T23:55:05Z",
            from_phase="REVIEW_WAIT",
            to_phase="REVIEW_WAIT",
            material_progress=False,
            progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
        )


def test_controlled_wait_signal_cannot_be_material_progress():
    wait = WaitPolicy(
        awaited_signal="review_completed",
        started_at="2026-07-30T23:55:05Z",
        threshold_at="2026-07-31T00:25:05Z",
        retry_policy="single-reminder",
        threshold_response=WaitThresholdResponse.BLOCKED_NEEDS_EL_LE,
    )
    with pytest.raises(ValidationError, match="controlled wait signals cannot be material progress"):
        WorkflowDecision(
            decision_id="d-wait-material-progress",
            decided_at="2026-07-30T23:55:05Z",
            from_phase="REVIEW_WAIT",
            to_phase="REVIEW_WAIT",
            material_progress=True,
            progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
            wait_to_start=wait,
        )


def test_decision_rejects_multiple_scheduled_activities_until_queue_exists():
    with pytest.raises(ValidationError):
        WorkflowDecision(
            decision_id="d-multi-activity",
            decided_at="2026-07-30T23:55:05Z",
            from_phase="PLANNING",
            to_phase="PLAN_REVIEW",
            material_progress=True,
            progress_signal=ProgressSignal.PLAN_CREATED,
            activities_to_schedule=[activity(), activity_two()],
        )


def test_material_progress_without_signal_updates_progress_ledger_timestamp():
    decision = WorkflowDecision(
        decision_id="d-evidence-only-progress",
        decided_at="2026-07-30T23:55:05Z",
        from_phase="PLANNING",
        to_phase="PLANNING",
        material_progress=True,
        evidence_refs=[evidence("plan:material-update")],
    )
    updated = apply_decision(state(), decision)
    assert updated.progress_ledger.last_material_progress_at == "2026-07-30T23:55:05Z"
    assert updated.progress_ledger.last_progress_signal is None
    assert updated.progress_ledger.no_op_observation_count == 0


def test_apply_decision_rejects_stale_from_phase():
    decision = WorkflowDecision(
        decision_id="d-stale",
        decided_at="2026-07-30T23:55:06Z",
        from_phase="TESTING",
        to_phase="DONE",
        terminal_outcome=TerminalOutcome.DONE,
    )
    with pytest.raises(ValueError, match="cannot apply decision from phase"):
        apply_decision(state("PLANNING"), decision)


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
            decided_at=event.emitted_at,
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
        decided_at="2026-07-30T23:55:04Z",
        from_phase="FINAL_REPORT",
        to_phase="DONE",
        terminal_outcome=TerminalOutcome.DONE,
    )
    updated = apply_decision(state("FINAL_REPORT"), decision)
    assert updated.terminal is not None
    assert updated.terminal.outcome == TerminalOutcome.DONE


def test_terminal_decision_cannot_record_live_blocker():
    with pytest.raises(
        ValidationError,
        match="terminal decisions cannot schedule activities, start waits, or record blockers",
    ):
        WorkflowDecision(
            decision_id="d-terminal-blocked",
            decided_at="2026-07-30T23:55:07Z",
            from_phase="FINAL_REPORT",
            to_phase="DONE",
            terminal_outcome=TerminalOutcome.DONE,
            blocker_to_record=blocker(),
        )


def test_terminal_decision_cannot_leave_scheduled_activity_or_wait():
    wait = WaitPolicy(
        awaited_signal="final_report_delivered",
        started_at="2026-07-30T23:55:07Z",
        threshold_at="2026-07-31T00:25:07Z",
        retry_policy="single-reminder",
        threshold_response=WaitThresholdResponse.FAILED,
    )
    with pytest.raises(ValidationError):
        WorkflowDecision(
            decision_id="d-terminal-activity",
            decided_at="2026-07-30T23:55:07Z",
            from_phase="FINAL_REPORT",
            to_phase="DONE",
            terminal_outcome=TerminalOutcome.DONE,
            activities_to_schedule=[activity()],
        )
    with pytest.raises(ValidationError):
        WorkflowDecision(
            decision_id="d-terminal-wait",
            decided_at="2026-07-30T23:55:07Z",
            from_phase="FINAL_REPORT",
            to_phase="DONE",
            terminal_outcome=TerminalOutcome.DONE,
            progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
            wait_to_start=wait,
        )
