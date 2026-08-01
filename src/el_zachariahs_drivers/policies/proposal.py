"""Proposal/source-discovery gate helpers for Workflow V2.

These helpers are intentionally pure so the workflow can persist the evidence and
replay the same gate decision without depending on chat memory or adapter state.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from el_zachariahs_drivers.models import (
    ApprovedTargetBinding,
    EvidenceRef,
    ProjectIntakePhase,
    ProjectState,
    ProposalGateStatus,
    TargetSurface,
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
        if not any(_target_identity_matches(binding.target, target) for target in source_targets):
            if not _has_explicit_substitute_approval(binding):
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
