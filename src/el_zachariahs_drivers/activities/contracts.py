"""Activity contracts and a local runner for side-effecting operations.

Temporal workflows call activities for IO: GitHub, git, Hermes/Kanban, tests,
review routing, proof packets, and user/El-Le escalation. These contracts keep
workflow logic decoupled from specific tools. The local runner is intentionally
adapter-neutral: tests and demos can bind fake callables without importing Hermes,
GitHub, Temporal, or CLI code.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from el_zachariahs_drivers.models import (
    ActivityRequest,
    ActivityResultEnvelope,
    ActivityStatus,
    Blocker,
    ProjectState,
    TaskState,
)


def utc_now_iso() -> str:
    """Return a durable UTC timestamp string for local activity envelopes."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


ActivityHandler = Callable[[ActivityRequest], ActivityResultEnvelope]


class ActivityRunner(Protocol):
    def run(self, request: ActivityRequest) -> ActivityResultEnvelope: ...


class LocalActivityRunner:
    """Run registered activity handlers with local idempotency protection.

    This is not a production queue. It is a deterministic boundary for unit tests,
    local smoke runs, and future adapters: repeated idempotency keys do not invoke
    the handler again and return a duplicate-skip envelope that points at the
    previously completed activity.
    """

    def __init__(
        self,
        handlers: dict[str, ActivityHandler],
        *,
        clock: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._handlers = dict(handlers)
        self._clock = clock
        self._completed_by_idempotency_key: dict[str, ActivityResultEnvelope] = {}

    def run(self, request: ActivityRequest) -> ActivityResultEnvelope:
        previous = self._completed_by_idempotency_key.get(request.idempotency_key)
        if previous is not None:
            timestamp = self._clock()
            return ActivityResultEnvelope(
                activity_id=request.activity_id,
                activity_type=request.activity_type,
                idempotency_key=request.idempotency_key,
                role=request.role,
                status=ActivityStatus.SKIPPED_DUPLICATE,
                started_at=timestamp,
                finished_at=timestamp,
                output={"previous_activity_id": previous.activity_id},
            )

        handler = self._handlers.get(request.activity_type)
        if handler is None:
            timestamp = self._clock()
            return ActivityResultEnvelope(
                activity_id=request.activity_id,
                activity_type=request.activity_type,
                idempotency_key=request.idempotency_key,
                role=request.role,
                status=ActivityStatus.FAILED,
                started_at=timestamp,
                finished_at=timestamp,
                error=f"no local activity handler registered for {request.activity_type!r}",
            )

        result = handler(request)
        self._validate_result_matches_request(request, result)
        if result.status == ActivityStatus.SUCCEEDED:
            self._completed_by_idempotency_key[request.idempotency_key] = result
        return result

    @staticmethod
    def _validate_result_matches_request(
        request: ActivityRequest,
        result: ActivityResultEnvelope,
    ) -> None:
        if result.activity_id != request.activity_id:
            raise ValueError("activity result activity_id does not match request")
        if result.activity_type != request.activity_type:
            raise ValueError("activity result activity_type does not match request")
        if result.idempotency_key != request.idempotency_key:
            raise ValueError("activity result idempotency_key does not match request")
        if result.role != request.role:
            raise ValueError("activity result role does not match request")
        if result.status == ActivityStatus.SUCCEEDED and len(result.evidence_refs) < len(
            request.required_evidence
        ):
            raise ValueError("successful activity result is missing required evidence refs")


class ProjectActivities(Protocol):
    def create_plan_tasks(self, project: ProjectState) -> list[TaskState]: ...
    def open_or_update_pr(self, project: ProjectState) -> str: ...
    def request_review(self, project: ProjectState) -> None: ...
    def escalate_blocker(self, blocker: Blocker) -> None: ...


class TaskActivities(Protocol):
    def implement_task(self, task: TaskState) -> TaskState: ...
    def run_verification(self, task: TaskState) -> TaskState: ...
    def request_task_review(self, task: TaskState) -> TaskState: ...
