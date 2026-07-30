from el_zachariahs_drivers.models import ProjectIntakePhase, ProjectState, TaskPhase, TaskState
from el_zachariahs_drivers.workflows.project_driver import next_project_phase
from el_zachariahs_drivers.workflows.task_driver import next_task_phase


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
