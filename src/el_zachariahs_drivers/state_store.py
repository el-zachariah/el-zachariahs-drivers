"""Local durable workflow state store.

The JSON store is intentionally adapter-neutral and boring: it persists an initial
state, append-only event/decision logs, and a derived current-state snapshot that
can be rebuilt by deterministic replay after a restart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from el_zachariahs_drivers.models import Blocker, WorkflowDecision, WorkflowEvent, WorkflowStateRecord
from el_zachariahs_drivers.policies.replay import apply_decision, replay_decisions


class WorkflowStatus(BaseModel):
    """Small operational status view for humans, cron, and adapters."""

    workflow_id: str
    phase: str
    next_trigger: str
    blocker: dict[str, Any] | None = None
    evidence_uris: list[str]
    terminal: str | None = None


class JsonWorkflowStore:
    """Append-only local JSON/JSONL store for one workflow instance."""

    initial_state_name = "initial_state.json"
    events_name = "events.jsonl"
    decisions_name = "decisions.jsonl"
    current_state_name = "current_state.json"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @property
    def initial_state_path(self) -> Path:
        return self.root / self.initial_state_name

    @property
    def events_path(self) -> Path:
        return self.root / self.events_name

    @property
    def decisions_path(self) -> Path:
        return self.root / self.decisions_name

    @property
    def current_state_path(self) -> Path:
        return self.root / self.current_state_name

    def initialize(self, state: WorkflowStateRecord, *, overwrite: bool = False) -> WorkflowStateRecord:
        """Create a new store with an initial state.

        Existing stores are rejected by default so a cron or CLI retry cannot
        silently fork durable history.
        """
        if self.initial_state_path.exists() and not overwrite:
            raise FileExistsError("workflow store is already initialized")
        self.root.mkdir(parents=True, exist_ok=True)
        self._write_model(self.initial_state_path, state)
        self.events_path.write_text("", encoding="utf-8")
        self.decisions_path.write_text("", encoding="utf-8")
        self._write_model(self.current_state_path, state)
        return state

    def load_initial_state(self) -> WorkflowStateRecord:
        return WorkflowStateRecord.model_validate_json(self.initial_state_path.read_text(encoding="utf-8"))

    def load_current_state(self) -> WorkflowStateRecord:
        return WorkflowStateRecord.model_validate_json(self.current_state_path.read_text(encoding="utf-8"))

    def append_event(self, event: WorkflowEvent) -> WorkflowEvent:
        self._require_initialized()
        self._append_jsonl(self.events_path, event)
        return event

    def iter_events(self) -> list[WorkflowEvent]:
        return [WorkflowEvent.model_validate(item) for item in self._read_jsonl(self.events_path)]

    def append_decision(self, decision: WorkflowDecision) -> WorkflowStateRecord:
        """Append a decision and update the derived current-state snapshot."""
        self._require_initialized()
        current = self.load_current_state()
        updated = apply_decision(current, decision)
        self._append_jsonl(self.decisions_path, decision)
        self._write_model(self.current_state_path, updated)
        return updated

    def iter_decisions(self) -> list[WorkflowDecision]:
        return [WorkflowDecision.model_validate(item) for item in self._read_jsonl(self.decisions_path)]

    def replay(self) -> WorkflowStateRecord:
        """Replay all persisted decisions from the initial state and refresh the snapshot."""
        replayed = replay_decisions(self.load_initial_state(), self.iter_decisions())
        self._write_model(self.current_state_path, replayed)
        return replayed

    def status(self) -> WorkflowStatus:
        state = self.load_current_state()
        return WorkflowStatus(
            workflow_id=state.workflow_id,
            phase=state.phase,
            next_trigger=self._next_trigger(state),
            blocker=self._blocker_summary(state.blocker),
            evidence_uris=self._status_evidence_uris(state),
            terminal=state.terminal.outcome.value if state.terminal else None,
        )

    def _require_initialized(self) -> None:
        if not self.initial_state_path.exists():
            raise FileNotFoundError("workflow store is not initialized")

    @staticmethod
    def _write_model(path: Path, model: BaseModel) -> None:
        path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _append_jsonl(path: Path, model: BaseModel) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(model.model_dump_json() + "\n")

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc.msg}") from exc
        return records

    @staticmethod
    def _status_evidence_uris(state: WorkflowStateRecord) -> list[str]:
        """Return durable evidence URIs surfaced by the operational status view."""
        refs = [*state.evidence_refs]
        if state.blocker:
            refs.extend(state.blocker.evidence_refs)

        uris: list[str] = []
        seen: set[str] = set()
        for ref in refs:
            if ref.uri in seen:
                continue
            seen.add(ref.uri)
            uris.append(ref.uri)
        return uris

    @staticmethod
    def _next_trigger(state: WorkflowStateRecord) -> str:
        if state.terminal:
            return f"terminal:{state.terminal.outcome.value}"
        if state.blocker:
            return f"blocker:{state.blocker.owner_role.value}:{state.blocker.required_decision}"
        if state.wait:
            return f"wait:{state.wait.awaited_signal} until {state.wait.threshold_at}"
        if state.current_activity:
            return f"activity:{state.current_activity.role.value}:{state.current_activity.activity_id}"
        return "event"

    @staticmethod
    def _blocker_summary(blocker: Blocker | None) -> dict[str, Any] | None:
        if blocker is None:
            return None
        return {
            "owner_role": blocker.owner_role.value,
            "category": blocker.category,
            "required_decision": blocker.required_decision,
            "reason": blocker.reason,
            "resume_phase_if_unblocked": blocker.resume_target.resume_phase_if_unblocked,
        }
