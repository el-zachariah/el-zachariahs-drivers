import pytest
from pydantic import ValidationError

from el_zachariahs_drivers.models import (
    Blocker,
    DriverKind,
    EvidenceRef,
    EvidenceType,
    ProgressSignal,
    ProjectIntakePhase,
    ResumeDecisionOption,
    ResumeTarget,
    TaskPhase,
    TerminalOutcome,
    WaitPolicy,
    WaitThresholdResponse,
    WorkflowDecision,
    WorkflowRole,
)
from el_zachariahs_drivers.policies.templates import (
    PROJECT_PHASE_POLICIES,
    TASK_PHASE_POLICIES,
    phase_policy_for,
    validate_decision_against_phase_policy,
)


def wait_policy(threshold_response: WaitThresholdResponse = WaitThresholdResponse.BLOCKED_NEEDS_EL_LE) -> WaitPolicy:
    return WaitPolicy(
        awaited_signal="review_completed",
        started_at="2026-07-31T05:15:00Z",
        threshold_at="2026-07-31T05:45:00Z",
        retry_policy="single-reminder",
        threshold_response=threshold_response,
    )


def blocker(owner_role: WorkflowRole = WorkflowRole.PROCESS_STEWARD) -> Blocker:
    return Blocker(
        reason="review is stuck",
        category="process" if owner_role != WorkflowRole.HUMAN_APPROVER else "human_authority",
        owner_role=owner_role,
        required_decision="resume or escalate",
        resume_target=ResumeTarget(
            blocked_phase="REVIEW_WAIT",
            resume_phase_if_unblocked="REVIEW_REQUESTED",
            decision_options=[
                ResumeDecisionOption(
                    decision="resume",
                    resulting_phase="REVIEW_REQUESTED",
                    notes="request review again",
                )
            ],
        ),
    )


def evidence() -> EvidenceRef:
    return EvidenceRef(type=EvidenceType.PLAN, uri="plan:1")


def test_project_and_task_phase_policy_maps_cover_all_template_phases():
    assert set(PROJECT_PHASE_POLICIES) == {phase.value for phase in ProjectIntakePhase}
    assert set(TASK_PHASE_POLICIES) == {phase.value for phase in TaskPhase}


def test_phase_policy_names_allowed_signals_waits_blockers_and_terminals():
    review_wait = phase_policy_for(DriverKind.SOFTWARE_TASK, TaskPhase.REVIEW_WAIT)
    assert ProgressSignal.REVIEW_COMPLETED in review_wait.progress_signals
    assert ProgressSignal.WAIT_TIMER_STARTED in review_wait.wait_signals
    assert WorkflowRole.REVIEWER in review_wait.blocker_owner_roles

    final_report = phase_policy_for(DriverKind.SOFTWARE_PROJECT, ProjectIntakePhase.FINAL_REPORT)
    assert final_report.terminal_outcomes == frozenset({TerminalOutcome.DONE})


def test_validate_decision_accepts_allowed_material_project_signal():
    decision = WorkflowDecision(
        decision_id="d-plan-created",
        decided_at="2026-07-31T05:15:01Z",
        from_phase=ProjectIntakePhase.PLANNING,
        to_phase=ProjectIntakePhase.PLAN_REVIEW,
        material_progress=True,
        progress_signal=ProgressSignal.PLAN_CREATED,
    )

    assert validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, decision) == decision


def test_validate_decision_rejects_signal_not_allowed_for_phase():
    decision = WorkflowDecision(
        decision_id="d-bad-signal",
        decided_at="2026-07-31T05:15:02Z",
        from_phase=ProjectIntakePhase.PLANNING,
        to_phase=ProjectIntakePhase.PLANNING,
        material_progress=True,
        progress_signal=ProgressSignal.PROOF_STARTED,
    )

    with pytest.raises(ValueError, match="not allowed"):
        validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, decision)


def test_validate_decision_accepts_controlled_wait_only_where_allowed():
    task_review_wait = WorkflowDecision(
        decision_id="d-task-review-wait",
        decided_at="2026-07-31T05:15:03Z",
        from_phase=TaskPhase.REVIEW_REQUESTED,
        to_phase=TaskPhase.REVIEW_WAIT,
        material_progress=False,
        progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
        wait_to_start=wait_policy(),
    )
    assert validate_decision_against_phase_policy(DriverKind.SOFTWARE_TASK, task_review_wait) == task_review_wait

    task_assigned_wait = WorkflowDecision(
        decision_id="d-task-assigned-wait",
        decided_at="2026-07-31T05:15:04Z",
        from_phase=TaskPhase.TASK_ASSIGNED,
        to_phase=TaskPhase.TASK_ASSIGNED,
        material_progress=False,
        progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
        wait_to_start=wait_policy(),
    )
    with pytest.raises(ValueError, match="does not allow controlled waits"):
        validate_decision_against_phase_policy(DriverKind.SOFTWARE_TASK, task_assigned_wait)


def test_validate_decision_checks_wait_threshold_route_against_phase_blocker_policy():
    proof_auth_wait = WorkflowDecision(
        decision_id="d-proof-auth-human-wait",
        decided_at="2026-07-31T05:15:05Z",
        from_phase=ProjectIntakePhase.PROOF_AUTH_WAIT,
        to_phase=ProjectIntakePhase.PROOF_AUTH_WAIT,
        material_progress=False,
        progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
        wait_to_start=wait_policy(WaitThresholdResponse.BLOCKED_NEEDS_ZO_EL),
    )
    assert validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, proof_auth_wait) == proof_auth_wait

    invalid_process_escalation = WorkflowDecision(
        decision_id="d-proof-auth-process-wait",
        decided_at="2026-07-31T05:15:06Z",
        from_phase=ProjectIntakePhase.PROOF_AUTH_WAIT,
        to_phase=ProjectIntakePhase.PROOF_AUTH_WAIT,
        material_progress=False,
        progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
        wait_to_start=wait_policy(WaitThresholdResponse.BLOCKED_NEEDS_EL_LE),
    )
    with pytest.raises(ValueError, match="cannot escalate waits"):
        validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, invalid_process_escalation)


def test_validate_decision_rejects_blocker_owner_not_allowed_for_phase():
    decision = WorkflowDecision(
        decision_id="d-feedback-blocker",
        decided_at="2026-07-31T05:15:07Z",
        from_phase=ProjectIntakePhase.FEEDBACK_WAIT,
        to_phase=ProjectIntakePhase.BLOCKED_NEEDS_EL_LE,
        material_progress=True,
        progress_signal=ProgressSignal.BLOCKER_CREATED,
        blocker_to_record=blocker(WorkflowRole.PROCESS_STEWARD),
    )

    with pytest.raises(ValueError, match="blocker owner"):
        validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, decision)


def test_validate_decision_accepts_terminal_only_from_configured_terminal_phase():
    decision = WorkflowDecision(
        decision_id="d-final-report-done",
        decided_at="2026-07-31T05:15:08Z",
        from_phase=ProjectIntakePhase.FINAL_REPORT,
        to_phase=ProjectIntakePhase.DONE,
        material_progress=True,
        progress_signal=ProgressSignal.FINAL_REPORT_DELIVERED,
        terminal_outcome=TerminalOutcome.DONE,
    )
    assert validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, decision) == decision

    bad_terminal = WorkflowDecision(
        decision_id="d-plan-done",
        decided_at="2026-07-31T05:15:09Z",
        from_phase=ProjectIntakePhase.PLANNING,
        to_phase=ProjectIntakePhase.DONE,
        material_progress=True,
        terminal_outcome=TerminalOutcome.DONE,
    )
    with pytest.raises(ValueError, match="terminal outcome"):
        validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, bad_terminal)


def test_validate_decision_accepts_task_rescope_terminal_cancellation():
    decision = WorkflowDecision(
        decision_id="d-rescope-cancelled",
        decided_at="2026-07-31T05:15:09Z",
        from_phase=TaskPhase.RESCOPE_REQUESTED,
        to_phase="CANCELLED",
        material_progress=True,
        terminal_outcome=TerminalOutcome.CANCELLED,
    )

    assert validate_decision_against_phase_policy(DriverKind.SOFTWARE_TASK, decision) == decision


def test_workflow_decision_rejects_material_progress_without_signal_or_evidence_or_effect():
    with pytest.raises(ValidationError, match="material progress decisions require"):
        WorkflowDecision(
            decision_id="d-no-op-progress",
            decided_at="2026-07-31T05:15:10Z",
            from_phase=ProjectIntakePhase.PLANNING,
            to_phase=ProjectIntakePhase.PLANNING,
            material_progress=True,
        )


def test_validate_decision_allows_evidence_only_material_progress_but_not_policy_stall():
    decision = WorkflowDecision(
        decision_id="d-evidence-only",
        decided_at="2026-07-31T05:15:11Z",
        from_phase=ProjectIntakePhase.PLANNING,
        to_phase=ProjectIntakePhase.PLANNING,
        material_progress=True,
        evidence_refs=[evidence()],
    )

    with pytest.raises(ValueError, match="does not produce material progress"):
        validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, decision)
