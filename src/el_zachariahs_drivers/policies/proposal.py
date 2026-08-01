"""Proposal/source-discovery gate helpers for Workflow V2.

These helpers are intentionally pure so the workflow can persist the evidence and
replay the same gate decision without depending on chat memory or adapter state.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from el_zachariahs_drivers.models import (
    AcceptanceReport,
    ApprovedTargetBinding,
    Blocker,
    DriverActor,
    DriverAuthorizationEvidence,
    EvidenceRef,
    ProjectIntakePhase,
    ProjectState,
    ProposalGateStatus,
    ResumeDecisionOption,
    ResumeTarget,
    TargetSurface,
    WorkflowRole,
)


class ProposalGateCheck(BaseModel):
    status: ProposalGateStatus
    proposal_required: bool
    approved_binding_version: str | None = None
    failures: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {ProposalGateStatus.NOT_REQUIRED, ProposalGateStatus.APPROVED}


class TargetBindingCheck(BaseModel):
    status: ProposalGateStatus
    binding_version: str | None = None
    failures: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == ProposalGateStatus.APPROVED


class ProjectTransitionGateCheck(BaseModel):
    ok: bool
    failures: list[str] = Field(default_factory=list)
    blocker: Blocker | None = None


class AcceptanceProofCheck(BaseModel):
    ok: bool
    failures: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


GATED_IMPLEMENTATION_PHASES = {
    ProjectIntakePhase.TASK_BREAKDOWN,
    ProjectIntakePhase.TASK_EXECUTION,
    ProjectIntakePhase.PR_OPEN,
}

DRIVER_AUTHORIZED_PROGRESS_PHASES = {
    ProjectIntakePhase.TASK_EXECUTION,
    ProjectIntakePhase.PR_OPEN,
    ProjectIntakePhase.REVIEW_REQUESTED,
}


def check_proposal_gate(project: ProjectState) -> ProposalGateCheck:
    """Return whether an ambiguous initiative may advance past planning.

    Slice A records the shape and status of the gate. Slice B wires this into
    transition enforcement, but callers can already expose durable status.
    """
    if not project.proposal_required:
        return ProposalGateCheck(status=ProposalGateStatus.NOT_REQUIRED, proposal_required=False)
    if project.approved_target_binding is None:
        return ProposalGateCheck(
            status=ProposalGateStatus.REQUIRED_MISSING,
            proposal_required=True,
            failures=["proposal approval must produce an approved target binding"],
        )
    status, failures = _binding_evidence_failures(project)
    if failures:
        return ProposalGateCheck(
            status=status,
            proposal_required=True,
            approved_binding_version=project.approved_target_binding.version,
            failures=failures,
        )
    return ProposalGateCheck(
        status=ProposalGateStatus.APPROVED,
        proposal_required=True,
        approved_binding_version=project.approved_target_binding.version,
    )


def _binding_evidence_failures(project: ProjectState) -> tuple[ProposalGateStatus, list[str]]:
    binding = project.approved_target_binding
    if binding is None:
        return ProposalGateStatus.REQUIRED_MISSING, ["proposal approval must produce an approved target binding"]

    failures: list[str] = []
    blocked_ownership = False
    target_mismatch = False
    if project.source_discovery is None:
        failures.append("source discovery report is required before proposal approval can pass")
    else:
        source_discovery = project.source_discovery
        if not source_discovery.evidence_refs:
            failures.append("source discovery report must include evidence refs")
        if source_discovery.required_next_gate in {
            ProjectIntakePhase.BLOCKED_NEEDS_EL_LE,
            ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL,
        }:
            blocked_ownership = True
            failures.append(
                f"ownership route is unresolved: source discovery requires {source_discovery.required_next_gate}"
            )
        elif binding.source_discovery_refs and not _refs_overlap(
            binding.source_discovery_refs, source_discovery.evidence_refs
        ):
            failures.append("approved target binding must cite the persisted source discovery evidence")

        source_targets = [source_discovery.recommended_target] if source_discovery.recommended_target else []
        source_targets.extend(source_discovery.discovered_sources)
        if not any(
            _target_identity_matches(binding.target, target) for target in source_targets
        ) and not _has_explicit_substitute_approval(binding):
            target_mismatch = True
            failures.append(
                "approved target is not the discovered/recommended target and no explicit approved substitute evidence is recorded"
            )

    if not binding.source_discovery_refs:
        failures.append("approved target binding must reference source discovery evidence")

    approval = project.proposal_approval
    if approval is None:
        failures.append("proposal approval evidence is required before proposal gate can pass")
        return _proposal_gate_failure_status(blocked_ownership, target_mismatch), failures

    if binding.proposal_id != approval.proposal_id:
        failures.append(
            f"proposal id mismatch: approval={approval.proposal_id!r} binding={binding.proposal_id!r}"
        )
    if binding.proposal_version != approval.proposal_version:
        failures.append(
            f"proposal version mismatch: approval={approval.proposal_version!r} binding={binding.proposal_version!r}"
        )
    if binding.proposal_digest != approval.proposal_digest:
        failures.append(
            f"proposal digest mismatch: approval={approval.proposal_digest!r} binding={binding.proposal_digest!r}"
        )
    if binding.approval_record != approval.approval_record:
        failures.append("approval record mismatch between proposal approval and target binding")
    if binding.approved_by != approval.approved_by:
        failures.append(
            f"approved_by mismatch: approval={approval.approved_by!r} binding={binding.approved_by!r}"
        )
    failures.extend(
        _criteria_mismatch_failures(
            approval.covered_acceptance_criteria,
            binding.covered_acceptance_criteria,
        )
    )
    return _proposal_gate_failure_status(blocked_ownership, target_mismatch), failures


def _proposal_gate_failure_status(blocked_ownership: bool, target_mismatch: bool) -> ProposalGateStatus:
    if blocked_ownership:
        return ProposalGateStatus.BLOCKED_OWNERSHIP
    if target_mismatch:
        return ProposalGateStatus.TARGET_MISMATCH
    return ProposalGateStatus.REQUIRED_MISSING


def _ref_key(ref: EvidenceRef) -> tuple[str, str, str | None]:
    return (str(ref.type), ref.uri, ref.digest)


def _refs_overlap(left: list[EvidenceRef], right: list[EvidenceRef]) -> bool:
    right_keys = {_ref_key(ref) for ref in right}
    return any(_ref_key(ref) in right_keys for ref in left)


def _criteria_mismatch_failures(approved: list[str], binding: list[str]) -> list[str]:
    approved_set = set(approved)
    binding_set = set(binding)
    failures: list[str] = []
    for criterion in sorted(approved_set - binding_set):
        failures.append(
            "approved target binding is missing proposal-approved acceptance criterion: "
            f"{criterion!r}"
        )
    for criterion in sorted(binding_set - approved_set):
        failures.append(
            "approved target binding includes acceptance criterion not present in proposal approval: "
            f"{criterion!r}"
        )
    return failures


def _target_identity_matches(left: TargetSurface, right: TargetSurface) -> bool:
    fields = ("url", "port", "service_identity", "cwd", "repo", "worktree", "owner_profile")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _has_explicit_substitute_approval(binding: ApprovedTargetBinding) -> bool:
    """Return whether a non-discovered target was explicitly approved as a substitute.

    The target binding cannot simply become the source of truth by naming a new
    surface. It must carry proposal-approved substitute evidence on both the
    binding and the substitute target so reviewers/auditors can see the bypass.
    """
    return bool(binding.approved_substitute_artifacts) and _refs_overlap(
        binding.approved_substitute_artifacts, binding.target.evidence_refs
    )


def _has_report_substitute_approval(
    binding: ApprovedTargetBinding,
    report: AcceptanceReport,
) -> bool:
    """Return whether acceptance proof may satisfy an approved substitute artifact.

    A substitute approval ref is not a bearer token that any later report target
    can copy onto itself. The approved substitute target must be represented in
    the binding's allowed side-effect/substitute surfaces, must carry the same
    approval evidence, and the report target must match that approved surface's
    identity. This keeps terminal acceptance tied to the specific substitute the
    human reviewed instead of any artifact that can cite the approval URI.
    """
    if not (
        binding.approved_substitute_artifacts
        and report.substitute_approval_refs
        and _refs_overlap(binding.approved_substitute_artifacts, report.substitute_approval_refs)
    ):
        return False

    return any(
        _target_identity_matches(approved_surface, report.target)
        and _refs_overlap(binding.approved_substitute_artifacts, approved_surface.evidence_refs)
        and _refs_overlap(report.substitute_approval_refs, report.target.evidence_refs)
        for approved_surface in binding.allowed_side_effect_surfaces
    )


def _field_failure(approved: str | int | None, candidate: str | int | None, field: str) -> str | None:
    if approved is None:
        return None if candidate is None else f"{field} unexpected: approved=None candidate={candidate!r}"
    if candidate is None:
        return f"missing candidate {field}: approved={approved!r}"
    if approved != candidate:
        return f"{field} mismatch: approved={approved!r} candidate={candidate!r}"
    return None


def target_matches_binding(binding: ApprovedTargetBinding, candidate: TargetSurface) -> TargetBindingCheck:
    """Check that a proposed target is still the approved target.

    Missing candidate fields are treated as unspecified, not as permission to
    drift. Provided fields must match the approved binding exactly.
    """
    fields = ("url", "port", "service_identity", "cwd", "repo", "worktree", "owner_profile")
    failures = [
        failure
        for field in fields
        if (failure := _field_failure(getattr(binding.target, field), getattr(candidate, field), field))
        is not None
    ]
    return TargetBindingCheck(
        status=ProposalGateStatus.APPROVED if not failures else ProposalGateStatus.TARGET_MISMATCH,
        binding_version=binding.version,
        failures=failures,
    )


def check_project_target_binding(project: ProjectState, candidate: TargetSurface) -> TargetBindingCheck:
    if project.approved_target_binding is None:
        return TargetBindingCheck(
            status=ProposalGateStatus.REQUIRED_MISSING,
            failures=["no approved target binding is recorded"],
        )
    return target_matches_binding(project.approved_target_binding, candidate)


def check_acceptance_proof(project: ProjectState) -> AcceptanceProofCheck:
    """Validate terminal DONE proof against the approved target and original criteria."""
    if not project.proposal_required:
        return AcceptanceProofCheck(ok=True)

    proposal_check = check_proposal_gate(project)
    failures = list(proposal_check.failures)
    if project.approved_target_binding is None:
        failures.append("approved target binding is required before DONE")
        return AcceptanceProofCheck(ok=False, failures=failures)

    binding = project.approved_target_binding
    report = project.acceptance_report
    if report is None:
        failures.append("acceptance report is required before DONE")
        return AcceptanceProofCheck(ok=False, failures=failures)

    if report.binding_version != binding.version:
        failures.append(
            "acceptance report binding version mismatch: "
            f"approved={binding.version!r} report={report.binding_version!r}"
        )

    target_check = target_matches_binding(binding, report.target)
    if not target_check.ok and not _has_report_substitute_approval(binding, report):
        failures.extend(target_check.failures)
        failures.append("substitute deliverable is not explicitly approved for terminal acceptance")

    proved_criteria = {proof.criterion for proof in report.criteria if proof.satisfied and proof.evidence_refs}
    required_criteria = list(binding.covered_acceptance_criteria)
    if project.proposal_approval is not None:
        for criterion in project.proposal_approval.covered_acceptance_criteria:
            if criterion not in required_criteria:
                required_criteria.append(criterion)
    for criterion in required_criteria:
        if criterion not in proved_criteria:
            failures.append(f"missing acceptance proof for original criterion: {criterion!r}")

    for proof in report.criteria:
        if not proof.satisfied:
            failures.append(f"acceptance criterion is not satisfied: {proof.criterion!r}")
        if not proof.evidence_refs:
            failures.append(f"acceptance criterion lacks evidence: {proof.criterion!r}")

    if not report.live_verification_required:
        failures.append("live verification is required for proposal-required terminal acceptance")
    if report.live_verification_passed is not True:
        failures.append("live verification is required for this acceptance report and has not passed")

    if not report.evidence_refs:
        failures.append("acceptance report must include evidence refs")

    return AcceptanceProofCheck(ok=not failures, failures=failures, evidence_refs=report.evidence_refs)


def check_project_transition_gate(
    project: ProjectState,
    *,
    next_phase: ProjectIntakePhase,
    candidate_target: TargetSurface | None = None,
    driver_authorization: DriverAuthorizationEvidence | None = None,
    driver_test_mode: bool = False,
) -> ProjectTransitionGateCheck:
    """Validate V2 process gates before allowing implementation/PR progress.

    Ambiguous projects cannot enter implementation/PR phases until the proposal
    gate passes, target evidence must still match the approved binding, and
    driver-test progress must cite a non-supervisor driver authorization.
    """
    if next_phase == project.phase:
        return ProjectTransitionGateCheck(ok=True)

    failures: list[str] = []
    status = ProposalGateStatus.APPROVED

    if project.proposal_required and next_phase in GATED_IMPLEMENTATION_PHASES:
        proposal_check = check_proposal_gate(project)
        if not proposal_check.ok:
            failures.extend(proposal_check.failures)
            status = proposal_check.status
        elif candidate_target is None:
            failures.append("candidate target evidence is required for implementation/PR phases")
            status = ProposalGateStatus.TARGET_MISMATCH
        else:
            target_check = check_project_target_binding(project, candidate_target)
            if not target_check.ok:
                failures.extend(target_check.failures)
                status = target_check.status

    if driver_test_mode and next_phase in DRIVER_AUTHORIZED_PROGRESS_PHASES:
        if driver_authorization is None:
            failures.append("driver-test material progress requires driver authorization evidence")
        elif driver_authorization.supervisor_intervention:
            failures.append("supervisor intervention cannot count as driver-authorized initiative progress")
        elif driver_authorization.authorized_by_role != WorkflowRole.DEVELOPER:
            failures.append(
                "driver-test material progress must be authorized by the developer role: "
                f"authorized_by_role={driver_authorization.authorized_by_role!r}"
            )
        elif (
            project.approved_target_binding is not None
            and driver_authorization.binding_version != project.approved_target_binding.version
        ):
            failures.append(
                "driver authorization binding version mismatch: "
                f"approved={project.approved_target_binding.version!r} "
                f"authorized={driver_authorization.binding_version!r}"
            )

    if not failures:
        return ProjectTransitionGateCheck(ok=True)
    return ProjectTransitionGateCheck(
        ok=False,
        failures=failures,
        blocker=_blocker_for_transition_gate(project.id, project.phase, next_phase, status, failures),
    )


def _blocker_for_transition_gate(
    project_id: str,
    from_phase: ProjectIntakePhase,
    next_phase: ProjectIntakePhase,
    status: ProposalGateStatus,
    failures: list[str],
) -> Blocker:
    if status == ProposalGateStatus.BLOCKED_OWNERSHIP:
        owner_role = WorkflowRole.PROCESS_STEWARD
        owner = DriverActor.EL_LE
        category = "process"
        required_decision = "route cross-profile target ownership and resume proposal review"
    else:
        owner_role = WorkflowRole.HUMAN_APPROVER
        owner = DriverActor.ZO_EL
        category = "human_authority"
        required_decision = "approve a source-backed proposal/target binding or request plan rethink"

    return Blocker(
        reason=f"V2 transition gate blocked {project_id} before {next_phase}: " + "; ".join(failures),
        category=category,
        owner=owner,
        owner_role=owner_role,
        required_decision=required_decision,
        resume_target=ResumeTarget(
            blocked_phase=str(from_phase),
            resume_phase_if_unblocked=str(ProjectIntakePhase.PLAN_REVIEW),
            resume_activity="review_source_backed_proposal",
            decision_options=[
                ResumeDecisionOption(
                    decision="proposal_approved_with_target_binding",
                    resulting_phase=str(ProjectIntakePhase.PLAN_REVIEW),
                    notes="Retry the gated transition after approved target binding and target evidence are persisted.",
                ),
                ResumeDecisionOption(
                    decision="plan_rethink_required",
                    resulting_phase=str(ProjectIntakePhase.PLAN_RETHINK),
                    notes="Return to plan rethink when target/source/authorization evidence does not match.",
                ),
            ],
        ),
    )
