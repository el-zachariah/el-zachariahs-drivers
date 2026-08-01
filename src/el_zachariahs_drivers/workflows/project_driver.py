"""Temporal-style software project driver skeleton.

The project driver owns lifecycle phases and creates task-driver work.
It should not perform repo/GitHub/Hermes side effects directly.
"""

from __future__ import annotations

from el_zachariahs_drivers.models import (
    Blocker,
    DriverActor,
    DriverAuthorizationEvidence,
    ProgressSignal,
    ProjectIntakePhase,
    ProjectState,
    ResumeDecisionOption,
    ResumeTarget,
    TaskPhase,
    TerminalOutcome,
    WaitPolicy,
    WorkflowDecision,
    WorkflowRole,
    TargetSurface,
)
from el_zachariahs_drivers.policies.proposal import check_project_transition_gate
from el_zachariahs_drivers.review_triggers import ReviewTriggerState, ReviewTriggerVerification


def _blocked_phase_for(owner_role: WorkflowRole) -> ProjectIntakePhase:
    if owner_role == WorkflowRole.HUMAN_APPROVER:
        return ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    return ProjectIntakePhase.BLOCKED_NEEDS_EL_LE


def _blocker_for_review_trigger(
    verification: ReviewTriggerVerification,
    *,
    blocked_phase: ProjectIntakePhase,
) -> Blocker:
    owner_role = (
        WorkflowRole.HUMAN_APPROVER
        if verification.state == ReviewTriggerState.BLOCKED_REVIEWER_ACCESS
        else WorkflowRole.PROCESS_STEWARD
    )
    category = (
        "human_authority"
        if verification.state == ReviewTriggerState.BLOCKED_REVIEWER_ACCESS
        else "process"
    )
    required_decision = verification.required_decision or verification.resume_condition
    return Blocker(
        reason=(
            f"Review trigger for {verification.pr_url} is {verification.state}; "
            f"cannot enter REVIEW_WAIT until {verification.resume_condition}."
        ),
        category=category,
        owner=DriverActor.ZO_EL if owner_role == WorkflowRole.HUMAN_APPROVER else DriverActor.EL_LE,
        owner_role=owner_role,
        required_decision=required_decision,
        resume_target=ResumeTarget(
            blocked_phase=str(blocked_phase),
            resume_phase_if_unblocked=str(ProjectIntakePhase.REVIEW_REQUESTED),
            resume_activity="request_review",
            decision_options=[
                ResumeDecisionOption(
                    decision="review_trigger_verified",
                    resulting_phase=str(ProjectIntakePhase.REVIEW_REQUESTED),
                    notes="Retry review request after a durable review trigger is available.",
                )
            ],
        ),
    )


PROJECT_TRANSITION_SIGNALS: dict[tuple[ProjectIntakePhase, ProjectIntakePhase], ProgressSignal] = {
    (
        ProjectIntakePhase.PROJECT_INTAKE_ASSIGNED,
        ProjectIntakePhase.PLANNING,
    ): ProgressSignal.PROJECT_ACCEPTED,
    (ProjectIntakePhase.PLANNING, ProjectIntakePhase.PLAN_REVIEW): ProgressSignal.PLAN_CREATED,
    (ProjectIntakePhase.PLAN_REVIEW, ProjectIntakePhase.TASK_BREAKDOWN): ProgressSignal.PLAN_APPROVED,
    (ProjectIntakePhase.PLAN_RETHINK, ProjectIntakePhase.TASK_BREAKDOWN): ProgressSignal.PLAN_REVISED,
    (ProjectIntakePhase.TASK_BREAKDOWN, ProjectIntakePhase.TASK_EXECUTION): ProgressSignal.TASKS_CREATED,
    (ProjectIntakePhase.TASK_EXECUTION, ProjectIntakePhase.PLAN_RETHINK): ProgressSignal.TASK_RESCOPE_REQUESTED,
    (ProjectIntakePhase.TASK_EXECUTION, ProjectIntakePhase.PR_OPEN): ProgressSignal.TASK_COMPLETED,
    (ProjectIntakePhase.PR_OPEN, ProjectIntakePhase.REVIEW_REQUESTED): ProgressSignal.PR_CREATED,
    (ProjectIntakePhase.REVIEW_REQUESTED, ProjectIntakePhase.REVIEW_WAIT): ProgressSignal.WAIT_TIMER_STARTED,
    (ProjectIntakePhase.FINAL_REPORT, ProjectIntakePhase.DONE): ProgressSignal.FINAL_REPORT_DELIVERED,
}


def next_project_phase(state: ProjectState) -> ProjectIntakePhase:
    """Pure phase transition sketch for the software project lifecycle."""
    if state.blocker:
        return _blocked_phase_for(state.blocker.owner_role)
    if state.phase == ProjectIntakePhase.PROJECT_INTAKE_ASSIGNED:
        return ProjectIntakePhase.PLANNING
    if state.phase == ProjectIntakePhase.PLANNING:
        return ProjectIntakePhase.PLAN_REVIEW
    if state.phase == ProjectIntakePhase.PLAN_REVIEW:
        return ProjectIntakePhase.TASK_BREAKDOWN
    if state.phase == ProjectIntakePhase.PLAN_RETHINK:
        return ProjectIntakePhase.TASK_BREAKDOWN
    if state.phase == ProjectIntakePhase.TASK_BREAKDOWN and state.tasks:
        return ProjectIntakePhase.TASK_EXECUTION
    if state.phase == ProjectIntakePhase.TASK_EXECUTION:
        if any(task.phase == TaskPhase.RESCOPE_REQUESTED for task in state.tasks):
            return ProjectIntakePhase.PLAN_RETHINK
        if all(task.phase == TaskPhase.COMPLETE for task in state.tasks):
            return ProjectIntakePhase.PR_OPEN
        return ProjectIntakePhase.TASK_EXECUTION
    if state.phase == ProjectIntakePhase.PR_OPEN and state.pr_url:
        return ProjectIntakePhase.REVIEW_REQUESTED
    if state.phase == ProjectIntakePhase.REVIEW_REQUESTED:
        return ProjectIntakePhase.REVIEW_WAIT
    if state.phase == ProjectIntakePhase.FINAL_REPORT:
        return ProjectIntakePhase.DONE
    return state.phase


def decide_next_project_transition(
    state: ProjectState,
    *,
    decided_at: str,
    decision_id: str | None = None,
    wait_to_start: WaitPolicy | None = None,
    review_trigger: ReviewTriggerVerification | None = None,
    candidate_target: TargetSurface | None = None,
    driver_authorization: DriverAuthorizationEvidence | None = None,
    driver_test_mode: bool = False,
) -> WorkflowDecision:
    """Return the contract decision for the next deterministic project transition."""
    next_phase = next_project_phase(state)
    progress_signal = PROJECT_TRANSITION_SIGNALS.get((state.phase, next_phase))

    gate_check = check_project_transition_gate(
        state,
        next_phase=next_phase,
        candidate_target=candidate_target,
        driver_authorization=driver_authorization,
        driver_test_mode=driver_test_mode,
    )
    if not gate_check.ok:
        blocker = gate_check.blocker
        if blocker is None:
            raise ValueError("transition gate failures must include a blocker")
        blocked_phase = _blocked_phase_for(blocker.owner_role)
        return WorkflowDecision(
            decision_id=decision_id or f"{state.id}:{state.phase}:v2-transition-gate-blocked",
            decided_at=decided_at,
            from_phase=state.phase,
            to_phase=blocked_phase,
            material_progress=True,
            progress_signal=ProgressSignal.BLOCKER_CREATED,
            blocker_to_record=blocker,
        )

    if state.blocker:
        if next_phase == state.phase:
            if wait_to_start is None:
                raise ValueError("already-blocked project transitions require a durable wait policy")
            return WorkflowDecision(
                decision_id=decision_id or f"{state.id}:{state.phase}:blocked-wait",
                decided_at=decided_at,
                from_phase=state.phase,
                to_phase=next_phase,
                material_progress=False,
                progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
                wait_to_start=wait_to_start,
                blocker_to_record=state.blocker,
            )
        return WorkflowDecision(
            decision_id=decision_id or f"{state.id}:{state.phase}:blocked",
            decided_at=decided_at,
            from_phase=state.phase,
            to_phase=next_phase,
            material_progress=True,
            progress_signal=ProgressSignal.BLOCKER_CREATED,
            blocker_to_record=state.blocker,
        )

    if next_phase == ProjectIntakePhase.DONE:
        return WorkflowDecision(
            decision_id=decision_id or f"{state.id}:{state.phase}:done",
            decided_at=decided_at,
            from_phase=state.phase,
            to_phase=next_phase,
            material_progress=True,
            progress_signal=progress_signal,
            terminal_outcome=TerminalOutcome.DONE,
        )

    if progress_signal == ProgressSignal.WAIT_TIMER_STARTED:
        if review_trigger is not None and not review_trigger.can_wait_for_review:
            blocker = _blocker_for_review_trigger(review_trigger, blocked_phase=next_phase)
            blocked_phase = _blocked_phase_for(blocker.owner_role)
            return WorkflowDecision(
                decision_id=decision_id or f"{state.id}:{state.phase}:review-trigger-blocked",
                decided_at=decided_at,
                from_phase=state.phase,
                to_phase=blocked_phase,
                material_progress=True,
                progress_signal=ProgressSignal.BLOCKER_CREATED,
                blocker_to_record=blocker,
            )
        if wait_to_start is None:
            raise ValueError("review wait transitions require wait_to_start")
        return WorkflowDecision(
            decision_id=decision_id or f"{state.id}:{state.phase}:wait",
            decided_at=decided_at,
            from_phase=state.phase,
            to_phase=next_phase,
            material_progress=False,
            progress_signal=progress_signal,
            wait_to_start=wait_to_start,
        )

    if next_phase == state.phase:
        if wait_to_start is None:
            raise ValueError("same-phase project transitions require a durable wait policy")
        return WorkflowDecision(
            decision_id=decision_id or f"{state.id}:{state.phase}:wait",
            decided_at=decided_at,
            from_phase=state.phase,
            to_phase=next_phase,
            material_progress=False,
            progress_signal=ProgressSignal.WAIT_TIMER_STARTED,
            wait_to_start=wait_to_start,
        )

    return WorkflowDecision(
        decision_id=decision_id or f"{state.id}:{state.phase}:to:{next_phase}",
        decided_at=decided_at,
        from_phase=state.phase,
        to_phase=next_phase,
        material_progress=True,
        progress_signal=progress_signal,
    )
