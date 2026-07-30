"""Temporal-style software project driver skeleton.

The project driver owns lifecycle phases and creates task-driver work.
It should not perform repo/GitHub/Hermes side effects directly.
"""

from __future__ import annotations

from el_zachariahs_drivers.models import ProjectIntakePhase, ProjectState, TaskPhase


def next_project_phase(state: ProjectState) -> ProjectIntakePhase:
    """Pure phase transition sketch for the software project lifecycle."""
    if state.blocker:
        return ProjectIntakePhase.BLOCKED_NEEDS_EL_LE
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
    return state.phase
