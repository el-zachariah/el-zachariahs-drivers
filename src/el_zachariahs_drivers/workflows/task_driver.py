"""Temporal-style software task driver skeleton.

This file should stay deterministic when implemented as a real Temporal workflow.
Side effects belong in activities, not workflow code.
"""

from __future__ import annotations

from el_zachariahs_drivers.models import TaskPhase, TaskState


def next_task_phase(state: TaskState) -> TaskPhase:
    """Pure phase transition sketch for one bounded software task."""
    if state.blocker:
        return TaskPhase.BLOCKED_NEEDS_EL_LE
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
