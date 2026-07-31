"""Shared durable-state and workflow-contract models.

Keep these models boring and explicit. Durable workflows should persist typed state,
not rely on chat transcript memory or adapter-private state.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectIntakePhase(StrEnum):
    PROJECT_INTAKE_ASSIGNED = "PROJECT_INTAKE_ASSIGNED"
    PLANNING = "PLANNING"
    PLAN_REVIEW = "PLAN_REVIEW"
    PLAN_RETHINK = "PLAN_RETHINK"
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
    TASK_ASSIGNED = "TASK_ASSIGNED"
    INSPECTING = "INSPECTING"
    CLAIMED = "CLAIMED"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    REVIEW_WAIT = "REVIEW_WAIT"
    FIXING_REVIEW = "FIXING_REVIEW"
    RESCOPE_REQUESTED = "RESCOPE_REQUESTED"
    COMPLETE = "COMPLETE"
    BLOCKED_NEEDS_EL_LE = "BLOCKED_NEEDS_EL_LE"
    BLOCKED_NEEDS_ZO_EL = "BLOCKED_NEEDS_ZO_EL"


class ProgressSignal(StrEnum):
    PROJECT_ACCEPTED = "PROJECT_ACCEPTED"
    PLAN_CREATED = "PLAN_CREATED"
    PLAN_REVIEW_REQUESTED = "PLAN_REVIEW_REQUESTED"
    PLAN_APPROVED = "PLAN_APPROVED"
    PLAN_REVISED = "PLAN_REVISED"
    TASKS_CREATED = "TASKS_CREATED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_RESCOPE_REQUESTED = "TASK_RESCOPE_REQUESTED"
    PR_CREATED = "PR_CREATED"
    PR_UPDATED = "PR_UPDATED"
    PR_HEAD_CHANGED = "PR_HEAD_CHANGED"
    TEST_EVIDENCE_CREATED = "TEST_EVIDENCE_CREATED"
    PROOF_AUTH_REQUESTED = "PROOF_AUTH_REQUESTED"
    PROOF_STARTED = "PROOF_STARTED"
    PROOF_EVIDENCE_CREATED = "PROOF_EVIDENCE_CREATED"
    PROOF_COMPLETED = "PROOF_COMPLETED"
    PROOF_REPAIR_REQUIRED = "PROOF_REPAIR_REQUIRED"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    REVIEW_STARTED = "REVIEW_STARTED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"
    REVIEW_FINDINGS_ACCEPTED = "REVIEW_FINDINGS_ACCEPTED"
    REVIEW_FINDINGS_FIXED = "REVIEW_FINDINGS_FIXED"
    FEEDBACK_REQUESTED = "FEEDBACK_REQUESTED"
    FEEDBACK_RECEIVED = "FEEDBACK_RECEIVED"
    DOGFOOD_STARTED = "DOGFOOD_STARTED"
    DOGFOOD_COMPLETED = "DOGFOOD_COMPLETED"
    MERGE_READY = "MERGE_READY"
    RELEASE_COMPLETED = "RELEASE_COMPLETED"
    BLOCKER_CREATED = "BLOCKER_CREATED"
    BLOCKER_ESCALATED = "BLOCKER_ESCALATED"
    BLOCKER_RESOLVED = "BLOCKER_RESOLVED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    WAIT_TIMER_STARTED = "WAIT_TIMER_STARTED"
    FINAL_REPORT_DELIVERED = "FINAL_REPORT_DELIVERED"


class RunOutcome(StrEnum):
    MATERIAL_PROGRESS = "MATERIAL_PROGRESS"
    CONTROLLED_WAIT = "CONTROLLED_WAIT"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    FAILED = "FAILED"
    STALLED = "STALLED"


class TerminalOutcome(StrEnum):
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DriverKind(StrEnum):
    SOFTWARE_PROJECT = "SoftwareProjectDriver"
    SOFTWARE_TASK = "SoftwareTaskDriver"


class WorkflowRole(StrEnum):
    PROJECT_INTAKE_OWNER = "project_intake_owner"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    PROOF_RUNNER = "proof_runner"
    PROCESS_STEWARD = "process_steward"
    HUMAN_APPROVER = "human_approver"


class ActorKind(StrEnum):
    AGENT = "agent"
    HUMAN = "human"
    SERVICE = "service"


class ActivitySideEffect(StrEnum):
    NONE = "none"
    GIT_BRANCH = "git_branch"
    GIT_COMMIT = "git_commit"
    CHANGE_ARTIFACT = "change_artifact"
    PULL_REQUEST = "pull_request"
    REVIEW = "review"
    COMMAND = "command"
    EXTERNAL_SERVICE = "external_service"
    USER_MESSAGE = "user_message"


class EvidenceType(StrEnum):
    PLAN = "plan"
    TASK = "task"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    REVIEW = "review"
    COMMAND = "command"
    PROOF = "proof"
    REPORT = "report"
    ADAPTER_RECORD = "adapter_record"
    PROFILE = "profile"


class WaitThresholdResponse(StrEnum):
    BLOCKED_NEEDS_EL_LE = "BLOCKED_NEEDS_EL_LE"
    BLOCKED_NEEDS_ZO_EL = "BLOCKED_NEEDS_ZO_EL"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    FAILED = "FAILED"


class DriverActor(StrEnum):
    EL_ZACHARIAH = "el-zachariah"
    MICAIAH = "el-micaiah"
    EL_LE = "el-le"
    ZO_EL = "zo-el"


class EvidenceRef(BaseModel):
    type: EvidenceType
    uri: str
    digest: str | None = None


class ResumeDecisionOption(BaseModel):
    decision: str
    resulting_phase: str
    notes: str


class ResumeTarget(BaseModel):
    blocked_phase: str
    resume_phase_if_unblocked: str
    resume_activity: str | None = None
    decision_options: list[ResumeDecisionOption] = Field(min_length=1)


class Blocker(BaseModel):
    """Canonical non-terminal blocker contract.

    `owner` is retained for current council-specific policy helpers. The reusable
    contract fields are `owner_role`, `required_decision`, `evidence_refs`, and
    `resume_target`.
    """

    reason: str
    category: Literal["developer", "process", "human_authority", "resource", "product", "external"]
    owner_role: WorkflowRole
    required_decision: str
    resume_target: ResumeTarget
    owner: DriverActor | None = None
    intake_outcome_preserved: bool = True
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class DriverInput(BaseModel):
    intake_id: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    input_digest: str


class CurrentActivity(BaseModel):
    activity_id: str
    role: WorkflowRole
    requested_at: str
    deadline_at: str | None = None


class WaitPolicy(BaseModel):
    awaited_signal: str
    started_at: str
    threshold_at: str
    retry_policy: str
    threshold_response: WaitThresholdResponse


class ProgressLedger(BaseModel):
    last_material_progress_at: str | None = None
    last_progress_signal: ProgressSignal | None = None
    no_op_observation_count: int = 0


class WorkflowCounters(BaseModel):
    review_loop_count: int | None = None
    retry_count: int = 0


class TerminalState(BaseModel):
    outcome: TerminalOutcome
    reason: str | None = None
    final_report_ref: str | None = None


class WorkflowStateRecord(BaseModel):
    workflow_id: str
    template_id: str
    template_version: str
    driver_kind: DriverKind
    phase: str
    input: DriverInput
    role_bindings_version: str
    plan_version: str | None = None
    current_activity: CurrentActivity | None = None
    wait: WaitPolicy | None = None
    blocker: Blocker | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    progress_ledger: ProgressLedger = Field(default_factory=ProgressLedger)
    counters: WorkflowCounters = Field(default_factory=WorkflowCounters)
    terminal: TerminalState | None = None


class WorkflowEvent(BaseModel):
    event_id: str
    type: str
    emitted_at: str
    source_role: WorkflowRole
    correlation_id: str
    causation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TimeoutPolicy(BaseModel):
    start_to_close: str
    schedule_to_close: str


class RetryPolicy(BaseModel):
    max_attempts: int = Field(ge=1)
    backoff: str


class ActivityFailurePolicy(BaseModel):
    rescope_allowed: bool
    blocker_owner_role: WorkflowRole


class ActivityRequest(BaseModel):
    activity_id: str
    activity_type: str
    role: WorkflowRole
    purpose: str
    input_refs: list[EvidenceRef] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(min_length=1)
    allowed_side_effects: list[ActivitySideEffect] = Field(default_factory=lambda: [ActivitySideEffect.NONE])
    required_evidence: list[str] = Field(default_factory=list)
    idempotency_key: str
    timeout_policy: TimeoutPolicy
    retry_policy: RetryPolicy
    on_failure: ActivityFailurePolicy


class WorkflowDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    decided_at: str
    from_phase: str
    to_phase: str
    material_progress: bool = False
    progress_signal: ProgressSignal | None = None
    activities_to_schedule: list[ActivityRequest] = Field(default_factory=list, max_length=1)
    wait_to_start: WaitPolicy | None = None
    blocker_to_record: Blocker | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    terminal_outcome: TerminalOutcome | None = None

    @model_validator(mode="after")
    def enforce_run_invariant(self) -> WorkflowDecision:
        if self.from_phase == self.to_phase and not any(
            (
                self.material_progress,
                self.progress_signal,
                self.activities_to_schedule,
                self.wait_to_start,
                self.blocker_to_record,
                self.evidence_refs,
                self.terminal_outcome,
            )
        ):
            raise ValueError(
                "same-phase decisions must record progress, activity, wait, blocker, evidence, or terminal outcome"
            )
        controlled_wait_signals = {ProgressSignal.RETRY_SCHEDULED, ProgressSignal.WAIT_TIMER_STARTED}
        if self.progress_signal in controlled_wait_signals and self.wait_to_start is None:
            raise ValueError("controlled wait signals require wait_to_start")
        if self.progress_signal in controlled_wait_signals and self.material_progress:
            raise ValueError("controlled wait signals cannot be material progress")
        if (
            self.progress_signal
            and not self.material_progress
            and self.progress_signal not in controlled_wait_signals
        ):
            raise ValueError("material progress signals require material_progress=True")
        if self.terminal_outcome and any(
            (self.activities_to_schedule, self.wait_to_start, self.blocker_to_record)
        ):
            raise ValueError(
                "terminal decisions cannot schedule activities, start waits, or record blockers"
            )
        return self


class RoleBinding(BaseModel):
    role: WorkflowRole
    actor: str
    kind: ActorKind
    adapter: str


class RuntimeProfile(BaseModel):
    profile_id: str
    version: str
    description: str
    role_bindings: list[RoleBinding]

    @model_validator(mode="after")
    def require_unique_roles(self) -> RuntimeProfile:
        roles = [binding.role for binding in self.role_bindings]
        if len(roles) != len(set(roles)):
            raise ValueError("runtime profiles must bind each role at most once")
        return self

    def actor_for(self, role: WorkflowRole) -> str:
        for binding in self.role_bindings:
            if binding.role == role:
                return binding.actor
        raise KeyError(f"role is not bound in this profile: {role}")


class TaskState(BaseModel):
    id: str
    title: str
    phase: TaskPhase = TaskPhase.TASK_ASSIGNED
    owner: DriverActor = DriverActor.EL_ZACHARIAH
    acceptance: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    blocker: Blocker | None = None
    review_loop_count: int = 0
    max_review_loops: int = 3
    rescope_reason: str | None = None


class ProjectState(BaseModel):
    id: str
    title: str
    phase: ProjectIntakePhase = ProjectIntakePhase.PROJECT_INTAKE_ASSIGNED
    tasks: list[TaskState] = Field(default_factory=list)
    current_task_id: str | None = None
    pr_url: str | None = None
    last_progress: ProgressSignal | None = None
    blocker: Blocker | None = None
