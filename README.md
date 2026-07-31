# el-zachariahs-drivers

Durable workflow engine for **software project and task execution**.

The first bundled workflow templates externalize el-zachariah's software-development execution pattern, but that pattern is a proving profile, not the product boundary.

This is intentionally **not** "zo-el's brain" and not a generic agent swarm. It is a reusable engine for moving software work forward without relying on chat memory, stale cron loops, or hidden local state.

## Design stance

- Reuse production workflow patterns and libraries instead of inventing a private orchestration system.
- Treat Temporal as the likely first durable-runtime backend, not as the product model itself.
- Use deterministic workflow templates to decide state transitions; activities perform side effects.
- Keep LangGraph-compatible seams for agent decision subgraphs where useful, but do not make an LLM own durable state.
- Split the first software-delivery template into two drivers:
  - **Project driver**: owns the full software project lifecycle and phase transitions.
  - **Task driver**: owns one bounded implementation/review/proof task.

## Current workflow proposal

The current documentation proposal should be engine-first and template-second:

1. Define the product goal: a reusable durable workflow engine for software projects/tasks.
2. Define the shared workflow contract: durable state records, typed events, role-based activity requests, wait policies, blocker ownership, and evidence references.
3. Provide `SoftwareProjectDriver` and `SoftwareTaskDriver` as the first reusable software-delivery templates.
4. Bind concrete workers/transports through runtime profiles and adapters.

```text
SoftwareProjectDriver
  PROJECT_INTAKE_ASSIGNED
  → PLANNING
  → PLAN_REVIEW
  → TASK_BREAKDOWN
  → TASK_EXECUTION
      ↳ SoftwareTaskDriver per bounded task
  → CHANGE_ARTIFACT_READY (PR in GitHub profile)
  → REVIEW_REQUESTED / REVIEW_WAIT
  → FIXING_REVIEW or PROOF_AUTH_WAIT or FEEDBACK_READY
  → FEEDBACK_WAIT
  → DOGFOOD_GATE / MERGE_GATE when configured
  → FINAL_REPORT
  → DONE, FAILED, CANCELLED, or BLOCKED_NEEDS_*
```

Start with:

- [`docs/product_goal.md`](docs/product_goal.md) for the reusable-engine target and non-goals.
- [`docs/architecture.md`](docs/architecture.md) for the system boundary and v1 target.
- [`docs/workflow_contract.md`](docs/workflow_contract.md) for the common implementation contract.
- [`docs/workflows/software_project_driver.md`](docs/workflows/software_project_driver.md) for the outer lifecycle.
- [`docs/workflows/software_task_driver.md`](docs/workflows/software_task_driver.md) for the bounded task lifecycle.
- [`docs/design_iterations.md`](docs/design_iterations.md) for accepted critique passes.

## Repository map

```text
docs/
  product_goal.md                         Reusable-engine target, non-goals, and product-layer boundaries.
  architecture.md                         System boundary, design stance, and v1 target.
  workflow_contract.md                    Shared state/event/activity/wait/blocker contract.
  design_iterations.md                    Accepted critique passes and recommendation history.
  workflows/
    software_project_driver.md            Outer durable project lifecycle.
    software_task_driver.md               Inner bounded task lifecycle.
src/el_zachariahs_drivers/
  cli.py                                  Local JSON store/replay/status CLI.
  models.py                               Shared typed state/events.
  state_store.py                          Local durable state/event/decision JSON store.
  workflows/
    project_driver.py                     Durable-runtime project lifecycle workflow skeleton.
    task_driver.py                        Durable-runtime bounded task workflow skeleton.
  activities/
    contracts.py                          Activity interfaces; side effects live behind these contracts.
  policies/
    progress.py                           Material-progress/no-op detection policy.
    escalation.py                         Configured escalation routing policy.
  adapters/
    hermes.py                             Placeholder adapter boundary for runtime worker integrations.
examples/
  agent_toolkit_slice_1.yaml              Example config named after the concrete project slice.
tests/
  test_policies.py                        Pure deterministic policy tests.
```

## Current status

Bones only. The first review goal is to discuss each file and agree whether the concepts/files are right before deeper implementation.
