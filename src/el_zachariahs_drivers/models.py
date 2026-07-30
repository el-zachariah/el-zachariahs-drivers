"""Shared state models for project and task drivers.

Keep these models boring and explicit. Durable workflows should persist typed state,
not rely on chat transcript memory.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ProjectIntakePhase(StrEnum):
    PROJECT_INTAKE_ASSIGNED = "PROJECT_INTAKE_ASSIGNED"
    PLANNING = "PLANNING"
    PLAN_REVIEW = "PLAN_REVIEW"
    TASK_BREAKDOWN = "TASK_BREAKDOWN"
    TASK_EXECUTION = "TASK_EXECUTION"
    PR_OPEN = "PR_OPEN"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    REVIEW_WAIT = "REVIEW_WAIT"
    FIXING_REVIEW = "FIXING_REVIEW"
    PROOF_AUTH_WAIT = "PROOF_AUTH_WAIT"
    PROOF_RUNNING = "PROOF_RUNNING"
    PROOF_REPAIR = "PROOF_REPAIR"
    FEEDBACK_READY = "FEEDBACK_READY"
    FEEDBACK_WAIT = "FEEDBACK_WAIT"
    DOGFOOD_GATE = "DOGFOOD_GATE"
    MERGE_GATE = "MERGE_GATE"
    FINAL_REPORT = "FINAL_REPORT"
    DONE = "DONE"
    BLOCKED_NEEDS_EL_LE = "BLOCKED_NEEDS_EL_LE"
    BLOCKED_NEEDS_ZO_EL = "BLOCKED_NEEDS_ZO_EL"


class TaskPhase(StrEnum):
    READY = "READY"
    CLAIMED = "CLAIMED"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FIXING_REVIEW = "FIXING_REVIEW"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


class ProgressSignal(StrEnum):
    PR_HEAD_CHANGED = "PR_HEAD_CHANGED"
    TEST_EVIDENCE_CREATED = "TEST_EVIDENCE_CREATED"
    PROOF_EVIDENCE_CREATED = "PROOF_EVIDENCE_CREATED"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    BLOCKER_ESCALATED = "BLOCKER_ESCALATED"
    STATE_ADVANCED = "STATE_ADVANCED"
    NO_CHANGE = "NO_CHANGE"


class DriverActor(StrEnum):
    EL_ZACHARIAH = "el-zachariah"
    MICAIAH = "el-micaiah"
    EL_LE = "el-lee"
    ZO_EL = "zo-el"


class Blocker(BaseModel):
    reason: str
    owner: DriverActor
    category: Literal["developer", "process", "human_authority", "resource", "product", "external"]


class TaskState(BaseModel):
    id: str
    title: str
    phase: TaskPhase = TaskPhase.READY
    owner: DriverActor = DriverActor.EL_ZACHARIAH
    acceptance: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    blocker: Blocker | None = None


class ProjectState(BaseModel):
    id: str
    title: str
    phase: ProjectIntakePhase = ProjectIntakePhase.PROJECT_INTAKE_ASSIGNED
    tasks: list[TaskState] = Field(default_factory=list)
    current_task_id: str | None = None
    pr_url: str | None = None
    last_progress: ProgressSignal = ProgressSignal.NO_CHANGE
    blocker: Blocker | None = None
