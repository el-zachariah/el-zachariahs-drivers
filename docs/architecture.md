# el-zachariahs-drivers Architecture

This repo externalizes el-zachariah's software-development execution pattern into durable drivers.

The core design is intentionally not tied to Hermes Kanban, Discord, or any single agent transport. Those are adapters. The durable workflow owns state and schedules role-based activities.

## System boundary

```mermaid
flowchart TD
  User[zo-el / requester] -->|assigns work| ProjectDriver[Software Project Driver]

  ProjectDriver -->|plans, scopes, creates tasks| ProjectState[(Durable Project State)]
  ProjectDriver -->|runs task workflow| TaskDriver[Software Task Driver]
  TaskDriver --> TaskState[(Durable Task State)]

  ProjectDriver -->|schedule role activity| Activities[Workflow Activities]
  TaskDriver -->|schedule role activity| Activities

  Activities --> Adapters[Adapter Layer]
  Adapters --> GitHub[GitHub PRs / reviews / checks]
  Adapters --> Hermes[Hermes agent profiles]
  Adapters --> Temporal[Temporal timers / signals]
  Adapters --> HumanGateway[Human approval channel]

  Activities --> Dev[Developer role]
  Activities --> Reviewer[Reviewer role]
  Activities --> Steward[Process steward role]
  Activities --> Approver[Human approver role]
```

## Design principles

1. **Workflow owns state.** Chat memory is not project state.
2. **Agents are workers.** They execute bounded activities with inputs and acceptance criteria.
3. **Roles are abstract.** The workflow calls `developer`, `reviewer`, `process_steward`, or `human_approver`; adapters bind those roles to real agents/services/channels.
4. **No implicit no-op progress.** A run must produce material progress, a controlled wait, a blocker, done, or failed. Otherwise it is stalled.
5. **Self-recover before escalating.** Task-level findings first return to project plan rethink. Escalate only if the intake outcome changes or outside authority/opinion is needed.
6. **Human gates are explicit.** Spending, credentials, product scope, merge, deploy, and dogfood activation wait for explicit approval signals.

## Layers

```mermaid
flowchart LR
  Spec[Workflow spec] --> Models[Typed models]
  Models --> Workflows[Temporal workflows]
  Workflows --> Activities[Activity contracts]
  Activities --> Adapters[Runtime adapters]
  Adapters --> Evidence[PRs / tests / reviews / reports]
```

## Driver split

- **Project driver**: owns lifecycle, planning, task breakdown, gates, and final reporting.
- **Task driver**: owns one bounded software task: inspect, implement, test, review/fix loop, complete, block, or request rescope.

The project driver may create many task-driver runs. A small job can still enter the project driver if it needs durable state, but simple one-shot work should go directly to a task driver or normal agent execution.
