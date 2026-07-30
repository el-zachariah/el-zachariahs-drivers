# Software Project Driver Workflow

The software project driver is the outer durable workflow. It manages a project intake, a project milestone, or a durable job that needs lifecycle tracking.

## State diagram

```mermaid
stateDiagram-v2
  [*] --> PROJECT_INTAKE_ASSIGNED

  PROJECT_INTAKE_ASSIGNED --> PLANNING: PROJECT_ACCEPTED
  PLANNING --> PLAN_REVIEW: PLAN_CREATED
  PLAN_REVIEW --> TASK_BREAKDOWN: PLAN_APPROVED
  PLAN_REVIEW --> PLANNING: PLAN_REVISED
  PLAN_REVIEW --> BLOCKED_NEEDS_EL_LE: process/developer disagreement
  PLAN_REVIEW --> BLOCKED_NEEDS_ZO_EL: outcome/scope authority needed

  TASK_BREAKDOWN --> TASK_EXECUTION: TASKS_CREATED

  TASK_EXECUTION --> TASK_EXECUTION: TASK_COMPLETED / more tasks remain
  TASK_EXECUTION --> PLAN_RETHINK: TASK_RESCOPE_REQUESTED
  PLAN_RETHINK --> TASK_BREAKDOWN: PLAN_REVISED / outcome unchanged
  PLAN_RETHINK --> BLOCKED_NEEDS_EL_LE: needs process/developer opinion
  PLAN_RETHINK --> BLOCKED_NEEDS_ZO_EL: intake outcome changes
  TASK_EXECUTION --> PR_OPEN: all required tasks complete

  PR_OPEN --> REVIEW_REQUESTED: PR_CREATED or PR_UPDATED
  REVIEW_REQUESTED --> REVIEW_WAIT: REVIEW_REQUESTED
  REVIEW_WAIT --> FIXING_REVIEW: REVIEW_COMPLETED with findings
  REVIEW_WAIT --> PROOF_AUTH_WAIT: REVIEW_COMPLETED approved and proof required
  REVIEW_WAIT --> FEEDBACK_READY: REVIEW_COMPLETED approved and no proof required
  REVIEW_WAIT --> BLOCKED_NEEDS_EL_LE: review wait threshold exceeded

  FIXING_REVIEW --> TASK_EXECUTION: REVIEW_FINDINGS_ACCEPTED
  FIXING_REVIEW --> PLAN_RETHINK: findings change plan assumptions

  PROOF_AUTH_WAIT --> PROOF_RUNNING: approval signal received
  PROOF_AUTH_WAIT --> FEEDBACK_READY: proof explicitly skipped / feedback-only
  PROOF_AUTH_WAIT --> BLOCKED_NEEDS_ZO_EL: proof resource/authority decision needed

  PROOF_RUNNING --> FEEDBACK_READY: PROOF_COMPLETED
  PROOF_RUNNING --> PROOF_REPAIR: PROOF_REPAIR_REQUIRED
  PROOF_REPAIR --> TASK_EXECUTION: repair task created

  FEEDBACK_READY --> FEEDBACK_WAIT: FEEDBACK_REQUESTED
  FEEDBACK_WAIT --> TASK_BREAKDOWN: FEEDBACK_RECEIVED with changes
  FEEDBACK_WAIT --> DOGFOOD_GATE: FEEDBACK_RECEIVED accepted / dogfood required
  FEEDBACK_WAIT --> MERGE_GATE: FEEDBACK_RECEIVED accepted / merge required
  FEEDBACK_WAIT --> FINAL_REPORT: feedback accepted / no release gate

  DOGFOOD_GATE --> MERGE_GATE: DOGFOOD_COMPLETED
  DOGFOOD_GATE --> BLOCKED_NEEDS_ZO_EL: dogfood activation approval needed
  MERGE_GATE --> FINAL_REPORT: RELEASE_COMPLETED or merge skipped
  MERGE_GATE --> BLOCKED_NEEDS_ZO_EL: merge/release approval needed

  FINAL_REPORT --> DONE: FINAL_REPORT_DELIVERED

  BLOCKED_NEEDS_EL_LE --> PLANNING: process unblock preserves outcome
  BLOCKED_NEEDS_EL_LE --> PLAN_RETHINK: process unblock requires rethink
  BLOCKED_NEEDS_ZO_EL --> PLANNING: human decision changes scope
  BLOCKED_NEEDS_ZO_EL --> PROOF_RUNNING: human approves proof
  BLOCKED_NEEDS_ZO_EL --> FINAL_REPORT: human stops / accepts current artifact
```

## State contract

| State | Purpose | Primary role | Expected outputs | Next decision |
|---|---|---|---|---|
| `PROJECT_INTAKE_ASSIGNED` | A durable work intake exists but is not yet planned. | project intake owner | accepted/rejected intake, initial constraints | move to planning or block for authority |
| `PLANNING` | Produce a project/milestone plan with acceptance and gates. | project intake owner | plan artifact | request plan review |
| `PLAN_REVIEW` | Independent check before task creation. | reviewer | approval or findings | task breakdown, planning revision, or block |
| `PLAN_RETHINK` | Self-recovery after task/review findings reveal plan drift. | project intake owner | revised plan/tasks, unchanged-or-changed outcome assessment | task breakdown or escalation |
| `TASK_BREAKDOWN` | Create bounded task-driver inputs. | project intake owner | task list with acceptance/evidence commands | task execution |
| `TASK_EXECUTION` | Run task drivers until required tasks complete or rescope. | developer/task driver | completed tasks, evidence, rescope requests | continue, rethink, or PR open |
| `PR_OPEN` | Create/update remote feedback artifact. | developer | PR URL/head | review request |
| `REVIEW_REQUESTED` | Request review once and record evidence. | project driver/adapters | review request evidence | review wait |
| `REVIEW_WAIT` | Wait for reviewer result with threshold. | reviewer | review approval/findings | fix, proof, feedback, or process block |
| `FIXING_REVIEW` | Turn review findings into task-driver repair work. | developer | accepted findings, repair tasks | task execution or plan rethink |
| `PROOF_AUTH_WAIT` | Wait for explicit proof/resource approval when required. | human approver | approval/denial signal | proof running, feedback-only, or block |
| `PROOF_RUNNING` | Execute approved proof under current controls. | proof runner/developer | proof packet/evidence | feedback ready or proof repair |
| `PROOF_REPAIR` | Repair proof harness/control problems. | developer | repair task | task execution |
| `FEEDBACK_READY` | Artifact is ready for user feedback. | project driver | feedback request | feedback wait |
| `FEEDBACK_WAIT` | Wait for feedback window/result. | human approver/requester | feedback accepted/changes | tasks, dogfood, merge, or final report |
| `DOGFOOD_GATE` | Real-use validation gate if configured. | human approver/developer | dogfood approval/evidence | merge gate or block |
| `MERGE_GATE` | Merge/release decision gate if configured. | human approver | merge/release approval/evidence | final report or block |
| `FINAL_REPORT` | Produce final evidence-backed report. | project intake owner | final report | done |
| `DONE` | Terminal success. | workflow | immutable summary | none |
| `BLOCKED_NEEDS_EL_LE` | Process/developer unblock needed. | process steward | decision or diagnosis | resume or rethink |
| `BLOCKED_NEEDS_ZO_EL` | Human authority/resource/product gate. | human approver | decision | resume, stop, or revise |

## Run invariant

Every project-driver tick/activity completion must result in exactly one of:

1. material progress signal;
2. controlled wait with timer/signal condition;
3. blocker with owner role and required decision;
4. terminal done/failed outcome.

If none is produced, the run is `STALLED` and should be treated as a workflow failure, not as progress.
