"""Activity contracts for side-effecting operations.

Temporal workflows call activities for IO: GitHub, git, Hermes/Kanban, tests,
review routing, proof packets, and user/El-Le escalation. These protocols keep
workflow logic decoupled from specific tools.
"""

from __future__ import annotations

from typing import Protocol

from el_zachariahs_drivers.models import Blocker, ProjectState, TaskState


class ProjectActivities(Protocol):
    def create_plan_tasks(self, project: ProjectState) -> list[TaskState]: ...
    def open_or_update_pr(self, project: ProjectState) -> str: ...
    def request_review(self, project: ProjectState) -> None: ...
    def escalate_blocker(self, blocker: Blocker) -> None: ...


class TaskActivities(Protocol):
    def implement_task(self, task: TaskState) -> TaskState: ...
    def run_verification(self, task: TaskState) -> TaskState: ...
    def request_task_review(self, task: TaskState) -> TaskState: ...
