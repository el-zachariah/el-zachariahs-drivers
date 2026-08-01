import pytest
from pydantic import ValidationError

from el_zachariahs_drivers.models import (
    AcceptanceCriterionProof,
    AcceptanceReport,
    ApprovedTargetBinding,
    Blocker,
    DiscoveryConfidence,
    DriverActor,
    DriverAuthorizationEvidence,
    DriverKind,
    EvidenceRef,
    EvidenceType,
    ProgressSignal,
    ProjectIntakePhase,
    ProjectState,
    ProposalApprovalEvidence,
    ResumeDecisionOption,
    ResumeTarget,
    SourceDiscoveryReport,
    TargetSurface,
    TaskPhase,
    TaskState,
    TerminalOutcome,
    WaitPolicy,
    WaitThresholdResponse,
    WorkflowRole,
)
from el_zachariahs_drivers.policies.templates import validate_decision_against_phase_policy
from el_zachariahs_drivers.review_triggers import verify_review_trigger
from el_zachariahs_drivers.workflows.project_driver import (
    decide_next_project_transition,
    next_project_phase,
)
from el_zachariahs_drivers.workflows.task_driver import decide_next_task_transition, next_task_phase


def wait_policy() -> WaitPolicy:
    return WaitPolicy(
        awaited_signal="review_completed",
        started_at="2026-07-31T04:40:00Z",
        threshold_at="2026-07-31T05:10:00Z",
        retry_policy="single-reminder",
        threshold_response=WaitThresholdResponse.BLOCKED_NEEDS_EL_LE,
    )


def blocker(owner_role: WorkflowRole = WorkflowRole.PROCESS_STEWARD) -> Blocker:
    return Blocker(
        reason="review dispatch stuck",
        category="process",
        owner=DriverActor.EL_ZACHARIAH,
        owner_role=owner_role,
        required_decision="diagnose dispatch and resume",
        resume_target=ResumeTarget(
            blocked_phase="REVIEW_WAIT",
            resume_phase_if_unblocked="REVIEW_REQUESTED",
            decision_options=[
                ResumeDecisionOption(
                    decision="dispatch fixed",
                    resulting_phase="REVIEW_REQUESTED",
                    notes="request review again",
                )
            ],
        ),
    )


def evidence(uri: str, type_: EvidenceType = EvidenceType.SOURCE_DISCOVERY) -> EvidenceRef:
    return EvidenceRef(type=type_, uri=uri)


def local_ui_target() -> TargetSurface:
    return TargetSurface(
        label="live micaiah status UI",
        url="http://192.168.0.110:8787/",
        port=8787,
        service_identity="micaiah_status.server",
        cwd="/home/zachariah/Documents/el-micaiah/micaiah-status-ui",
        repo="/home/zachariah/Documents/el-micaiah/micaiah-status-ui",
        owner_profile="el-micaiah",
    )


def wrong_preview_target() -> TargetSurface:
    return TargetSurface(
        label="parallel replacement preview",
        url="http://192.168.0.110:9120/",
        port=9120,
        service_identity="hermes-council-mind.preview",
        cwd="/home/zachariah/Documents/el-zachariah/repos/hermes-council-mind",
        repo="el-zachariah/hermes-council-mind",
        owner_profile="el-zachariah",
    )


def approved_local_ui_project(phase: ProjectIntakePhase) -> ProjectState:
    target = local_ui_target()
    discovery_ref = evidence("fixture://failed_local_agents_ui_run")
    approval_ref = evidence("gh-pr://approval/local-ui", EvidenceType.PROPOSAL_APPROVAL)
    return ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        phase=phase,
        proposal_required=True,
        source_discovery=SourceDiscoveryReport(
            intake_id="local-agents-ui-upgrade",
            discovered_sources=[target],
            recommended_target=target,
            confidence=DiscoveryConfidence.HIGH,
            required_next_gate=ProjectIntakePhase.PLAN_REVIEW,
            evidence_refs=[discovery_ref],
        ),
        proposal_approval=ProposalApprovalEvidence(
            proposal_id="proposal-local-agents-ui",
            proposal_version="v1",
            proposal_digest="sha256:proposal-digest",
            approved_by="zo-el",
            approved_at="2026-08-01T16:20:00Z",
            approval_record=approval_ref,
            covered_acceptance_criteria=["upgrade the currently running local UI/dashboard"],
        ),
        approved_target_binding=ApprovedTargetBinding(
            binding_id="binding-local-agents-ui-v1",
            version="v1",
            target=target,
            proposal_id="proposal-local-agents-ui",
            proposal_version="v1",
            proposal_digest="sha256:proposal-digest",
            approval_record=approval_ref,
            approved_by="zo-el",
            covered_acceptance_criteria=["upgrade the currently running local UI/dashboard"],
            source_discovery_refs=[discovery_ref],
        ),
    )


def driver_auth(
    binding_version: str = "v1",
    supervisor_intervention: bool = False,
    authorized_by_role: WorkflowRole = WorkflowRole.DEVELOPER,
) -> DriverAuthorizationEvidence:
    return DriverAuthorizationEvidence(
        workflow_decision_id="decision-task-complete-1",
        activity_id="activity-implement-approved-target",
        binding_version=binding_version,
        authorized_by_role=authorized_by_role,
        supervisor_intervention=supervisor_intervention,
    )


def test_review_fix_loop_returns_to_implementation_until_limit():
    task = TaskState(id="t1", title="Fix review findings", phase=TaskPhase.FIXING_REVIEW)
    assert next_task_phase(task) == TaskPhase.IMPLEMENTING


def test_review_fix_loop_requests_rescope_at_limit():
    task = TaskState(
        id="t1",
        title="Fix review findings",
        phase=TaskPhase.FIXING_REVIEW,
        review_loop_count=3,
        max_review_loops=3,
    )
    assert next_task_phase(task) == TaskPhase.RESCOPE_REQUESTED


def test_project_rethinks_plan_when_task_requests_rescope():
    project = ProjectState(
        id="p1",
        title="Project with new review finding",
        phase=ProjectIntakePhase.TASK_EXECUTION,
        tasks=[TaskState(id="t1", title="Task", phase=TaskPhase.RESCOPE_REQUESTED)],
    )
    assert next_project_phase(project) == ProjectIntakePhase.PLAN_RETHINK


def test_project_plan_rethink_self_recovers_to_task_breakdown():
    project = ProjectState(id="p1", title="Rethink", phase=ProjectIntakePhase.PLAN_RETHINK)
    assert next_project_phase(project) == ProjectIntakePhase.TASK_BREAKDOWN


def test_task_transition_helper_emits_workflow_decision():
    task = TaskState(id="t1", title="Inspect", phase=TaskPhase.CLAIMED)

    decision = decide_next_task_transition(task, decided_at="2026-07-31T04:40:01Z")

    assert decision.from_phase == TaskPhase.CLAIMED
    assert decision.to_phase == TaskPhase.INSPECTING
    assert decision.material_progress is True
    assert decision.progress_signal == ProgressSignal.TASK_STARTED


def test_task_review_wait_transition_requires_durable_wait_policy():
    task = TaskState(id="t1", title="Review", phase=TaskPhase.REVIEW_REQUESTED)

    with pytest.raises(ValueError, match="review wait transitions require wait_to_start"):
        decide_next_task_transition(task, decided_at="2026-07-31T04:40:02Z")

    decision = decide_next_task_transition(
        task,
        decided_at="2026-07-31T04:40:02Z",
        wait_to_start=wait_policy(),
    )

    assert decision.to_phase == TaskPhase.REVIEW_WAIT
    assert decision.material_progress is False
    assert decision.progress_signal == ProgressSignal.WAIT_TIMER_STARTED
    assert decision.wait_to_start == wait_policy()


def test_task_review_wait_rejects_weak_tag_only_trigger_even_with_wait_policy():
    task = TaskState(id="t1", title="Review", phase=TaskPhase.REVIEW_REQUESTED)
    weak_trigger = verify_review_trigger(
        target_reviewer="el-micaiah",
        pr_url="https://github.com/el-zachariah/example/pull/1",
        repo_visibility="PUBLIC",
        reviewer_permission="read",
        review_requests=[],
        latest_reviewers=[],
        tag_comment_url="https://github.com/el-zachariah/example/pull/1#issuecomment-1",
    )

    decision = decide_next_task_transition(
        task,
        decided_at="2026-07-31T04:40:02Z",
        wait_to_start=wait_policy(),
        review_trigger=weak_trigger,
    )

    assert decision.to_phase == TaskPhase.BLOCKED_NEEDS_EL_LE
    assert decision.progress_signal == ProgressSignal.BLOCKER_CREATED
    assert decision.blocker_to_record is not None
    assert decision.blocker_to_record.owner_role == WorkflowRole.PROCESS_STEWARD
    assert decision.wait_to_start is None


def test_task_same_phase_transition_must_be_controlled_wait_not_no_op_progress():
    task = TaskState(id="t1", title="Already waiting", phase=TaskPhase.REVIEW_WAIT)

    with pytest.raises(ValueError, match="same-phase task transitions require a durable wait policy"):
        decide_next_task_transition(task, decided_at="2026-07-31T04:40:03Z")

    decision = decide_next_task_transition(
        task,
        decided_at="2026-07-31T04:40:03Z",
        wait_to_start=wait_policy(),
    )
    assert decision.to_phase == TaskPhase.REVIEW_WAIT
    assert decision.material_progress is False
    assert decision.wait_to_start == wait_policy()


def test_task_blocker_transition_preserves_durable_blocker_and_human_owner_route():
    durable_blocker = blocker(WorkflowRole.HUMAN_APPROVER)
    task = TaskState(
        id="t1",
        title="Blocked",
        phase=TaskPhase.TESTING,
        blocker=durable_blocker,
    )

    decision = decide_next_task_transition(task, decided_at="2026-07-31T04:40:04Z")

    assert decision.to_phase == TaskPhase.BLOCKED_NEEDS_ZO_EL
    assert decision.progress_signal == ProgressSignal.BLOCKER_CREATED
    assert decision.blocker_to_record == durable_blocker


def test_already_blocked_task_transition_is_controlled_wait_not_new_blocker_progress():
    durable_blocker = blocker(WorkflowRole.HUMAN_APPROVER)
    task = TaskState(
        id="t1",
        title="Still blocked",
        phase=TaskPhase.BLOCKED_NEEDS_ZO_EL,
        blocker=durable_blocker,
    )

    with pytest.raises(ValueError, match="already-blocked task transitions require a durable wait policy"):
        decide_next_task_transition(task, decided_at="2026-07-31T04:40:04Z")

    decision = decide_next_task_transition(
        task,
        decided_at="2026-07-31T04:40:04Z",
        wait_to_start=wait_policy(),
    )

    assert decision.to_phase == TaskPhase.BLOCKED_NEEDS_ZO_EL
    assert decision.material_progress is False
    assert decision.progress_signal == ProgressSignal.WAIT_TIMER_STARTED
    assert decision.wait_to_start == wait_policy()
    assert decision.blocker_to_record == durable_blocker



def test_ambiguous_project_cannot_enter_task_breakdown_without_approved_proposal_binding():
    project = ProjectState(
        id="p-local-ui",
        title="Upgrade running local UI/dashboard",
        phase=ProjectIntakePhase.PLAN_REVIEW,
        proposal_required=True,
    )

    decision = decide_next_project_transition(project, decided_at="2026-08-01T17:00:00Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.progress_signal == ProgressSignal.BLOCKER_CREATED
    assert decision.blocker_to_record is not None
    assert decision.blocker_to_record.owner_role == WorkflowRole.HUMAN_APPROVER
    assert "approved target binding" in decision.blocker_to_record.reason


def test_ambiguous_project_rejects_target_drift_before_task_breakdown():
    project = approved_local_ui_project(ProjectIntakePhase.PLAN_REVIEW)

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T17:01:00Z",
        candidate_target=wrong_preview_target(),
    )

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "port mismatch" in decision.blocker_to_record.reason
    assert "owner_profile mismatch" in decision.blocker_to_record.reason


def test_ambiguous_project_allows_task_breakdown_for_approved_target():
    project = approved_local_ui_project(ProjectIntakePhase.PLAN_REVIEW)

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T17:02:00Z",
        candidate_target=local_ui_target(),
    )

    assert decision.to_phase == ProjectIntakePhase.TASK_BREAKDOWN
    assert decision.material_progress is True
    assert decision.progress_signal == ProgressSignal.PLAN_APPROVED


def test_driver_test_progress_requires_driver_authorization_evidence():
    project = approved_local_ui_project(ProjectIntakePhase.TASK_EXECUTION)
    project.tasks = [TaskState(id="t1", title="Task", phase=TaskPhase.COMPLETE)]

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T17:03:00Z",
        candidate_target=local_ui_target(),
        driver_test_mode=True,
    )

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "requires driver authorization evidence" in decision.blocker_to_record.reason
    assert decision.blocker_to_record.resume_target.blocked_phase == ProjectIntakePhase.TASK_EXECUTION
    assert validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, decision) == decision


def test_supervisor_intervention_cannot_count_as_driver_authorized_progress():
    project = approved_local_ui_project(ProjectIntakePhase.TASK_EXECUTION)
    project.tasks = [TaskState(id="t1", title="Task", phase=TaskPhase.COMPLETE)]

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T17:04:00Z",
        candidate_target=local_ui_target(),
        driver_authorization=driver_auth(supervisor_intervention=True),
        driver_test_mode=True,
    )

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "supervisor intervention cannot count" in decision.blocker_to_record.reason


def test_process_steward_authorization_cannot_count_as_driver_authorized_progress():
    project = approved_local_ui_project(ProjectIntakePhase.TASK_EXECUTION)
    project.tasks = [TaskState(id="t1", title="Task", phase=TaskPhase.COMPLETE)]

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T19:50:00Z",
        candidate_target=local_ui_target(),
        driver_authorization=driver_auth(authorized_by_role=WorkflowRole.PROCESS_STEWARD),
        driver_test_mode=True,
    )

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "must be authorized by the developer role" in decision.blocker_to_record.reason
    assert "process_steward" in decision.blocker_to_record.reason


def test_driver_authorization_must_match_approved_binding_version():
    project = approved_local_ui_project(ProjectIntakePhase.TASK_EXECUTION)
    project.tasks = [TaskState(id="t1", title="Task", phase=TaskPhase.COMPLETE)]

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T17:05:00Z",
        candidate_target=local_ui_target(),
        driver_authorization=driver_auth(binding_version="stale-v0"),
        driver_test_mode=True,
    )

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "binding version mismatch" in decision.blocker_to_record.reason


def test_driver_authorization_requires_durable_decision_and_activity_ids():
    with pytest.raises(ValidationError) as exc_info:
        DriverAuthorizationEvidence(
            workflow_decision_id="",
            activity_id="",
            binding_version="",
            authorized_by_role=WorkflowRole.DEVELOPER,
        )

    error_locations = {tuple(error["loc"]) for error in exc_info.value.errors()}
    assert ("workflow_decision_id",) in error_locations
    assert ("activity_id",) in error_locations
    assert ("binding_version",) in error_locations


def test_driver_authorization_rejects_whitespace_only_identifiers():
    with pytest.raises(ValidationError) as exc_info:
        DriverAuthorizationEvidence(
            workflow_decision_id="   ",
            activity_id="\t",
            binding_version="  ",
            authorized_by_role=WorkflowRole.DEVELOPER,
        )

    errors = exc_info.value.errors()
    error_locations = {tuple(error["loc"]) for error in errors}
    assert ("workflow_decision_id",) in error_locations
    assert ("activity_id",) in error_locations
    assert ("binding_version",) in error_locations
    assert all("must not be blank" in error["msg"] for error in errors)


def test_driver_authorized_progress_allows_pr_open_for_approved_target():
    project = approved_local_ui_project(ProjectIntakePhase.TASK_EXECUTION)
    project.tasks = [TaskState(id="t1", title="Task", phase=TaskPhase.COMPLETE)]

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T17:06:00Z",
        candidate_target=local_ui_target(),
        driver_authorization=driver_auth(),
        driver_test_mode=True,
    )

    assert decision.to_phase == ProjectIntakePhase.PR_OPEN
    assert decision.material_progress is True
    assert decision.progress_signal == ProgressSignal.TASK_COMPLETED
    assert decision.driver_authorization == driver_auth()


def test_driver_test_pr_artifact_progress_requires_driver_authorization_evidence():
    project = approved_local_ui_project(ProjectIntakePhase.PR_OPEN)
    project.pr_url = "https://github.com/el-zachariah/el-zachariahs-drivers/pull/26"

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T21:45:00Z",
        driver_test_mode=True,
    )

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "requires driver authorization evidence" in decision.blocker_to_record.reason
    assert decision.blocker_to_record.resume_target.blocked_phase == ProjectIntakePhase.PR_OPEN
    assert validate_decision_against_phase_policy(DriverKind.SOFTWARE_PROJECT, decision) == decision


def test_driver_authorized_pr_artifact_progress_allows_review_requested():
    project = approved_local_ui_project(ProjectIntakePhase.PR_OPEN)
    project.pr_url = "https://github.com/el-zachariah/el-zachariahs-drivers/pull/26"
    authorization = driver_auth()

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T21:46:00Z",
        driver_authorization=authorization,
        driver_test_mode=True,
    )

    assert decision.to_phase == ProjectIntakePhase.REVIEW_REQUESTED
    assert decision.material_progress is True
    assert decision.progress_signal == ProgressSignal.PR_CREATED
    assert decision.driver_authorization == authorization


def test_driver_authorized_progress_serializes_authorization_evidence():
    project = approved_local_ui_project(ProjectIntakePhase.TASK_EXECUTION)
    project.tasks = [TaskState(id="t1", title="Task", phase=TaskPhase.COMPLETE)]
    authorization = driver_auth()

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T20:16:00Z",
        candidate_target=local_ui_target(),
        driver_authorization=authorization,
        driver_test_mode=True,
    )
    persisted = type(decision).model_validate_json(decision.model_dump_json())

    assert persisted.driver_authorization == authorization


def test_driver_test_same_phase_task_execution_wait_does_not_require_authorization():
    project = approved_local_ui_project(ProjectIntakePhase.TASK_EXECUTION)
    project.tasks = [TaskState(id="t1", title="Task", phase=TaskPhase.TESTING)]

    decision = decide_next_project_transition(
        project,
        decided_at="2026-08-01T18:12:00Z",
        wait_to_start=wait_policy(),
        driver_test_mode=True,
    )

    assert decision.to_phase == ProjectIntakePhase.TASK_EXECUTION
    assert decision.material_progress is False
    assert decision.progress_signal == ProgressSignal.WAIT_TIMER_STARTED
    assert decision.wait_to_start == wait_policy()
    assert decision.blocker_to_record is None


def test_project_transition_helper_emits_workflow_decision():
    project = ProjectState(id="p1", title="Planning", phase=ProjectIntakePhase.PLANNING)

    decision = decide_next_project_transition(project, decided_at="2026-07-31T04:40:05Z")

    assert decision.from_phase == ProjectIntakePhase.PLANNING
    assert decision.to_phase == ProjectIntakePhase.PLAN_REVIEW
    assert decision.material_progress is True
    assert decision.progress_signal == ProgressSignal.PLAN_CREATED


def test_project_same_phase_task_execution_requires_durable_wait():
    project = ProjectState(
        id="p1",
        title="Executing",
        phase=ProjectIntakePhase.TASK_EXECUTION,
        tasks=[TaskState(id="t1", title="Task", phase=TaskPhase.TESTING)],
    )

    with pytest.raises(ValueError, match="same-phase project transitions require a durable wait policy"):
        decide_next_project_transition(project, decided_at="2026-07-31T04:40:06Z")

    decision = decide_next_project_transition(
        project,
        decided_at="2026-07-31T04:40:06Z",
        wait_to_start=wait_policy(),
    )
    assert decision.to_phase == ProjectIntakePhase.TASK_EXECUTION
    assert decision.material_progress is False
    assert decision.wait_to_start == wait_policy()


def test_project_review_wait_transition_requires_durable_wait_policy():
    project = ProjectState(
        id="p1",
        title="Await review",
        phase=ProjectIntakePhase.REVIEW_REQUESTED,
    )

    with pytest.raises(ValueError, match="review wait transitions require wait_to_start"):
        decide_next_project_transition(project, decided_at="2026-07-31T04:40:06Z")

    decision = decide_next_project_transition(
        project,
        decided_at="2026-07-31T04:40:06Z",
        wait_to_start=wait_policy(),
    )

    assert decision.to_phase == ProjectIntakePhase.REVIEW_WAIT
    assert decision.material_progress is False
    assert decision.progress_signal == ProgressSignal.WAIT_TIMER_STARTED
    assert decision.wait_to_start == wait_policy()



def test_project_review_wait_rejects_weak_tag_only_trigger_even_with_wait_policy():
    project = ProjectState(
        id="p1",
        title="Await review",
        phase=ProjectIntakePhase.REVIEW_REQUESTED,
    )
    weak_trigger = verify_review_trigger(
        target_reviewer="el-micaiah",
        pr_url="https://github.com/el-zachariah/example/pull/1",
        repo_visibility="PUBLIC",
        reviewer_permission="read",
        review_requests=[],
        latest_reviewers=[],
        tag_comment_url="https://github.com/el-zachariah/example/pull/1#issuecomment-1",
    )

    decision = decide_next_project_transition(
        project,
        decided_at="2026-07-31T04:40:06Z",
        wait_to_start=wait_policy(),
        review_trigger=weak_trigger,
    )

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_EL_LE
    assert decision.progress_signal == ProgressSignal.BLOCKER_CREATED
    assert decision.blocker_to_record is not None
    assert decision.blocker_to_record.owner_role == WorkflowRole.PROCESS_STEWARD
    assert decision.wait_to_start is None


def test_project_blocker_transition_preserves_durable_blocker():
    durable_blocker = blocker()
    project = ProjectState(
        id="p1",
        title="Blocked",
        phase=ProjectIntakePhase.PROOF_AUTH_WAIT,
        blocker=durable_blocker,
    )

    decision = decide_next_project_transition(project, decided_at="2026-07-31T04:40:07Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_EL_LE
    assert decision.progress_signal == ProgressSignal.BLOCKER_CREATED
    assert decision.blocker_to_record == durable_blocker


def test_already_blocked_project_transition_is_controlled_wait_not_new_blocker_progress():
    durable_blocker = blocker()
    project = ProjectState(
        id="p1",
        title="Still blocked",
        phase=ProjectIntakePhase.BLOCKED_NEEDS_EL_LE,
        blocker=durable_blocker,
    )

    with pytest.raises(ValueError, match="already-blocked project transitions require a durable wait policy"):
        decide_next_project_transition(project, decided_at="2026-07-31T04:40:07Z")

    decision = decide_next_project_transition(
        project,
        decided_at="2026-07-31T04:40:07Z",
        wait_to_start=wait_policy(),
    )

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_EL_LE
    assert decision.material_progress is False
    assert decision.progress_signal == ProgressSignal.WAIT_TIMER_STARTED
    assert decision.wait_to_start == wait_policy()
    assert decision.blocker_to_record == durable_blocker



def acceptance_report_for(
    target: TargetSurface,
    *,
    criteria: list[str] | None = None,
    live_verified: bool = True,
    binding_version: str = "v1",
) -> AcceptanceReport:
    covered_criteria = criteria or ["upgrade the currently running local UI/dashboard"]
    return AcceptanceReport(
        report_id="acceptance-local-ui-v1",
        binding_version=binding_version,
        target=target,
        criteria=[
            AcceptanceCriterionProof(
                criterion=criterion,
                satisfied=True,
                evidence_refs=[evidence(f"proof://{index}", EvidenceType.PROOF)],
            )
            for index, criterion in enumerate(covered_criteria, start=1)
        ],
        live_verification_required=True,
        live_verification_passed=live_verified,
        evidence_refs=[evidence("proof://acceptance-report", EvidenceType.REPORT)],
    )


def test_project_final_report_decision_requires_acceptance_report_for_ambiguous_project():
    project = approved_local_ui_project(ProjectIntakePhase.FINAL_REPORT)

    decision = decide_next_project_transition(project, decided_at="2026-07-31T04:40:08Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "acceptance report" in decision.blocker_to_record.reason


def test_project_final_report_rejects_acceptance_report_for_wrong_preview_target():
    project = approved_local_ui_project(ProjectIntakePhase.FINAL_REPORT)
    project.acceptance_report = acceptance_report_for(wrong_preview_target())

    decision = decide_next_project_transition(project, decided_at="2026-08-01T22:20:00Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "port mismatch" in decision.blocker_to_record.reason
    assert "owner_profile mismatch" in decision.blocker_to_record.reason


def test_project_final_report_rejects_unverified_live_ui_acceptance():
    project = approved_local_ui_project(ProjectIntakePhase.FINAL_REPORT)
    project.acceptance_report = acceptance_report_for(local_ui_target(), live_verified=False)

    decision = decide_next_project_transition(project, decided_at="2026-08-01T22:21:00Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "live verification is required" in decision.blocker_to_record.reason


def test_project_final_report_rejects_report_that_opts_out_of_live_verification():
    project = approved_local_ui_project(ProjectIntakePhase.FINAL_REPORT)
    project.acceptance_report = AcceptanceReport(
        report_id="acceptance-local-ui-v1",
        binding_version="v1",
        target=local_ui_target(),
        criteria=[
            AcceptanceCriterionProof(
                criterion="upgrade the currently running local UI/dashboard",
                satisfied=True,
                evidence_refs=[evidence("proof://1", EvidenceType.PROOF)],
            )
        ],
        live_verification_required=False,
        live_verification_passed=None,
        evidence_refs=[evidence("proof://acceptance-report", EvidenceType.REPORT)],
    )

    decision = decide_next_project_transition(project, decided_at="2026-08-01T22:21:30Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "live verification is required" in decision.blocker_to_record.reason


def test_project_final_report_rejects_missing_original_intake_criteria():
    project = approved_local_ui_project(ProjectIntakePhase.FINAL_REPORT)
    project.acceptance_report = acceptance_report_for(local_ui_target(), criteria=["some other criterion"])

    decision = decide_next_project_transition(project, decided_at="2026-08-01T22:22:00Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "missing acceptance proof" in decision.blocker_to_record.reason


def test_project_final_report_rejects_binding_that_narrows_approved_criteria():
    project = approved_local_ui_project(ProjectIntakePhase.FINAL_REPORT)
    assert project.proposal_approval is not None
    assert project.approved_target_binding is not None
    project.proposal_approval.covered_acceptance_criteria = [
        "upgrade the currently running local UI/dashboard",
        "preserve the original 8787 live service target",
    ]
    project.approved_target_binding.covered_acceptance_criteria = ["narrowed criterion only"]
    project.acceptance_report = acceptance_report_for(
        local_ui_target(),
        criteria=["narrowed criterion only"],
    )

    decision = decide_next_project_transition(project, decided_at="2026-08-01T22:37:00Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "missing proposal-approved acceptance criterion" in decision.blocker_to_record.reason
    assert "upgrade the currently running local UI/dashboard" in decision.blocker_to_record.reason
    assert "preserve the original 8787 live service target" in decision.blocker_to_record.reason


def test_project_final_report_rejects_substitute_approval_reused_for_unapproved_target():
    project = approved_local_ui_project(ProjectIntakePhase.FINAL_REPORT)
    assert project.approved_target_binding is not None
    substitute_ref = evidence("gh-comment://approved-9120-preview", EvidenceType.PROPOSAL_APPROVAL)
    project.approved_target_binding.approved_substitute_artifacts = [substitute_ref]
    unapproved_preview = TargetSurface(
        label="unapproved 9999 preview",
        url="http://192.168.0.110:9999/",
        port=9999,
        service_identity="unapproved.preview",
        cwd="/tmp/unapproved-preview",
        repo="el-zachariah/unapproved-preview",
        owner_profile="el-zachariah",
        evidence_refs=[evidence("preview://9999-run", EvidenceType.PROOF)],
    )
    project.acceptance_report = acceptance_report_for(unapproved_preview)
    project.acceptance_report.substitute_approval_refs = [substitute_ref]

    decision = decide_next_project_transition(project, decided_at="2026-08-01T22:38:00Z")

    assert decision.to_phase == ProjectIntakePhase.BLOCKED_NEEDS_ZO_EL
    assert decision.blocker_to_record is not None
    assert "port mismatch" in decision.blocker_to_record.reason
    assert "substitute deliverable is not explicitly approved" in decision.blocker_to_record.reason


def test_project_final_report_decision_is_terminal_done_with_verified_acceptance_report():
    project = approved_local_ui_project(ProjectIntakePhase.FINAL_REPORT)
    project.acceptance_report = acceptance_report_for(local_ui_target())

    decision = decide_next_project_transition(project, decided_at="2026-08-01T22:23:00Z")

    assert decision.to_phase == ProjectIntakePhase.DONE
    assert decision.terminal_outcome == TerminalOutcome.DONE
    assert decision.evidence_refs == project.acceptance_report.evidence_refs


def test_project_final_report_decision_is_terminal_done_when_proposal_not_required():
    project = ProjectState(id="p1", title="Done", phase=ProjectIntakePhase.FINAL_REPORT)

    decision = decide_next_project_transition(project, decided_at="2026-07-31T04:40:08Z")

    assert decision.to_phase == ProjectIntakePhase.DONE
    assert decision.terminal_outcome == TerminalOutcome.DONE
