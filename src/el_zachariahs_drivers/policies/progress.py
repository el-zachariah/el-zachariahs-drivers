"""Material-progress policy.

A driver run is only useful if it changes durable state or produces new evidence.
Repeated observation of the same state is not progress.
"""

from __future__ import annotations

from collections.abc import Iterable

from el_zachariahs_drivers.models import Blocker, ProgressSignal, RunOutcome

MATERIAL_PROGRESS_SIGNALS = frozenset(
    {
        ProgressSignal.PROJECT_ACCEPTED,
        ProgressSignal.PLAN_CREATED,
        ProgressSignal.PLAN_REVIEW_REQUESTED,
        ProgressSignal.PLAN_APPROVED,
        ProgressSignal.PLAN_REVISED,
        ProgressSignal.TASKS_CREATED,
        ProgressSignal.TASK_STARTED,
        ProgressSignal.TASK_COMPLETED,
        ProgressSignal.TASK_RESCOPE_REQUESTED,
        ProgressSignal.PR_CREATED,
        ProgressSignal.PR_UPDATED,
        ProgressSignal.PR_HEAD_CHANGED,
        ProgressSignal.TEST_EVIDENCE_CREATED,
        ProgressSignal.PROOF_AUTH_REQUESTED,
        ProgressSignal.PROOF_STARTED,
        ProgressSignal.PROOF_EVIDENCE_CREATED,
        ProgressSignal.PROOF_COMPLETED,
        ProgressSignal.PROOF_REPAIR_REQUIRED,
        ProgressSignal.REVIEW_REQUESTED,
        ProgressSignal.REVIEW_STARTED,
        ProgressSignal.REVIEW_COMPLETED,
        ProgressSignal.REVIEW_FINDINGS_ACCEPTED,
        ProgressSignal.REVIEW_FINDINGS_FIXED,
        ProgressSignal.FEEDBACK_REQUESTED,
        ProgressSignal.FEEDBACK_RECEIVED,
        ProgressSignal.DOGFOOD_STARTED,
        ProgressSignal.DOGFOOD_COMPLETED,
        ProgressSignal.MERGE_READY,
        ProgressSignal.RELEASE_COMPLETED,
        ProgressSignal.BLOCKER_CREATED,
        ProgressSignal.BLOCKER_ESCALATED,
        ProgressSignal.BLOCKER_RESOLVED,
        ProgressSignal.FINAL_REPORT_DELIVERED,
    }
)

CONTROLLED_WAIT_SIGNALS = frozenset(
    {
        ProgressSignal.RETRY_SCHEDULED,
        ProgressSignal.WAIT_TIMER_STARTED,
    }
)


def has_material_progress(signals: Iterable[ProgressSignal]) -> bool:
    """Return True if this run produced at least one durable progress signal."""
    return any(signal in MATERIAL_PROGRESS_SIGNALS for signal in signals)


def classify_run_outcome(
    signals: Iterable[ProgressSignal],
    *,
    blocker: Blocker | None = None,
    done: bool = False,
    failed: bool = False,
) -> RunOutcome:
    """Classify a driver run outcome.

    Lack of progress is not a progress signal. If a run emits no material signal,
    schedules no controlled wait, creates no blocker, and reaches no terminal
    state, the run is stalled and should be treated as a workflow failure.
    """
    signal_set = set(signals)
    if done:
        return RunOutcome.DONE
    if failed:
        return RunOutcome.FAILED
    if blocker or signal_set & {ProgressSignal.BLOCKER_CREATED, ProgressSignal.BLOCKER_ESCALATED}:
        return RunOutcome.BLOCKED
    if signal_set & MATERIAL_PROGRESS_SIGNALS:
        return RunOutcome.MATERIAL_PROGRESS
    if signal_set & CONTROLLED_WAIT_SIGNALS:
        return RunOutcome.CONTROLLED_WAIT
    return RunOutcome.STALLED
