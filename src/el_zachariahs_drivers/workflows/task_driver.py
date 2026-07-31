"""Temporal-style software task driver skeleton.

This file should stay deterministic when implemented as a real Temporal workflow.
Side effects belong in activities, not workflow code.
"""

from __future__ import annotations

from el_zachariahs_drivers.models import (
    ProgressSignal,
    TaskPhase,
    TaskState,
    WaitPolicy,
    WorkflowDecision,
    WorkflowRole,
)


def _blocked_phase_for(owner_role: WorkflowRole) -> TaskPhase:
    if owner_role == WorkflowRole.HUMAN_APPROVER:
        return TaskPhase.BLOCKED_NEEDS_ZO_EL
    return TaskPhase.BLOCKED_NEEDS_EL_LE


TASK_TRANSITION_SIGNALS: dict[tuple[TaskPhase, TaskPhase], ProgressSignal] = {
    (TaskPhase.TASK_ASSIGNED, TaskPhase.CLAIMED): ProgressSignal.TASK_STARTED,
    (TaskPhase.CLAIMED, TaskPhase.INSPECTING): ProgressSignal.TASK_STARTED,
    (TaskPhase.INSPECTING, TaskPhase.IMPLEMENTING): ProgressSignal.TASK_STARTED,
    (TaskPhase.IMPLEMENTING, TaskPhase.TESTING): ProgressSignal.TEST_EVIDENCE_CREATED,
    (TaskPhase.TESTING, TaskPhase.REVIEW_REQUESTED): ProgressSignal.REVIEW_REQUESTED,
    (TaskPhase.REVIEW_REQUESTED, TaskPhase.REVIEW_WAIT): ProgressSignal.WAIT_TIMER_STARTED,
    (TaskPhase.FIXING_REVIEW, TaskPhase.IMPLEMENTING): ProgressSignal.REVIEW_FINDINGS_ACCEPTED,
    (TaskPhase.FIXING_REVIEW, TaskPhase.RESCOPE_REQUESTED): ProgressSignal.TASK_RESCOPE_REQUESTED,
}


def next_task_phase(state: TaskState) -> TaskPhase:
    """Pure phase transition sketch for one bounded software task."""
    if state.blocker:
        return _blocked_phase_for(state.blocker.owner_role)
    if state.phase == TaskPhase.FIXING_REVIEW and state.review_loop_count >= state.max_review_loops:
        return TaskPhase.RESCOPE_REQUESTED
    if state.phase == TaskPhase.TASK_ASSIGNED:
        return TaskPhase.CLAIMED
    if state.phase == TaskPhase.CLAIMED:
        return TaskPhase.INSPECTING
    if state.phase == TaskPhase.INSPECTING:
        return TaskPhase.IMPLEMENTING
    if state.phase == TaskPhase.IMPLEMENTING:
        return TaskPhase.TESTING
    if state.phase == TaskPhase.TESTING:
        return TaskPhase.REVIEW_REQUESTED
    if state.phase == TaskPhase.REVIEW_REQUESTED:
        return TaskPhase.REVIEW_WAIT
    if state.phase == TaskPhase.FIXING_REVIEW:
        return TaskPhase.IMPLEMENTING
    return state.phase


def decide_next_task_transition(
    state: TaskState,
    *,
    decided_at: str,
    decision_id: str | None = None,
    wait_to_start: WaitPolicy | None = None,
) -> WorkflowDecision:
    """Return the contract decision for the next deterministic task transition.

    The legacy phase helper is intentionally still available for call sites that
    only need a sketch. New workflow code should use this function so blocked
    outcomes carry their durable ``Blocker`` and same-phase waits carry a durable
    ``WaitPolicy`` instead of being mistaken for progress.
    """
    next_phase = next_task_phase(state)
    progress_signal = TASK_TRANSITION_SIGNALS.get((state.phase, next_phase))

    if state.blocker:
        return WorkflowDecision(
            decision_id=decision_id or f"{state.id}:{state.phase}:blocked",
            decided_at=decided_at,
            from_phase=state.phase,
            to_phase=next_phase,
            material_progress=True,
            progress_signal=ProgressSignal.BLOCKER_CREATED,
            blocker_to_record=state.blocker,
        )

    if progress_signal == ProgressSignal.WAIT_TIMER_STARTED:
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
            raise ValueError("same-phase task transitions require a durable wait policy")
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
