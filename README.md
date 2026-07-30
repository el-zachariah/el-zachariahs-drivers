# el-zachariahs-drivers

Durable project and task drivers for **el-zachariah's software-development execution patterns**.

This is intentionally **not** "zo-el's brain" and not a generic agent swarm. It is a reusable place to externalize how a developer agent should move software projects forward without relying on chat memory, stale cron loops, or hidden local state.

## Design stance

- Reuse production workflow patterns and libraries instead of inventing a private orchestration system.
- Use Temporal-style separation: deterministic workflows decide state transitions; activities perform side effects.
- Keep LangGraph-compatible seams for agent decision subgraphs where useful, but do not make an LLM own durable state.
- Split the system into two drivers:
  - **Project driver**: owns the full software project lifecycle and phase transitions.
  - **Task driver**: owns one bounded implementation/review/proof task.

## Current workflow proposal

The current documentation proposal is contract-first:

1. Define the shared workflow contract: durable state records, typed events, role-based activity requests, wait policies, blocker ownership, and evidence references.
2. Run an outer `SoftwareProjectDriver` for durable project/milestone/job lifecycle.
3. Spawn bounded `SoftwareTaskDriver` runs for implementation, review-repair, proof-repair, or directly assigned small tasks.
4. Keep all transports and concrete workers behind adapters.

```text
SoftwareProjectDriver
  PROJECT_INTAKE_ASSIGNED
  → PLANNING
  → PLAN_REVIEW
  → TASK_BREAKDOWN
  → TASK_EXECUTION
      ↳ SoftwareTaskDriver per bounded task
  → PR_OPEN
  → REVIEW_REQUESTED / REVIEW_WAIT
  → FIXING_REVIEW or PROOF_AUTH_WAIT or FEEDBACK_READY
  → FEEDBACK_WAIT
  → DOGFOOD_GATE / MERGE_GATE when configured
  → FINAL_REPORT
  → DONE, FAILED, CANCELLED, or BLOCKED_NEEDS_*
```

Start with:

- [`docs/architecture.md`](docs/architecture.md) for the system boundary and v1 target.
- [`docs/workflow_contract.md`](docs/workflow_contract.md) for the common implementation contract.
- [`docs/workflows/software_project_driver.md`](docs/workflows/software_project_driver.md) for the outer lifecycle.
- [`docs/workflows/software_task_driver.md`](docs/workflows/software_task_driver.md) for the bounded task lifecycle.
- [`docs/design_iterations.md`](docs/design_iterations.md) for accepted critique passes.

## Repository map

```text
docs/
  architecture.md                         System boundary, design stance, and v1 target.
  workflow_contract.md                    Shared state/event/activity/wait/blocker contract.
  design_iterations.md                    Accepted critique passes and recommendation history.
  workflows/
    software_project_driver.md            Outer durable project lifecycle.
    software_task_driver.md               Inner bounded task lifecycle.
src/el_zachariahs_drivers/
  models.py                               Shared typed state/events.
  workflows/
    project_driver.py                     Temporal-style project lifecycle workflow skeleton.
    task_driver.py                        Temporal-style bounded task workflow skeleton.
  activities/
    contracts.py                          Activity interfaces; side effects live behind these contracts.
  policies/
    progress.py                           Material-progress/no-op detection policy.
    escalation.py                         El-Le vs zo-el escalation routing policy.
  adapters/
    hermes.py                             Placeholder adapter boundary for runtime worker integrations.
examples/
  agent_toolkit_slice_1.yaml              Example config named after the concrete project slice.
tests/
  test_policies.py                        Pure deterministic policy tests.
```

## Current status

Bones only. The first review goal is to discuss each file and agree whether the concepts/files are right before deeper implementation.
