from el_zachariahs_drivers.models import ActivitySideEffect, WorkflowRole
from el_zachariahs_drivers.workflows.temporal_skeleton import (
    DurableWorkflowTemporalSkeleton,
    TemporalWorkflowCommand,
    TemporalWorkflowResult,
    build_store_activity_request,
)


def test_temporal_skeleton_imports_without_temporalio_dependency() -> None:
    skeleton = DurableWorkflowTemporalSkeleton()

    assert skeleton.workflow_type == "DurableWorkflowTemporalSkeleton"


def test_store_activity_request_is_adapter_neutral_and_idempotent() -> None:
    command = TemporalWorkflowCommand(
        workflow_id="workflow-1",
        store_root_uri="file:///tmp/workflow-1",
        action="replay_status",
    )

    request = build_store_activity_request(command, requested_at="2026-07-31T00:00:00Z")

    assert request.activity_id == "workflow-1:store:replay_status"
    assert request.activity_type == "workflow_store.replay_status"
    assert request.role == WorkflowRole.PROCESS_STEWARD
    assert request.allowed_side_effects == [ActivitySideEffect.COMMAND]
    assert request.idempotency_key == "workflow-1:store:replay_status:file:///tmp/workflow-1"
    assert request.acceptance_criteria == [
        "Replay persisted workflow decisions from the durable store.",
        "Return a status envelope with phase, next trigger, blocker, and evidence refs.",
    ]


def test_skeleton_plan_run_schedules_one_store_activity_without_side_effects() -> None:
    command = TemporalWorkflowCommand(
        workflow_id="workflow-2",
        store_root_uri="file:///tmp/workflow-2",
        action="status",
    )
    skeleton = DurableWorkflowTemporalSkeleton()

    result = skeleton.plan_run(command, requested_at="2026-07-31T00:00:00Z")

    assert isinstance(result, TemporalWorkflowResult)
    assert result.workflow_id == "workflow-2"
    assert result.runtime_backend == "temporal-compatible"
    assert result.scheduled_activities[0].activity_type == "workflow_store.status"
    assert result.status is None
    assert result.notes == [
        "Skeleton only plans adapter-neutral activity requests; workers own IO and durable side effects."
    ]


def test_unknown_temporal_command_is_rejected() -> None:
    command = TemporalWorkflowCommand.model_construct(
        workflow_id="workflow-3",
        store_root_uri="file:///tmp/workflow-3",
        action="unsupported",
    )

    try:
        build_store_activity_request(command, requested_at="2026-07-31T00:00:00Z")
    except ValueError as exc:
        assert "unsupported Temporal workflow command action" in str(exc)
    else:
        raise AssertionError("unsupported command should fail closed")
