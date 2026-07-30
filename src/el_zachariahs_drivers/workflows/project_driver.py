"""Temporal-style software project driver skeleton.

The project driver owns lifecycle phases and creates task-driver work.
It should not perform repo/GitHub/Hermes side effects directly.
"""

from __future__ import annotations

from el_zachariahs_drivers.models import ProjectPhase, ProjectState, TaskPhase


def next_project_phase(state: ProjectState) -> ProjectPhase:
    """Pure phase transition sketch for the software project lifecycle."""
    if state.blocker:
        return ProjectPhase.BLOCKED
    if state.phase == ProjectPhase.PROJECT_ASSIGNED:
        return ProjectPhase.PROJECT_PLANNING
    if state.phase == ProjectPhase.PROJECT_PLANNING:
        return ProjectPhase.TASK_BREAKDOWN
    if state.phase == ProjectPhase.TASK_BREAKDOWN and state.tasks:
        return ProjectPhase.TASK_EXECUTION
    if state.phase == ProjectPhase.TASK_EXECUTION:
        if all(task.phase == TaskPhase.COMPLETE for task in state.tasks):
            return ProjectPhase.PR_INTEGRATION
        return ProjectPhase.TASK_EXECUTION
    if state.phase == ProjectPhase.PR_INTEGRATION and state.pr_url:
        return ProjectPhase.REVIEW_PHASE
    return state.phase
