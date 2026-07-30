"""Temporal-style software task driver skeleton.

This file should stay deterministic when implemented as a real Temporal workflow.
Side effects belong in activities, not workflow code.
"""

from __future__ import annotations

from el_zachariahs_drivers.models import TaskPhase, TaskState


def next_task_phase(state: TaskState) -> TaskPhase:
    """Pure phase transition sketch for one bounded software task."""
    if state.blocker:
        return TaskPhase.BLOCKED
    if state.phase == TaskPhase.READY:
        return TaskPhase.CLAIMED
    if state.phase == TaskPhase.CLAIMED:
        return TaskPhase.IMPLEMENTING
    if state.phase == TaskPhase.IMPLEMENTING:
        return TaskPhase.TESTING
    if state.phase == TaskPhase.TESTING:
        return TaskPhase.REVIEW_REQUIRED
    if state.phase == TaskPhase.FIXING_REVIEW:
        return TaskPhase.TESTING
    return state.phase
