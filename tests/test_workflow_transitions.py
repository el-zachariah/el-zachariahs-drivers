import pytest

from el_zachariahs_drivers.models import (
    Blocker,
    DriverActor,
    ProgressSignal,
    ProjectIntakePhase,
    ProjectState,
    ResumeDecisionOption,
    ResumeTarget,
    TaskPhase,
    TaskState,
    TerminalOutcome,
    WaitPolicy,
    WaitThresholdResponse,
    WorkflowRole,
)
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


def test_project_final_report_decision_is_terminal_done():
    project = ProjectState(id="p1", title="Done", phase=ProjectIntakePhase.FINAL_REPORT)

    decision = decide_next_project_transition(project, decided_at="2026-07-31T04:40:08Z")

    assert decision.to_phase == ProjectIntakePhase.DONE
    assert decision.terminal_outcome == TerminalOutcome.DONE
