# Five-Pass Design Critique

This note records five critique passes over the initial driver proposal and the changes accepted into the current recommendation.

## Pass 1 — Remove transport assumptions

**Critique:** The workflow docs still implied concrete transports like Hermes profiles in the architecture diagram. That makes the core design too coupled to one runtime.

**Decision:** The core workflow should schedule role-based activities. Runtime configuration binds roles to adapters. Hermes, GitHub, human chat, or another service are adapter implementations, not workflow concepts.

## Pass 2 — Separate project state from task execution

**Critique:** The project diagram risked becoming a big task loop. It needs to own phase gates and task orchestration, not implementation details.

**Decision:** The project driver owns intake, planning, review gates, proof/feedback/release gates, and final reporting. The task driver owns inspect/implement/test/review-fix/rescope for one bounded task.

## Pass 3 — Make waits explicit and bounded

**Critique:** Waiting states can quietly become no-op loops unless every wait has a timer, signal, and threshold response.

**Decision:** Every wait state must define: awaited signal, timeout/threshold, retry policy, and escalation target. A run with no progress signal, no controlled wait, no blocker, and no terminal outcome is `STALLED`.

## Pass 4 — Self-recover before escalating

**Critique:** Review/test findings should not immediately escalate to El-Le or zo-el. The assigned intake owner should first rethink the plan when the original outcome can still be preserved.

**Decision:** Task `RESCOPE_REQUESTED` returns to project `PLAN_RETHINK`. Escalate only if the rethink changes the intake outcome, needs process/developer opinion, or needs human authority/resources/product direction.

## Pass 5 — Tighten the v1 target

**Critique:** The proposal could sprawl into a general agent operating system. That would delay the useful product.

**Decision:** v1 should implement one vertical: software-development project delivery. The product should prove it can drive one project from intake through plan, tasks, PR, review, validation/proof, feedback, release gates, and final report.

## Pass 6 — Add the contract layer before implementation

**Critique:** The lifecycle diagrams are strong, but diagrams alone do not prevent implementation drift. The first code slice could still hide state in adapters, schedule non-idempotent side effects, or lose enough transition context that a restart cannot explain the run.

**Decision:** Add a shared workflow contract for durable state records, typed events/decisions, role-based activity requests, wait policies, blockers, evidence refs, and terminal outcomes. Implement that contract before broad adapter work.

## Clear recommendation after six passes

Build `el-zachariahs-drivers` as a Temporal-style software-development workflow system with two drivers:

1. **SoftwareProjectDriver** — durable outer lifecycle for project/milestone/job execution.
2. **SoftwareTaskDriver** — bounded inner lifecycle for one task.

Keep core workflows role-based and adapter-neutral. Add Temporal implementations only after the workflow docs are tight enough that each state has explicit inputs, outputs, progress signals, wait policy, blocker policy, evidence refs, terminal outcomes, and next transition.
