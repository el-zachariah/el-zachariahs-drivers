"""Command-line access to the local durable workflow state store."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from el_zachariahs_drivers.models import WorkflowDecision, WorkflowEvent, WorkflowStateRecord
from el_zachariahs_drivers.state_store import JsonWorkflowStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="el-zachariahs-drivers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize a local workflow store")
    init_parser.add_argument("store", type=Path)
    init_parser.add_argument("--state", required=True, type=Path, help="WorkflowStateRecord JSON file")
    init_parser.add_argument("--overwrite", action="store_true", help="replace an existing store")

    append_event_parser = subparsers.add_parser("append-event", help="append a WorkflowEvent JSON file")
    append_event_parser.add_argument("store", type=Path)
    append_event_parser.add_argument("--event", required=True, type=Path, help="WorkflowEvent JSON file")

    append_decision_parser = subparsers.add_parser(
        "append-decision", help="append a WorkflowDecision JSON file and update current state"
    )
    append_decision_parser.add_argument("store", type=Path)
    append_decision_parser.add_argument("--decision", required=True, type=Path, help="WorkflowDecision JSON file")

    replay_parser = subparsers.add_parser("replay", help="replay decisions and print current state")
    replay_parser.add_argument("store", type=Path)

    status_parser = subparsers.add_parser("status", help="print phase, next trigger, blocker, evidence")
    status_parser.add_argument("store", type=Path)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = JsonWorkflowStore(args.store)

    if args.command == "init":
        state = _read_model(args.state, WorkflowStateRecord)
        _print_model(store.initialize(state, overwrite=args.overwrite))
        return 0
    if args.command == "append-event":
        event = _read_model(args.event, WorkflowEvent)
        _print_model(store.append_event(event))
        return 0
    if args.command == "append-decision":
        decision = _read_model(args.decision, WorkflowDecision)
        _print_model(store.append_decision(decision))
        return 0
    if args.command == "replay":
        _print_model(store.replay())
        return 0
    if args.command == "status":
        _print_model(store.status())
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _read_model(path: Path, model_type: type[BaseModel]) -> BaseModel:
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def _print_model(model: BaseModel) -> None:
    print(model.model_dump_json(indent=2))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
