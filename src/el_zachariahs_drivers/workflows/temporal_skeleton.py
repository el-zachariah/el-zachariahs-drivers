"""Thin Temporal-compatible workflow skeletons.

This module is intentionally adapter-neutral. It does not import Hermes, GitHub,
Kanban, or local CLI implementations, and it remains importable when the optional
``temporalio`` package is not installed. The skeleton only produces contract
``ActivityRequest`` objects; workers/adapters are responsible for binding those
requests to Temporal activities or local fake runners.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from el_zachariahs_drivers.models import (
    ActivityRequest,
    ActivitySideEffect,
    ActivityFailurePolicy,
    EvidenceType,
    RetryPolicy,
    TimeoutPolicy,
    WorkflowRole,
)
from el_zachariahs_drivers.state_store import WorkflowStatus

try:  # pragma: no cover - exercised only when optional dependency is installed.
    from temporalio import workflow as _temporal_workflow
except ModuleNotFoundError:  # pragma: no cover - default test environment path.
    _temporal_workflow = None


def _workflow_definition(cls: type) -> type:
    """Apply Temporal's workflow decorator when available, otherwise no-op."""
    if _temporal_workflow is None:
        return cls
    return _temporal_workflow.defn(cls)


def _workflow_run(fn: Any) -> Any:
    """Apply Temporal's run decorator when available, otherwise no-op."""
    if _temporal_workflow is None:
        return fn
    return _temporal_workflow.run(fn)


class TemporalWorkflowCommand(BaseModel):
    """Input for the Temporal-compatible workflow shim.

    ``store_root_uri`` is an adapter-owned URI rather than a ``Path`` so the core
    contract can be backed by local JSON files in tests or a different durable
    store in a real Temporal worker.
    """

    workflow_id: str
    store_root_uri: str
    action: Literal["status", "replay_status"] = "replay_status"
    correlation_id: str | None = None


class TemporalWorkflowResult(BaseModel):
    """Planned side effects and optional status returned by the skeleton."""

    workflow_id: str
    runtime_backend: str = "temporal-compatible"
    scheduled_activities: list[ActivityRequest] = Field(default_factory=list)
    status: WorkflowStatus | None = None
    notes: list[str] = Field(default_factory=list)


STORE_ACTIVITY_TYPES = {
    "status": "workflow_store.status",
    "replay_status": "workflow_store.replay_status",
}

STORE_ACTIVITY_ACCEPTANCE = {
    "status": [
        "Read the current durable workflow snapshot without mutating workflow history.",
        "Return a status envelope with phase, next trigger, blocker, and evidence refs.",
    ],
    "replay_status": [
        "Replay persisted workflow decisions from the durable store.",
        "Return a status envelope with phase, next trigger, blocker, and evidence refs.",
    ],
}


def build_store_activity_request(
    command: TemporalWorkflowCommand,
    *,
    requested_at: str,
) -> ActivityRequest:
    """Build the single adapter-neutral store activity for a Temporal workflow tick."""
    activity_type = STORE_ACTIVITY_TYPES.get(command.action)
    if activity_type is None:
        raise ValueError(f"unsupported Temporal workflow command action: {command.action!r}")

    return ActivityRequest(
        activity_id=f"{command.workflow_id}:store:{command.action}",
        activity_type=activity_type,
        role=WorkflowRole.PROCESS_STEWARD,
        purpose=(
            "Produce the durable workflow status used to decide the next trigger, wait, "
            "blocker, or terminal outcome."
        ),
        acceptance_criteria=STORE_ACTIVITY_ACCEPTANCE[command.action],
        allowed_side_effects=[ActivitySideEffect.COMMAND],
        required_evidence=[EvidenceType.ADAPTER_RECORD.value],
        idempotency_key=f"{command.workflow_id}:store:{command.action}:{command.store_root_uri}",
        timeout_policy=TimeoutPolicy(start_to_close="30s", schedule_to_close="2m"),
        retry_policy=RetryPolicy(max_attempts=3, backoff="exponential:1s"),
        on_failure=ActivityFailurePolicy(
            rescope_allowed=False,
            blocker_owner_role=WorkflowRole.PROCESS_STEWARD,
        ),
    )


@_workflow_definition
class DurableWorkflowTemporalSkeleton:
    """Minimal Temporal-compatible workflow boundary.

    The workflow remains deterministic by only planning activity requests from its
    command input. A real Temporal worker may wrap ``plan_run`` by executing the
    scheduled ``ActivityRequest`` with a bound activity adapter and then persisting
    the resulting ``ActivityResultEnvelope`` in the durable event log.
    """

    workflow_type = "DurableWorkflowTemporalSkeleton"

    @_workflow_run
    async def run(self, command: TemporalWorkflowCommand) -> TemporalWorkflowResult:
        """Temporal entry point; returns planned work instead of doing IO directly."""
        return self.plan_run(command, requested_at="temporal-workflow-clock")

    def plan_run(
        self,
        command: TemporalWorkflowCommand,
        *,
        requested_at: str,
    ) -> TemporalWorkflowResult:
        request = build_store_activity_request(command, requested_at=requested_at)
        return TemporalWorkflowResult(
            workflow_id=command.workflow_id,
            scheduled_activities=[request],
            notes=[
                "Skeleton only plans adapter-neutral activity requests; workers own IO and durable side effects."
            ],
        )
