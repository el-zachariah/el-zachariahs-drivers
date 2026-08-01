import json
from pathlib import Path

from el_zachariahs_drivers.models import (
    ApprovedTargetBinding,
    DiscoveryConfidence,
    EvidenceRef,
    EvidenceType,
    ProjectIntakePhase,
    ProjectState,
    ProposalApprovalEvidence,
    ProposalGateStatus,
    SourceDiscoveryReport,
    TargetSurface,
)
from el_zachariahs_drivers.policies.proposal import (
    check_project_target_binding,
    check_proposal_gate,
)

FIXTURE = Path(__file__).parent / "fixtures" / "failed_local_agents_ui_run.json"


def evidence(uri: str, type_: EvidenceType = EvidenceType.SOURCE_DISCOVERY) -> EvidenceRef:
    return EvidenceRef(type=type_, uri=uri)


def load_failed_run_targets() -> tuple[TargetSurface, TargetSurface]:
    raw = json.loads(FIXTURE.read_text())
    return TargetSurface(**raw["original_target"]), TargetSurface(**raw["wrong_substitute"])


def approved_binding(target: TargetSurface) -> ApprovedTargetBinding:
    approval_ref = evidence("gh-pr://el-zachariah/el-zachariahs-drivers/24#approved", EvidenceType.PROPOSAL_APPROVAL)
    return ApprovedTargetBinding(
        binding_id="binding-local-agents-ui-v1",
        version="v1",
        target=target,
        proposal_id="proposal-local-agents-ui",
        proposal_version="v1",
        proposal_digest="sha256:proposal-digest",
        approval_record=approval_ref,
        approved_by="zo-el",
        covered_acceptance_criteria=[
            "upgrade the currently running local UI/dashboard for el-le brain and Micaiah"
        ],
        source_discovery_refs=[evidence("fixture://failed_local_agents_ui_run")],
    )


def test_source_discovery_captures_cross_profile_live_target_before_implementation():
    live_target, _wrong_substitute = load_failed_run_targets()

    report = SourceDiscoveryReport(
        intake_id="local-agents-ui-upgrade",
        discovered_sources=[live_target],
        recommended_target=live_target,
        ownership_boundary="target is under el-micaiah profile; route ownership before implementation",
        confidence=DiscoveryConfidence.HIGH,
        required_next_gate=ProjectIntakePhase.BLOCKED_NEEDS_EL_LE,
        evidence_refs=[evidence("fixture://failed_local_agents_ui_run")],
    )

    assert report.recommended_target is not None
    assert report.recommended_target.port == 8787
    assert report.recommended_target.owner_profile == "el-micaiah"
    assert report.required_next_gate == ProjectIntakePhase.BLOCKED_NEEDS_EL_LE


def test_ambiguous_project_status_requires_proposal_binding_until_approved():
    project = ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        proposal_required=True,
    )

    missing = check_proposal_gate(project)
    assert missing.status == ProposalGateStatus.REQUIRED_MISSING
    assert missing.ok is False

    live_target, _wrong_substitute = load_failed_run_targets()
    binding = approved_binding(live_target)
    approval_record = binding.approval_record
    project.source_discovery = SourceDiscoveryReport(
        intake_id="local-agents-ui-upgrade",
        discovered_sources=[live_target],
        recommended_target=live_target,
        confidence=DiscoveryConfidence.HIGH,
        required_next_gate=ProjectIntakePhase.PLAN_REVIEW,
        evidence_refs=[evidence("fixture://failed_local_agents_ui_run")],
    )
    project.proposal_approval = ProposalApprovalEvidence(
        proposal_id="proposal-local-agents-ui",
        proposal_version="v1",
        proposal_digest="sha256:proposal-digest",
        approved_by="zo-el",
        approved_at="2026-08-01T16:20:00Z",
        approval_record=approval_record,
        covered_acceptance_criteria=["upgrade the currently running local UI/dashboard"],
    )
    project.approved_target_binding = binding

    approved = check_proposal_gate(project)
    assert approved.status == ProposalGateStatus.APPROVED
    assert approved.approved_binding_version == "v1"
    assert approved.ok is True


def test_orphan_binding_without_source_discovery_and_approval_cannot_pass_gate():
    live_target, _wrong_substitute = load_failed_run_targets()
    project = ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        proposal_required=True,
        approved_target_binding=approved_binding(live_target),
    )

    check = check_proposal_gate(project)

    assert check.status == ProposalGateStatus.REQUIRED_MISSING
    assert check.ok is False
    assert any("source discovery" in failure for failure in check.failures)
    assert any("proposal approval" in failure for failure in check.failures)


def test_binding_must_match_proposal_approval_record_and_discovery_refs():
    live_target, _wrong_substitute = load_failed_run_targets()
    binding = approved_binding(live_target)
    binding.proposal_digest = "sha256:different-digest"
    project = ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        proposal_required=True,
        source_discovery=SourceDiscoveryReport(
            intake_id="local-agents-ui-upgrade",
            discovered_sources=[live_target],
            recommended_target=live_target,
            confidence=DiscoveryConfidence.HIGH,
            required_next_gate=ProjectIntakePhase.PLAN_REVIEW,
            evidence_refs=[evidence("fixture://failed_local_agents_ui_run")],
        ),
        proposal_approval=ProposalApprovalEvidence(
            proposal_id="proposal-local-agents-ui",
            proposal_version="v1",
            proposal_digest="sha256:proposal-digest",
            approved_by="zo-el",
            approved_at="2026-08-01T16:20:00Z",
            approval_record=evidence("gh-pr://approval", EvidenceType.PROPOSAL_APPROVAL),
            covered_acceptance_criteria=["upgrade the currently running local UI/dashboard"],
        ),
        approved_target_binding=binding,
    )

    check = check_proposal_gate(project)

    assert check.status == ProposalGateStatus.REQUIRED_MISSING
    assert any("proposal digest" in failure for failure in check.failures)


def test_failed_run_fixture_detects_8787_to_9120_target_drift():
    live_target, wrong_substitute = load_failed_run_targets()
    project = ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        proposal_required=True,
        approved_target_binding=approved_binding(live_target),
    )

    check = check_project_target_binding(project, wrong_substitute)

    assert check.status == ProposalGateStatus.TARGET_MISMATCH
    assert check.ok is False
    assert any("port mismatch" in failure for failure in check.failures)
    assert any("owner_profile mismatch" in failure for failure in check.failures)


def test_empty_candidate_target_cannot_pass_by_omitting_binding_fields():
    live_target, _wrong_substitute = load_failed_run_targets()
    project = ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        proposal_required=True,
        approved_target_binding=approved_binding(live_target),
    )

    check = check_project_target_binding(project, TargetSurface(label="task-progress-without-target-evidence"))

    assert check.status == ProposalGateStatus.TARGET_MISMATCH
    assert check.ok is False
    assert any("missing candidate url" in failure for failure in check.failures)
    assert any("missing candidate port" in failure for failure in check.failures)


def test_partial_candidate_target_cannot_omit_populated_binding_fields():
    live_target, _wrong_substitute = load_failed_run_targets()
    project = ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        proposal_required=True,
        approved_target_binding=approved_binding(live_target),
    )

    check = check_project_target_binding(project, TargetSurface(label="partial", url=live_target.url))

    assert check.status == ProposalGateStatus.TARGET_MISMATCH
    assert check.ok is False
    assert any("missing candidate port" in failure for failure in check.failures)
    assert not any("url mismatch" in failure for failure in check.failures)


def test_matching_target_passes_binding_check():
    live_target, _wrong_substitute = load_failed_run_targets()
    project = ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        proposal_required=True,
        approved_target_binding=approved_binding(live_target),
    )

    check = check_project_target_binding(project, live_target)

    assert check.status == ProposalGateStatus.APPROVED
    assert check.ok is True
    assert check.failures == []
