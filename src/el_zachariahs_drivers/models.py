"""Shared state models for project and task drivers.

Keep these models boring and explicit. Durable workflows should persist typed state,
not rely on chat transcript memory.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ProjectPhase(StrEnum):
    PROJECT_ASSIGNED = "PROJECT_ASSIGNED"
    PROJECT_PLANNING = "PROJECT_PLANNING"
    TASK_BREAKDOWN = "TASK_BREAKDOWN"
    TASK_EXECUTION = "TASK_EXECUTION"
    PR_INTEGRATION = "PR_INTEGRATION"
    REVIEW_PHASE = "REVIEW_PHASE"
    PROOF_PHASE = "PROOF_PHASE"
    FEEDBACK_PHASE = "FEEDBACK_PHASE"
    DOGFOOD_OR_MERGE_GATE = "DOGFOOD_OR_MERGE_GATE"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


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
    phase: ProjectPhase = ProjectPhase.PROJECT_ASSIGNED
    tasks: list[TaskState] = Field(default_factory=list)
    current_task_id: str | None = None
    pr_url: str | None = None
    last_progress: ProgressSignal = ProgressSignal.NO_CHANGE
    blocker: Blocker | None = None
