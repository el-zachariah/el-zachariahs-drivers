"""Template-level phase policies for software project and task drivers.

The engine contract validates generic run invariants. These policies add the
software-delivery template rules: which phases may emit which signals, which
phases are controlled waits, which phases may record blockers, and which phases
are terminal for each driver kind.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from el_zachariahs_drivers.models import (
    DriverKind,
    ProgressSignal,
    ProjectIntakePhase,
    RunOutcome,
    TaskPhase,
    TerminalOutcome,
    WaitThresholdResponse,
    WorkflowDecision,
    WorkflowRole,
)
from el_zachariahs_drivers.policies.progress import classify_run_outcome


@dataclass(frozen=True)
class PhasePolicy:
    """Allowed outcomes and controls for one template phase."""

    phase: str
    progress_signals: frozenset[ProgressSignal] = frozenset()
    wait_signals: frozenset[ProgressSignal] = frozenset()
    blocker_owner_roles: frozenset[WorkflowRole] = frozenset()
    terminal_outcomes: frozenset[TerminalOutcome] = frozenset()

    @property
    def allowed_signals(self) -> frozenset[ProgressSignal]:
        return self.progress_signals | self.wait_signals


def _policy(
    phase: str,
    *,
    progress: set[ProgressSignal] | None = None,
    wait: set[ProgressSignal] | None = None,
    blockers: set[WorkflowRole] | None = None,
    terminal: set[TerminalOutcome] | None = None,
) -> PhasePolicy:
    return PhasePolicy(
        phase=phase,
        progress_signals=frozenset(progress or ()),
        wait_signals=frozenset(wait or ()),
        blocker_owner_roles=frozenset(blockers or ()),
        terminal_outcomes=frozenset(terminal or ()),
    )


_CONTROLLED_WAIT = {ProgressSignal.WAIT_TIMER_STARTED, ProgressSignal.RETRY_SCHEDULED}
_ANY_BLOCKER_OWNER = frozenset(WorkflowRole)
_PROCESS_OR_HUMAN_BLOCKER = {
    WorkflowRole.PROCESS_STEWARD,
    WorkflowRole.HUMAN_APPROVER,
}
_HUMAN_BLOCKER = {WorkflowRole.HUMAN_APPROVER}

PROJECT_PHASE_POLICIES: Mapping[str, PhasePolicy] = {
    ProjectIntakePhase.PROJECT_INTAKE_ASSIGNED: _policy(
        ProjectIntakePhase.PROJECT_INTAKE_ASSIGNED,
        progress={ProgressSignal.PROJECT_ACCEPTED},
        blockers={WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.PLANNING: _policy(
        ProjectIntakePhase.PLANNING,
        progress={ProgressSignal.PLAN_CREATED},
        blockers=_PROCESS_OR_HUMAN_BLOCKER,
    ),
    ProjectIntakePhase.PLAN_REVIEW: _policy(
        ProjectIntakePhase.PLAN_REVIEW,
        progress={ProgressSignal.PLAN_APPROVED, ProgressSignal.PLAN_REVISED},
        wait=_CONTROLLED_WAIT,
        blockers={WorkflowRole.REVIEWER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.PLAN_RETHINK: _policy(
        ProjectIntakePhase.PLAN_RETHINK,
        progress={ProgressSignal.PLAN_REVISED},
        blockers=_PROCESS_OR_HUMAN_BLOCKER,
    ),
    ProjectIntakePhase.TASK_BREAKDOWN: _policy(
        ProjectIntakePhase.TASK_BREAKDOWN,
        progress={ProgressSignal.TASKS_CREATED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.TASK_EXECUTION: _policy(
        ProjectIntakePhase.TASK_EXECUTION,
        progress={ProgressSignal.TASK_COMPLETED, ProgressSignal.TASK_RESCOPE_REQUESTED},
        wait=_CONTROLLED_WAIT,
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.PR_OPEN: _policy(
        ProjectIntakePhase.PR_OPEN,
        progress={ProgressSignal.PR_CREATED, ProgressSignal.PR_UPDATED, ProgressSignal.PR_HEAD_CHANGED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.REVIEW_REQUESTED: _policy(
        ProjectIntakePhase.REVIEW_REQUESTED,
        progress={ProgressSignal.REVIEW_REQUESTED},
        wait=_CONTROLLED_WAIT,
        blockers={WorkflowRole.REVIEWER, WorkflowRole.PROCESS_STEWARD},
    ),
    ProjectIntakePhase.REVIEW_WAIT: _policy(
        ProjectIntakePhase.REVIEW_WAIT,
        progress={ProgressSignal.REVIEW_STARTED, ProgressSignal.REVIEW_COMPLETED},
        wait=_CONTROLLED_WAIT,
        blockers={WorkflowRole.REVIEWER, WorkflowRole.PROCESS_STEWARD},
    ),
    ProjectIntakePhase.FIXING_REVIEW: _policy(
        ProjectIntakePhase.FIXING_REVIEW,
        progress={ProgressSignal.REVIEW_FINDINGS_ACCEPTED, ProgressSignal.REVIEW_FINDINGS_FIXED, ProgressSignal.PR_UPDATED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.PROOF_AUTH_WAIT: _policy(
        ProjectIntakePhase.PROOF_AUTH_WAIT,
        progress={ProgressSignal.PROOF_AUTH_REQUESTED},
        wait=_CONTROLLED_WAIT,
        blockers=_HUMAN_BLOCKER,
    ),
    ProjectIntakePhase.PROOF_RUNNING: _policy(
        ProjectIntakePhase.PROOF_RUNNING,
        progress={ProgressSignal.PROOF_STARTED, ProgressSignal.PROOF_EVIDENCE_CREATED, ProgressSignal.PROOF_COMPLETED},
        wait=_CONTROLLED_WAIT,
        blockers={WorkflowRole.PROOF_RUNNER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.PROOF_REPAIR: _policy(
        ProjectIntakePhase.PROOF_REPAIR,
        progress={ProgressSignal.PROOF_REPAIR_REQUIRED, ProgressSignal.PROOF_EVIDENCE_CREATED, ProgressSignal.PROOF_COMPLETED},
        blockers={WorkflowRole.PROOF_RUNNER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.FEEDBACK_READY: _policy(
        ProjectIntakePhase.FEEDBACK_READY,
        progress={ProgressSignal.FEEDBACK_REQUESTED},
        blockers={WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    ProjectIntakePhase.FEEDBACK_WAIT: _policy(
        ProjectIntakePhase.FEEDBACK_WAIT,
        progress={ProgressSignal.FEEDBACK_RECEIVED},
        wait=_CONTROLLED_WAIT,
        blockers=_HUMAN_BLOCKER,
    ),
    ProjectIntakePhase.DOGFOOD_GATE: _policy(
        ProjectIntakePhase.DOGFOOD_GATE,
        progress={ProgressSignal.DOGFOOD_STARTED, ProgressSignal.DOGFOOD_COMPLETED},
        blockers=_HUMAN_BLOCKER,
    ),
    ProjectIntakePhase.MERGE_GATE: _policy(
        ProjectIntakePhase.MERGE_GATE,
        progress={ProgressSignal.MERGE_READY, ProgressSignal.RELEASE_COMPLETED},
        blockers=_HUMAN_BLOCKER,
    ),
    ProjectIntakePhase.FINAL_REPORT: _policy(
        ProjectIntakePhase.FINAL_REPORT,
        progress={ProgressSignal.FINAL_REPORT_DELIVERED},
        terminal={TerminalOutcome.DONE},
    ),
    ProjectIntakePhase.DONE: _policy(
        ProjectIntakePhase.DONE,
        terminal={TerminalOutcome.DONE},
    ),
    ProjectIntakePhase.BLOCKED_NEEDS_EL_LE: _policy(
        ProjectIntakePhase.BLOCKED_NEEDS_EL_LE,
        progress={ProgressSignal.BLOCKER_RESOLVED},
        wait=_CONTROLLED_WAIT,
        blockers=_ANY_BLOCKER_OWNER,
    ),
    ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL: _policy(
        ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL,
        progress={ProgressSignal.BLOCKER_RESOLVED},
        wait=_CONTROLLED_WAIT,
        blockers=_ANY_BLOCKER_OWNER,
    ),
}

TASK_PHASE_POLICIES: Mapping[str, PhasePolicy] = {
    TaskPhase.TASK_ASSIGNED: _policy(
        TaskPhase.TASK_ASSIGNED,
        progress={ProgressSignal.TASK_STARTED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    TaskPhase.CLAIMED: _policy(
        TaskPhase.CLAIMED,
        progress={ProgressSignal.TASK_STARTED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    TaskPhase.INSPECTING: _policy(
        TaskPhase.INSPECTING,
        progress={ProgressSignal.TASK_STARTED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    TaskPhase.IMPLEMENTING: _policy(
        TaskPhase.IMPLEMENTING,
        progress={ProgressSignal.TEST_EVIDENCE_CREATED, ProgressSignal.PR_UPDATED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    TaskPhase.TESTING: _policy(
        TaskPhase.TESTING,
        progress={ProgressSignal.REVIEW_REQUESTED, ProgressSignal.TEST_EVIDENCE_CREATED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    TaskPhase.REVIEW_REQUESTED: _policy(
        TaskPhase.REVIEW_REQUESTED,
        progress={ProgressSignal.REVIEW_REQUESTED},
        wait=_CONTROLLED_WAIT,
        blockers={WorkflowRole.REVIEWER, WorkflowRole.PROCESS_STEWARD},
    ),
    TaskPhase.REVIEW_WAIT: _policy(
        TaskPhase.REVIEW_WAIT,
        progress={ProgressSignal.REVIEW_STARTED, ProgressSignal.REVIEW_COMPLETED},
        wait=_CONTROLLED_WAIT,
        blockers={WorkflowRole.REVIEWER, WorkflowRole.PROCESS_STEWARD},
    ),
    TaskPhase.FIXING_REVIEW: _policy(
        TaskPhase.FIXING_REVIEW,
        progress={ProgressSignal.REVIEW_FINDINGS_ACCEPTED, ProgressSignal.REVIEW_FINDINGS_FIXED},
        blockers={WorkflowRole.DEVELOPER, WorkflowRole.PROCESS_STEWARD, WorkflowRole.HUMAN_APPROVER},
    ),
    TaskPhase.RESCOPE_REQUESTED: _policy(
        TaskPhase.RESCOPE_REQUESTED,
        progress={ProgressSignal.TASK_RESCOPE_REQUESTED},
        terminal={TerminalOutcome.CANCELLED, TerminalOutcome.FAILED},
    ),
    TaskPhase.COMPLETE: _policy(
        TaskPhase.COMPLETE,
        progress={ProgressSignal.TASK_COMPLETED},
        terminal={TerminalOutcome.DONE},
    ),
    TaskPhase.BLOCKED_NEEDS_EL_LE: _policy(
        TaskPhase.BLOCKED_NEEDS_EL_LE,
        progress={ProgressSignal.BLOCKER_RESOLVED},
        wait=_CONTROLLED_WAIT,
        blockers=_ANY_BLOCKER_OWNER,
    ),
    TaskPhase.BLOCKED_NEEDS_ZO_EL: _policy(
        TaskPhase.BLOCKED_NEEDS_ZO_EL,
        progress={ProgressSignal.BLOCKER_RESOLVED},
        wait=_CONTROLLED_WAIT,
        blockers=_ANY_BLOCKER_OWNER,
    ),
}

TEMPLATE_PHASE_POLICIES: Mapping[DriverKind, Mapping[str, PhasePolicy]] = {
    DriverKind.SOFTWARE_PROJECT: PROJECT_PHASE_POLICIES,
    DriverKind.SOFTWARE_TASK: TASK_PHASE_POLICIES,
}


def phase_policy_for(driver_kind: DriverKind, phase: str) -> PhasePolicy:
    """Return the policy for a concrete template phase."""
    try:
        return TEMPLATE_PHASE_POLICIES[driver_kind][phase]
    except KeyError as exc:
        raise KeyError(f"no phase policy for {driver_kind}:{phase}") from exc


def validate_decision_against_phase_policy(
    driver_kind: DriverKind,
    decision: WorkflowDecision,
) -> WorkflowDecision:
    """Validate a decision against the phase policy for its source phase.

    Pydantic enforces generic contract invariants when ``WorkflowDecision`` is
    built. This function enforces template-specific allowed signals, durable wait
    semantics, blocker owner routes, and terminal outcomes.
    """
    policy = phase_policy_for(driver_kind, decision.from_phase)

    blocker_signals = {ProgressSignal.BLOCKER_CREATED, ProgressSignal.BLOCKER_ESCALATED}

    if decision.wait_to_start and decision.progress_signal not in policy.wait_signals:
        raise ValueError(f"phase {decision.from_phase} does not allow controlled waits")

    if (
        decision.progress_signal
        and decision.progress_signal not in policy.allowed_signals
        and not (decision.progress_signal in blocker_signals and decision.blocker_to_record)
    ):
        raise ValueError(
            f"signal {decision.progress_signal} is not allowed from {driver_kind}:{decision.from_phase}"
        )

    if decision.wait_to_start:
        if decision.wait_to_start.threshold_response == WaitThresholdResponse.FAILED:
            if TerminalOutcome.FAILED not in policy.terminal_outcomes:
                raise ValueError(f"phase {decision.from_phase} cannot fail from a wait threshold")
        elif decision.wait_to_start.threshold_response.value.startswith("BLOCKED_NEEDS_"):
            expected_owner = (
                WorkflowRole.HUMAN_APPROVER
                if decision.wait_to_start.threshold_response == WaitThresholdResponse.BLOCKED_NEEDS_ZO_EL
                else WorkflowRole.PROCESS_STEWARD
            )
            if expected_owner not in policy.blocker_owner_roles:
                raise ValueError(
                    f"phase {decision.from_phase} cannot escalate waits to {expected_owner}"
                )

    if decision.blocker_to_record:
        owner_role = decision.blocker_to_record.owner_role
        if owner_role not in policy.blocker_owner_roles:
            raise ValueError(f"blocker owner {owner_role} is not allowed from {driver_kind}:{decision.from_phase}")

    if decision.terminal_outcome and decision.terminal_outcome not in policy.terminal_outcomes:
        raise ValueError(
            f"terminal outcome {decision.terminal_outcome} is not allowed from {driver_kind}:{decision.from_phase}"
        )

    outcome = classify_run_outcome(
        [decision.progress_signal] if decision.progress_signal else [],
        blocker=decision.blocker_to_record,
        done=decision.terminal_outcome == TerminalOutcome.DONE,
        failed=decision.terminal_outcome in {TerminalOutcome.CANCELLED, TerminalOutcome.FAILED},
    )
    if outcome == RunOutcome.STALLED:
        raise ValueError("decision does not produce material progress, controlled wait, blocker, or terminal outcome")

    return decision
