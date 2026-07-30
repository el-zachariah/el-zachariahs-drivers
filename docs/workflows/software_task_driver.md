# Software Task Driver Workflow

The software task driver is the bounded inner workflow. It executes one task created by the project driver or directly assigned when a job is small enough to avoid full project orchestration.

## State diagram

```mermaid
stateDiagram-v2
  [*] --> TASK_ASSIGNED

  TASK_ASSIGNED --> CLAIMED: TASK_STARTED
  CLAIMED --> INSPECTING: worker accepted task
  INSPECTING --> IMPLEMENTING: scope understood
  INSPECTING --> RESCOPE_REQUESTED: task scope is unsafe/wrong
  INSPECTING --> BLOCKED_NEEDS_EL_LE: process/developer opinion needed
  INSPECTING --> BLOCKED_NEEDS_ZO_EL: authority/resource/product decision needed

  IMPLEMENTING --> TESTING: implementation change made
  IMPLEMENTING --> RESCOPE_REQUESTED: implementation reveals plan drift
  IMPLEMENTING --> BLOCKED_NEEDS_EL_LE: process/developer unblock needed
  IMPLEMENTING --> BLOCKED_NEEDS_ZO_EL: human gate needed

  TESTING --> REVIEW_REQUESTED: tests/evidence pass and review required
  TESTING --> COMPLETE: tests/evidence pass and no review required
  TESTING --> IMPLEMENTING: tests fail with local fix path
  TESTING --> RESCOPE_REQUESTED: tests reveal wrong task assumptions

  REVIEW_REQUESTED --> REVIEW_WAIT: review requested once
  REVIEW_WAIT --> FIXING_REVIEW: review completed with findings
  REVIEW_WAIT --> COMPLETE: review approved
  REVIEW_WAIT --> BLOCKED_NEEDS_EL_LE: review wait threshold exceeded

  FIXING_REVIEW --> IMPLEMENTING: accepted findings within loop limit
  FIXING_REVIEW --> RESCOPE_REQUESTED: loop limit exceeded or findings alter task scope

  RESCOPE_REQUESTED --> [*]: return to project PLAN_RETHINK
  BLOCKED_NEEDS_EL_LE --> [*]: return blocker to project/process steward
  BLOCKED_NEEDS_ZO_EL --> [*]: return blocker to project/human approver
  COMPLETE --> [*]
```

## State contract

| State | Purpose | Primary role | Expected outputs | Next decision |
|---|---|---|---|---|
| `TASK_ASSIGNED` | Bounded task input exists. | task driver | claimable work package | claimed |
| `CLAIMED` | Worker accepted task ownership. | developer | task claim evidence | inspect |
| `INSPECTING` | Read repo/context before changing files. | developer | understanding, affected paths, verification plan | implement, rescope, or block |
| `IMPLEMENTING` | Make bounded changes. | developer | code/docs/config changes | testing, rescope, or block |
| `TESTING` | Produce executable evidence. | developer | test/proof/lint result | review, complete, implement again, or rescope |
| `REVIEW_REQUESTED` | Request review once with evidence. | developer/adapters | review request evidence | review wait |
| `REVIEW_WAIT` | Wait for review with threshold. | reviewer | approval/findings | complete, fix, or process block |
| `FIXING_REVIEW` | Apply accepted review findings as a directed repair set. | developer | fixed findings, updated evidence | implement/test or rescope |
| `RESCOPE_REQUESTED` | Task discovered the plan/intake needs rethinking. | task driver | rescope reason and evidence | return to project `PLAN_RETHINK` |
| `COMPLETE` | Terminal task success. | task driver | completion evidence | return to project |
| `BLOCKED_NEEDS_EL_LE` | Process/developer unblock needed. | process steward | precise blocker | return to project |
| `BLOCKED_NEEDS_ZO_EL` | Human authority/resource/product gate. | human approver | precise blocker | return to project |

## Review repair loop

`FIXING_REVIEW` is a bounded directed loop, not an infinite patch cycle.

Rules:

1. Review findings become a repair packet: finding id, severity, disposition, fix plan, affected files, verification command.
2. The developer fixes all accepted findings that safely fit the task scope.
3. Each pass increments `review_loop_count`.
4. When `review_loop_count >= max_review_loops`, or a finding changes task assumptions, the task emits `RESCOPE_REQUESTED` instead of looping again.
5. `RESCOPE_REQUESTED` returns control to the project driver's `PLAN_RETHINK` state before escalating.

## Task output shape

A completed or blocked task should return:

```yaml
task_id: string
phase: COMPLETE | RESCOPE_REQUESTED | BLOCKED_NEEDS_EL_LE | BLOCKED_NEEDS_ZO_EL
evidence:
  - command/result, PR URL, commit, file path, or review link
rescope_reason: optional string
blocker: optional actionable blocker
progress_signals:
  - TASK_COMPLETED | TASK_RESCOPE_REQUESTED | BLOCKER_CREATED | ...
```

## Task run invariant

A task-driver run must not end with a silent observation. It must emit one of:

- material progress: code changed, test evidence created, review requested/completed, findings fixed, task completed;
- controlled wait: review wait timer or retry scheduled;
- rescope: `RESCOPE_REQUESTED` with evidence and reason;
- blocker: owner role plus required decision;
- terminal failed/done.

If it emits none, the task run is `STALLED` and the project driver should not count it as progress.
