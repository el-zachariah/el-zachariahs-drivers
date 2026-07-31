"""Deterministic replay helpers for the durable workflow contract."""

from __future__ import annotations

from collections.abc import Iterable

from el_zachariahs_drivers.models import (
    CurrentActivity,
    EvidenceRef,
    ProgressLedger,
    ProgressSignal,
    TerminalOutcome,
    TerminalState,
    WorkflowDecision,
    WorkflowEvent,
    WorkflowStateRecord,
)


def apply_decision(state: WorkflowStateRecord, decision: WorkflowDecision) -> WorkflowStateRecord:
    """Return a new state record after applying one deterministic decision.

    The function is intentionally small and pure: a workflow implementation can
    persist the returned model and a replay can reproduce the same record from
    the same input state and decisions.
    """
    if decision.from_phase != state.phase:
        raise ValueError(
            f"cannot apply decision from phase {decision.from_phase!r} to state in phase {state.phase!r}"
        )

    next_state = state.model_copy(deep=True)
    next_state.phase = decision.to_phase
    next_state.current_activity = None

    if decision.activities_to_schedule:
        activity = decision.activities_to_schedule[0]
        next_state.current_activity = CurrentActivity(
            activity_id=activity.activity_id,
            role=activity.role,
            requested_at=decision.decided_at,
            deadline_at=None,
        )

    if decision.wait_to_start:
        next_state.wait = decision.wait_to_start
    elif decision.to_phase != state.phase:
        next_state.wait = None

    if decision.blocker_to_record:
        next_state.blocker = decision.blocker_to_record
        next_state.wait = None
    elif decision.progress_signal == ProgressSignal.BLOCKER_RESOLVED:
        next_state.blocker = None

    next_state.evidence_refs.extend(decision.evidence_refs)

    if decision.material_progress and decision.progress_signal:
        next_state.progress_ledger = ProgressLedger(
            last_material_progress_at=decision.decided_at,
            last_progress_signal=decision.progress_signal,
            no_op_observation_count=0,
        )
    elif decision.from_phase == decision.to_phase and not any(
        (decision.wait_to_start, decision.blocker_to_record, decision.activities_to_schedule)
    ):
        next_state.progress_ledger.no_op_observation_count += 1

    if decision.terminal_outcome:
        next_state.terminal = TerminalState(outcome=decision.terminal_outcome)

    return next_state


def replay_decisions(
    initial_state: WorkflowStateRecord,
    decisions: Iterable[WorkflowDecision],
) -> WorkflowStateRecord:
    """Replay decisions from an initial state."""
    state = initial_state
    for decision in decisions:
        state = apply_decision(state, decision)
    return state


def replay_events(
    initial_state: WorkflowStateRecord,
    events: Iterable[WorkflowEvent],
    decide,
) -> WorkflowStateRecord:
    """Replay events through a deterministic decision function.

    `decide` receives `(state, event)` and returns a `WorkflowDecision`.
    """
    state = initial_state
    for event in events:
        state = apply_decision(state, decide(state, event))
    return state


def evidence_digest(evidence_refs: Iterable[EvidenceRef]) -> tuple[tuple[str, str, str | None], ...]:
    """Stable evidence summary used by tests and adapters for replay checks."""
    return tuple((ref.type.value, ref.uri, ref.digest) for ref in evidence_refs)


def is_terminal(outcome: TerminalOutcome | None) -> bool:
    return outcome in {TerminalOutcome.DONE, TerminalOutcome.FAILED, TerminalOutcome.CANCELLED}
