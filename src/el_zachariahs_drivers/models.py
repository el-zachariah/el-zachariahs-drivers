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


class ActivityStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"


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
    SOURCE_DISCOVERY = "source_discovery"
    PROPOSAL_APPROVAL = "proposal_approval"
    TARGET_BINDING = "target_binding"


class DiscoveryConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProposalGateStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED_MISSING = "required_missing"
    APPROVED = "approved"
    BLOCKED_OWNERSHIP = "blocked_ownership"
    TARGET_MISMATCH = "target_mismatch"


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


class TargetSurface(BaseModel):
    """A discovered or approved implementation surface.

    This is intentionally explicit because V2 must distinguish the live target
    the intake named from a substitute preview/replacement artifact.
    """

    label: str
    url: str | None = None
    port: int | None = None
    service_identity: str | None = None
    cwd: str | None = None
    repo: str | None = None
    worktree: str | None = None
    owner_profile: str | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class SourceDiscoveryReport(BaseModel):
    intake_id: str
    discovered_sources: list[TargetSurface] = Field(min_length=1)
    recommended_target: TargetSurface | None = None
    ownership_boundary: str | None = None
    confidence: DiscoveryConfidence
    required_next_gate: ProjectIntakePhase
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ProposalApprovalEvidence(BaseModel):
    proposal_id: str
    proposal_version: str
    proposal_digest: str
    approved_by: str
    approved_at: str
    approval_record: EvidenceRef
    covered_acceptance_criteria: list[str] = Field(min_length=1)


class ApprovedTargetBinding(BaseModel):
    """Versioned target binding emitted by human-reviewed proposal approval."""

    binding_id: str
    version: str
    target: TargetSurface
    proposal_id: str
    proposal_version: str
    proposal_digest: str
    approval_record: EvidenceRef
    approved_by: str
    covered_acceptance_criteria: list[str] = Field(min_length=1)
    allowed_side_effect_surfaces: list[TargetSurface] = Field(default_factory=list)
    approved_substitute_artifacts: list[EvidenceRef] = Field(default_factory=list)
    source_discovery_refs: list[EvidenceRef] = Field(default_factory=list)


class DriverAuthorizationEvidence(BaseModel):
    """Evidence that a material progress signal was authorized by the driver.

    Driver-test supervision may fix the driver or unblock process failures, but
    those supervisor actions must not be mistaken for initiative progress. A
    progress signal that claims to advance implementation/deploy/PR work must
    name the durable driver decision/activity and the approved target binding
    version it advances. Blank identifiers are invalid because they do not point
    auditors back to an actual persisted workflow decision/activity.
    """

    workflow_decision_id: str = Field(min_length=1)
    activity_id: str = Field(min_length=1)
    binding_version: str | None = Field(default=None, min_length=1)
    authorized_by_role: WorkflowRole
    supervisor_intervention: bool = False


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


class ActivityResultEnvelope(BaseModel):
    """Adapter-neutral result for one side-effecting activity attempt.

    Activity implementations may use Hermes, GitHub, local commands, CI, or fake
    test adapters. The durable workflow records this envelope rather than
    adapter-private state so replay can distinguish successful effects, failed
    attempts, and duplicate idempotency-key replays.
    """

    model_config = ConfigDict(extra="forbid")

    activity_id: str
    activity_type: str
    idempotency_key: str
    role: WorkflowRole
    status: ActivityStatus
    started_at: str
    finished_at: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    @model_validator(mode="after")
    def enforce_result_shape(self) -> ActivityResultEnvelope:
        if self.status == ActivityStatus.FAILED and not self.error:
            raise ValueError("failed activity results require error")
        if self.status != ActivityStatus.FAILED and self.error is not None:
            raise ValueError("only failed activity results may carry error")
        if self.status == ActivityStatus.SKIPPED_DUPLICATE and self.evidence_refs:
            raise ValueError("duplicate-skip results must not claim new evidence")
        return self


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
        blocked_signals = {ProgressSignal.BLOCKER_CREATED, ProgressSignal.BLOCKER_ESCALATED}
        blocked_phase_prefix = "BLOCKED_NEEDS_"
        terminal_phases_by_outcome = {
            TerminalOutcome.DONE: {"DONE", "COMPLETE"},
            TerminalOutcome.FAILED: {"FAILED"},
            TerminalOutcome.CANCELLED: {"CANCELLED"},
        }
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
        if self.material_progress and not any(
            (
                self.progress_signal,
                self.activities_to_schedule,
                self.blocker_to_record,
                self.evidence_refs,
                self.terminal_outcome,
            )
        ):
            raise ValueError(
                "material progress decisions require a progress signal, activity, blocker, evidence, or terminal outcome"
            )
        if self.terminal_outcome and any(
            (self.activities_to_schedule, self.wait_to_start, self.blocker_to_record)
        ):
            raise ValueError(
                "terminal decisions cannot schedule activities, start waits, or record blockers"
            )
        if self.terminal_outcome:
            terminal_phases = terminal_phases_by_outcome[self.terminal_outcome]
            if self.to_phase not in terminal_phases:
                raise ValueError(
                    "terminal decisions must transition to a terminal phase matching terminal_outcome"
                )
        if (
            self.to_phase.startswith(blocked_phase_prefix)
            or self.progress_signal in blocked_signals
        ) and self.blocker_to_record is None:
            raise ValueError("blocked decisions require blocker_to_record")
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
    proposal_required: bool = False
    source_discovery: SourceDiscoveryReport | None = None
    proposal_approval: ProposalApprovalEvidence | None = None
    approved_target_binding: ApprovedTargetBinding | None = None
    tasks: list[TaskState] = Field(default_factory=list)
    current_task_id: str | None = None
    pr_url: str | None = None
    last_progress: ProgressSignal | None = None
    blocker: Blocker | None = None
