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

## Initial workflow shape

```text
SoftwareProjectDriver
  PROJECT_ASSIGNED
  → PROJECT_PLANNING
  → TASK_BREAKDOWN
  → TASK_EXECUTION
      ↳ SoftwareTaskDriver per task
  → PR_INTEGRATION
  → REVIEW_PHASE
  → PROOF_PHASE
  → FEEDBACK_PHASE
  → DOGFOOD_OR_MERGE_GATE
  → DONE or BLOCKED
```

## Repository map

```text
src/el_zachariahs_drivers/
  models.py                 Shared typed state/events.
  workflows/
    project_driver.py       Temporal-style project lifecycle workflow skeleton.
    task_driver.py          Temporal-style bounded task workflow skeleton.
  activities/
    contracts.py            Activity interfaces; side effects live behind these contracts.
  policies/
    progress.py             Material-progress/no-op detection policy.
    escalation.py           El-Le vs zo-el escalation routing policy.
  adapters/
    hermes.py               Placeholder adapter boundary for Hermes/Kanban/GitHub workers.
examples/
  software_project.yaml     Example project configuration.
tests/
  test_policies.py          Pure deterministic policy tests.
```

## Current status

Bones only. The first review goal is to discuss each file and agree whether the concepts/files are right before deeper implementation.
