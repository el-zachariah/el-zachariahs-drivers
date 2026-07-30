# Product Goal

The target product is a reusable durable workflow engine for software projects and software tasks.

The current project/task driver proposal is useful only if it is treated as a reusable engine plus a first software-delivery template. It is the wrong product if the implementation hardcodes one developer, one council, one chat surface, one GitHub PR flow, or one agent runtime into the core.

## Goal statement

Build a durable engine that can take a software-work intake, decompose it into bounded work, schedule role-based activities through replaceable adapters, preserve progress across restarts, enforce review/validation/release gates, and produce evidence-backed completion or blockers.

The engine should be reusable across projects and teams. `el-zachariah`'s workflow is the first proving template, not the whole system boundary.

## Non-goals

The engine is not:

- a private memory store for one agent;
- a generic agent swarm with no durable process model;
- a hardcoded Hermes/Kanban/Discord/GitHub bot;
- a one-off PR automation script;
- an LLM-owned state machine; or
- a replacement for human product/resource/merge authority.

## Product layers

The design should separate these layers:

1. **Engine core** — workflow runs, durable state, event replay, timers, signals, idempotent activity scheduling, blockers, evidence references, and terminal outcomes.
2. **Software workflow templates** — reusable state machines such as `SoftwareProjectDriver` and `SoftwareTaskDriver`.
3. **Policies** — progress/no-op detection, review-loop limits, escalation routing, retry thresholds, gate requirements, and cancellation/failure semantics.
4. **Runtime profiles** — bindings from abstract roles to concrete workers, services, queues, channels, or credentials.
5. **Adapters** — GitHub, CI, agent runtime, human approval, evidence storage, notification, and other side-effect implementations.

A change belongs in the core only if it remains true across different software projects, workers, and transport adapters. Anything specific to zo-el's council, el-zachariah, Micaiah, Hermes, Kanban, Discord, or a GitHub repository belongs in a runtime profile, adapter, or example.

## What the current proposal gets right

- Durable state is the right center of gravity.
- Project/task split is a reasonable first template: an outer project lifecycle and bounded inner task lifecycles.
- Roles should be abstract and adapter-bound.
- Waits, retries, blockers, and no-op observations need explicit contracts.
- Review and validation should be first-class, not afterthoughts hidden in chat.

## What must change before implementation

| Concern | Why it matters | Proposed correction |
|---|---|---|
| The docs still read partly like `el-zachariah`'s personal execution pattern. | A reusable engine cannot bake one worker identity into its product model. | Make `el-zachariah` a sample runtime profile/template consumer, not the core boundary. |
| GitHub PR and dogfood states appear as universal lifecycle phases. | Not every software project produces a GitHub PR or has the same release gate. | Treat PR/review/proof/dogfood/merge as configurable artifact, review, validation, feedback, and release gates in the template. |
| Temporal is named as the implementation style before the product contract is fully fixed. | Temporal may be the right runtime, but the reusable contract should survive a runtime swap. | Document Temporal as the likely first backend, not as the product model itself. |
| Role bindings name the zo-el council directly in the workflow docs. | That makes examples look like engine requirements. | Move concrete bindings to examples/runtime profiles and keep workflow docs role-only. |
| The acceptance criteria prove resumability for one vertical, but not reuse. | A one-off durable flow can pass that test and still fail as an engine. | Add acceptance that the same engine core can run at least two different software-work configurations or adapter profiles. |

## Correct v1 shape

The first implementation should prove one narrow vertical, but that vertical should be structured as:

```text
DurableWorkflowEngine core
  → SoftwareProjectDriver template
      → SoftwareTaskDriver template
  → runtime profile: el-zachariah software delivery
  → adapters: GitHub / CI / agent runtime / human approval / evidence storage
```

The engine core should not know it is serving `el-zachariah`. The runtime profile may know that.

## v1 acceptance criteria

A credible v1 should demonstrate:

1. A software project intake can be planned, decomposed, executed through task runs, reviewed, validated, gated, and reported.
2. The run survives process restart and can answer current phase, next trigger, owner role, blocker, and evidence refs from durable state alone.
3. All side effects are behind idempotent activity requests and replay-safe decisions.
4. At least one runtime profile binds roles to the current council/agent setup without leaking those identities into core models.
5. A second minimal profile or fixture can run the same core with different role/adapters, proving the design is reusable rather than only hardcoded to one developer flow.
