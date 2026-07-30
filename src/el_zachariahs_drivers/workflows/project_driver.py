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
    if state.phase == ProjectIntakePhase.PROJECT_INTAKE:
        return ProjectIntakePhase.PROJECT_SCOPING
    if state.phase == ProjectIntakePhase.PROJECT_SCOPING:
        return ProjectIntakePhase.PROJECT_PLANNING
    if state.phase == ProjectIntakePhase.PROJECT_PLANNING:
        return ProjectIntakePhase.TASK_BREAKDOWN
    if state.phase == ProjectIntakePhase.TASK_BREAKDOWN and state.tasks:
        return ProjectIntakePhase.TASK_EXECUTION
    if state.phase == ProjectIntakePhase.TASK_EXECUTION:
        if all(task.phase == TaskPhase.COMPLETE for task in state.tasks):
            return ProjectIntakePhase.INTEGRATION
        return ProjectIntakePhase.TASK_EXECUTION
    if state.phase == ProjectIntakePhase.INTEGRATION and state.pr_url:
        return ProjectIntakePhase.REVIEW_GATE
    return state.phase
