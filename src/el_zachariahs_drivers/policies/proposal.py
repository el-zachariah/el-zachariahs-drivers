"""Proposal/source-discovery gate helpers for Workflow V2.

These helpers are intentionally pure so the workflow can persist the evidence and
replay the same gate decision without depending on chat memory or adapter state.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from el_zachariahs_drivers.models import (
    ApprovedTargetBinding,
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
    return ProposalGateCheck(
        status=ProposalGateStatus.APPROVED,
        proposal_required=True,
        approved_binding_version=project.approved_target_binding.version,
    )


def _values_match(approved: str | int | None, candidate: str | int | None) -> bool:
    return candidate is None or approved == candidate


def target_matches_binding(binding: ApprovedTargetBinding, candidate: TargetSurface) -> TargetBindingCheck:
    """Check that a proposed target is still the approved target.

    Missing candidate fields are treated as unspecified, not as permission to
    drift. Provided fields must match the approved binding exactly.
    """
    fields = ("url", "port", "service_identity", "cwd", "repo", "worktree", "owner_profile")
    failures = [
        f"{field} mismatch: approved={getattr(binding.target, field)!r} candidate={getattr(candidate, field)!r}"
        for field in fields
        if not _values_match(getattr(binding.target, field), getattr(candidate, field))
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
