# Workflow Contract

The state diagrams describe the intended lifecycle, but implementation should start from a common contract shared by both drivers. Without this layer, a Temporal workflow can still drift into ad-hoc activity calls, hidden adapter state, or repeated observations that look like progress.

This contract is the proposed source of truth for the first implementation slice.

## Contract boundary

The core workflow may know about:

- typed workflow state;
- typed events and transition guards;
- role-based activity requests;
- wait policies;
- blocker ownership;
- evidence references; and
- terminal outcomes.

The core workflow must not know about:

- Discord threads;
- Hermes profile names;
- Kanban card mechanics;
- a particular agent CLI;
- GitHub notification internals; or
- local filesystem paths outside configured evidence/storage adapters.

Those details belong to adapter configuration and activity implementations.

## State record shape

Every durable driver instance should be able to serialize a state record with this shape:

```yaml
workflow_id: string
driver_kind: SoftwareProjectDriver | SoftwareTaskDriver
phase: string
input:
  intake_id: optional string
  project_id: optional string
  task_id: optional string
  input_digest: string
role_bindings_version: string
plan_version: optional string
current_activity: optional
  activity_id: string
  role: string
  requested_at: timestamp
  deadline_at: optional timestamp
wait: optional
  awaited_signal: string
  started_at: timestamp
  threshold_at: timestamp
  retry_policy: string
blocker: optional
  owner_role: process_steward | human_approver | project_intake_owner | developer | reviewer | proof_runner
  reason: string
  required_decision: string
evidence_refs:
  - type: plan | task | commit | pull_request | review | command | proof | report | adapter_record
    uri: string
    digest: optional string
progress_ledger:
  last_material_progress_at: optional timestamp
  last_progress_signal: optional string
  no_op_observation_count: integer
counters:
  review_loop_count: optional integer
  retry_count: integer
terminal: optional
  outcome: DONE | FAILED | CANCELLED
  reason: optional string
  final_report_ref: optional string
```

The exact model names can change, but the implementation should preserve the invariant that a restart can answer: where the run is, why it is there, what it is waiting for, who owns the next decision, and what evidence backs the answer.

## Event and decision shape

Each workflow tick should consume one typed event and emit one typed decision.

```yaml
event:
  event_id: string
  type: string
  emitted_at: timestamp
  source_role: string
  correlation_id: string
  causation_id: optional string
  payload: object

decision:
  decision_id: string
  from_phase: string
  to_phase: string
  material_progress: boolean
  progress_signal: optional string
  activities_to_schedule:
    - ActivityRequest
  wait_to_start: optional WaitPolicy
  blocker_to_record: optional Blocker
  evidence_refs:
    - EvidenceRef
  terminal_outcome: optional DONE | FAILED | CANCELLED
```

A decision that repeats the same phase is valid only when it also records material progress, a controlled wait/retry, a blocker, or a terminal outcome.

## Activity request contract

Role-based activities are the only way the workflow asks the outside world to do work. Every scheduled activity should include:

```yaml
activity_id: string
activity_type: string
role: project_intake_owner | developer | reviewer | proof_runner | process_steward | human_approver
purpose: string
input_refs:
  - uri: string
acceptance_criteria:
  - string
allowed_side_effects:
  - none | git_branch | git_commit | pull_request | review | command | external_service | user_message
required_evidence:
  - string
idempotency_key: string
timeout_policy:
  start_to_close: duration
  schedule_to_close: duration
retry_policy:
  max_attempts: integer
  backoff: string
on_failure:
  rescope_allowed: boolean
  blocker_owner_role: string
```

Adapters may add transport metadata, but the core workflow should be able to decide whether an activity result is acceptable without reading adapter-private state.

## Wait policy contract

A wait is controlled only if it records all of these fields:

```yaml
awaited_signal: string
started_at: timestamp
threshold_at: timestamp
retry_policy: string
threshold_response: BLOCKED_NEEDS_EL_LE | BLOCKED_NEEDS_ZO_EL | RETRY_SCHEDULED | FAILED
```

If the workflow cannot name the awaited signal and the threshold response, it is not waiting; it is stalled.

## Blocker policy

A blocker is not a terminal state. It is a durable request for a specific owner role to provide a decision.

A valid blocker must include:

- owner role;
- reason;
- requested decision;
- evidence references;
- whether the current intake outcome is still preserved; and
- the state to resume from if unblocked.

`BLOCKED_NEEDS_EL_LE` should mean process/developer ambiguity. `BLOCKED_NEEDS_ZO_EL` should mean product, resource, spending, credential, merge/release, or dogfood authority.

## Driver interaction contract

The project driver may create one or more task-driver runs. A task driver may not secretly mutate the project plan. It returns a task result packet:

```yaml
task_id: string
phase: COMPLETE | RESCOPE_REQUESTED | BLOCKED_NEEDS_EL_LE | BLOCKED_NEEDS_ZO_EL | FAILED | CANCELLED
evidence_refs:
  - EvidenceRef
progress_signals:
  - TASK_COMPLETED | TASK_RESCOPE_REQUESTED | BLOCKER_CREATED | TASK_FAILED | TASK_CANCELLED
rescope_reason: optional string
blocker: optional Blocker
repair_recommendations:
  - optional string
```

The project driver then decides whether to continue task execution, enter `PLAN_RETHINK`, record a blocker, fail, cancel, or report completion.

## Adapter-neutrality test

A workflow change is adapter-neutral if the answer to each question is yes:

1. Can the state transition be replayed without Discord, Kanban, GitHub notifications, or a specific agent profile?
2. Is every side effect behind an activity request with an idempotency key?
3. Can an adapter be replaced while preserving the role, evidence, and blocker contracts?
4. Can a restart reconstruct the next trigger and owner from durable state alone?
5. Does a repeated observation produce a controlled wait, blocker, terminal outcome, or explicit `STALLED` failure?

## v1 acceptance criteria

The first implementation slice should prove this contract before broad feature expansion:

1. Project and task state records serialize and rehydrate.
2. A replay of recorded events reaches the same phases and decisions.
3. A task `RESCOPE_REQUESTED` packet returns to project `PLAN_RETHINK` without human escalation when the original intake outcome can still be preserved.
4. A wait with no signal beyond its threshold records the configured blocker or failure path.
5. A simulated process restart can report current phase, next trigger, owner role, blocker if any, and evidence refs without consulting chat memory or adapter-private state.
