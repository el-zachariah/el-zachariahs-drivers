import pytest
from pydantic import ValidationError

from el_zachariahs_drivers.activities.contracts import LocalActivityRunner
from el_zachariahs_drivers.models import (
    ActivityFailurePolicy,
    ActivityRequest,
    ActivityResultEnvelope,
    ActivitySideEffect,
    ActivityStatus,
    EvidenceRef,
    EvidenceType,
    RetryPolicy,
    TimeoutPolicy,
    WorkflowRole,
)


def evidence(uri: str = "command:pytest") -> EvidenceRef:
    return EvidenceRef(type=EvidenceType.COMMAND, uri=uri, digest="sha256:test-output")


def request(
    *,
    activity_id: str = "act-1",
    activity_type: str = "run_tests",
    role: WorkflowRole = WorkflowRole.DEVELOPER,
    idempotency_key: str = "wf-1:run-tests",
    required_evidence: list[str] | None = None,
) -> ActivityRequest:
    return ActivityRequest(
        activity_id=activity_id,
        activity_type=activity_type,
        role=role,
        purpose="run verification command",
        acceptance_criteria=["verification command exits zero"],
        allowed_side_effects=[ActivitySideEffect.COMMAND],
        required_evidence=required_evidence or ["command output"],
        input_refs=[],
        idempotency_key=idempotency_key,
        timeout_policy=TimeoutPolicy(start_to_close="5m", schedule_to_close="10m"),
        retry_policy=RetryPolicy(max_attempts=1, backoff="none"),
        on_failure=ActivityFailurePolicy(
            rescope_allowed=False,
            blocker_owner_role=WorkflowRole.PROCESS_STEWARD,
        ),
    )


def result_for(req: ActivityRequest, *, uri: str = "command:pytest") -> ActivityResultEnvelope:
    return ActivityResultEnvelope(
        activity_id=req.activity_id,
        activity_type=req.activity_type,
        idempotency_key=req.idempotency_key,
        role=req.role,
        status=ActivityStatus.SUCCEEDED,
        started_at="2026-07-31T06:00:00Z",
        finished_at="2026-07-31T06:00:01Z",
        evidence_refs=[evidence(uri)],
        output={"exit_code": 0},
    )


def test_activity_result_envelope_rejects_failed_result_without_error():
    with pytest.raises(ValidationError, match="failed activity results require error"):
        ActivityResultEnvelope(
            activity_id="act-1",
            activity_type="run_tests",
            idempotency_key="wf-1:run-tests",
            role=WorkflowRole.DEVELOPER,
            status=ActivityStatus.FAILED,
            started_at="2026-07-31T06:00:00Z",
            finished_at="2026-07-31T06:00:01Z",
        )


def test_activity_result_envelope_rejects_success_with_error():
    with pytest.raises(ValidationError, match="only failed activity results may carry error"):
        ActivityResultEnvelope(
            activity_id="act-1",
            activity_type="run_tests",
            idempotency_key="wf-1:run-tests",
            role=WorkflowRole.DEVELOPER,
            status=ActivityStatus.SUCCEEDED,
            started_at="2026-07-31T06:00:00Z",
            finished_at="2026-07-31T06:00:01Z",
            error="should not be here",
        )


def test_local_activity_runner_runs_fake_handler_and_returns_evidence_envelope():
    calls: list[str] = []

    def fake_handler(req: ActivityRequest) -> ActivityResultEnvelope:
        calls.append(req.idempotency_key)
        return result_for(req)

    runner = LocalActivityRunner({"run_tests": fake_handler})
    req = request()

    result = runner.run(req)

    assert result.status == ActivityStatus.SUCCEEDED
    assert result.evidence_refs == [evidence()]
    assert result.output == {"exit_code": 0}
    assert calls == ["wf-1:run-tests"]


def test_local_activity_runner_skips_duplicate_idempotency_key_without_handler_call():
    calls: list[str] = []

    def fake_handler(req: ActivityRequest) -> ActivityResultEnvelope:
        calls.append(req.activity_id)
        return result_for(req)

    runner = LocalActivityRunner(
        {"run_tests": fake_handler},
        clock=lambda: "2026-07-31T06:00:02Z",
    )
    req = request()

    first = runner.run(req)
    duplicate = runner.run(req)

    assert first.status == ActivityStatus.SUCCEEDED
    assert duplicate.status == ActivityStatus.SKIPPED_DUPLICATE
    assert duplicate.output == {"previous_activity_id": "act-1"}
    assert duplicate.evidence_refs == []
    assert calls == ["act-1"]


def test_local_activity_runner_fails_idempotency_collision_without_handler_call():
    calls: list[str] = []

    def fake_handler(req: ActivityRequest) -> ActivityResultEnvelope:
        calls.append(req.activity_type)
        return result_for(req)

    runner = LocalActivityRunner(
        {"run_tests": fake_handler, "open_pr": fake_handler},
        clock=lambda: "2026-07-31T06:00:04Z",
    )

    first = runner.run(request())
    collision = runner.run(
        request(
            activity_id="act-2",
            activity_type="open_pr",
            role=WorkflowRole.PROJECT_INTAKE_OWNER,
            idempotency_key="wf-1:run-tests",
        )
    )

    assert first.status == ActivityStatus.SUCCEEDED
    assert collision.status == ActivityStatus.FAILED
    assert collision.error == (
        "idempotency key collision: request does not match previously completed activity"
    )
    assert collision.output == {"previous_activity_id": "act-1"}
    assert calls == ["run_tests"]


def test_local_activity_runner_returns_failed_envelope_for_missing_handler():
    runner = LocalActivityRunner({}, clock=lambda: "2026-07-31T06:00:03Z")

    result = runner.run(request(activity_type="missing"))

    assert result.status == ActivityStatus.FAILED
    assert result.error == "no local activity handler registered for 'missing'"
    assert result.started_at == "2026-07-31T06:00:03Z"
    assert result.finished_at == "2026-07-31T06:00:03Z"


def test_local_activity_runner_rejects_mismatched_handler_envelope():
    def bad_handler(req: ActivityRequest) -> ActivityResultEnvelope:
        return result_for(req.model_copy(update={"idempotency_key": "wrong"}))

    runner = LocalActivityRunner({"run_tests": bad_handler})

    with pytest.raises(ValueError, match="idempotency_key does not match request"):
        runner.run(request())


def test_local_activity_runner_requires_evidence_refs_for_required_evidence():
    def bad_handler(req: ActivityRequest) -> ActivityResultEnvelope:
        return result_for(req).model_copy(update={"evidence_refs": []})

    runner = LocalActivityRunner({"run_tests": bad_handler})

    with pytest.raises(ValueError, match="missing required evidence refs"):
        runner.run(request(required_evidence=["command output"]))
