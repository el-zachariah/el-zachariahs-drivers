# Workflow V2 Process Hardening Plan

## Goal

Build a good V2 of the `el-zachariah` driver workflow after the local-agents UI initiative exposed major process bugs. V2 must make it hard for the agent/supervisor to do visible work in the wrong target, skip human-reviewed planning, or mark an initiative complete without proving the original intent.

This plan is the artifact to verify with Micaiah before implementation.

## Source event: failed live driver-test

User request summary:

- Use a driver-test loop to give the driver an INITIATIVE/INTAKE.
- Intake: upgrade the currently running local UI/dashboard for el-le brain and Micaiah.
- Expected UI result: main dashboard lists Hermes agents on this device; each agent page lists crons; unknown crons get default view; selected crons can get custom views.
- Expected process result: test whether the driver can plan/build/complete; if stuck, fix driver bugs; file good findings; end only when intake completed by the driver.

What happened:

- The workflow created/used `el-zachariah/hermes-council-mind` and a LAN preview on `9120`.
- The actually running UI at `http://192.168.0.110:8787/` was not replaced or upgraded.
- That service runs from `/home/zachariah/Documents/el-micaiah/micaiah-status-ui`.
- The workflow reached terminal `DONE` anyway.

Conclusion: V1 can create state, PRs, evidence, review loops, and terminal conditions, but it can still complete the wrong work.

## Issue backlog

Critical issues:

- #18 — Workflow must require human-reviewed proposal before ambiguous UI implementation.
- #19 — Workflow DONE must validate original intake acceptance criteria.
- #20 — Driver-test supervisor must not count non-driver-authorized implementation as progress.
- #21 — Workflow must route cross-profile target ownership before implementation.
- #22 — Workflow needs explicit proposal approval gate before ambiguous implementation.

High-value regression/audit issue:

- #23 — Add failed-run audit fixture for v2 process invariants.

Already fixed during the failed run:

- #15 — Review request triggers must be verified before `REVIEW_WAIT`.
- #16 — Human blockers need visible notification and resume instructions.

## V2 principles

1. **Proposal before implementation for ambiguous initiatives.** If the intake touches product/UI/live systems/existing services, implementation is blocked until a proposal is produced and reviewed.
2. **Live target first.** If the user says a service/UI already exists, the driver must inventory process/port/HTTP identity/cwd/repo before choosing a target.
3. **Ownership is a gate.** A target under another agent profile is not silently bypassed; route collaboration or request approval.
4. **Driver-authorized actions only count.** Supervisor actions can fix the driver or emergency-unblock, but cannot count as initiative progress unless tied to a workflow decision/activity.
5. **Done means original intake satisfied.** Terminal `DONE` requires an acceptance report against the approved proposal and original criteria.
6. **Every gate is executable.** These cannot remain documentation-only. Add model/policy helpers, tests, and CLI/status visibility.

## Proposed V2 workflow shape

```text
PROJECT_INTAKE_ASSIGNED
→ SOURCE_DISCOVERY
→ PROPOSAL_DRAFTED
→ HUMAN_PLAN_REVIEW
→ PLAN_APPROVED
→ TASK_BREAKDOWN
→ TASK_EXECUTION
→ PR_OPEN
→ REVIEW_REQUESTED
→ REVIEW_WAIT
→ FIXING_REVIEW / PROOF_RUNNING
→ ACCEPTANCE_PROOF
→ FINAL_REPORT
→ DONE
```

Blocked branches:

```text
SOURCE_DISCOVERY → BLOCKED_NEEDS_EL_LE      # process/ownership ambiguity
SOURCE_DISCOVERY → BLOCKED_NEEDS_ZO_EL      # human authority/product target decision
HUMAN_PLAN_REVIEW → BLOCKED_NEEDS_ZO_EL     # user approval required
ACCEPTANCE_PROOF → PLAN_RETHINK             # proof shows wrong target/scope
```

## Required model/policy changes

### 1. Proposal artifact model

Add a structured proposal record or evidence convention containing:

- intake id/workflow id;
- discovered sources and target surfaces;
- candidate implementation targets;
- ownership boundary analysis;
- recommended target and why;
- alternatives rejected;
- acceptance criteria;
- approval requirement.

### 2. Source discovery contract

Add `SourceDiscoveryReport` or equivalent with:

- URL/port/process evidence;
- cwd/repo/worktree evidence;
- HTTP page identity/title/route hints;
- owner profile inference;
- confidence level;
- required next gate.

### 3. Proposal approval gate policy

Add transition validation that prevents ambiguous initiatives from entering `TASK_BREAKDOWN`, `TASK_EXECUTION`, or `PR_OPEN` until proposal approval evidence exists.

### 4. Driver authorization evidence

Each implementation/deployment progress signal must reference an authorizing driver decision/activity. Supervisor interventions must be marked separately and cannot satisfy initiative progress by default.

### 5. Acceptance proof / terminal policy

Add terminal policy that requires:

- approved target;
- criteria-by-criteria evidence;
- live verification for UI/service work;
- explicit substitute approval if the deliverable is a preview or replacement repo rather than original target.

## Implementation slices

### Slice A — Proposal/source-discovery models and status

Issues: #18, #21, #22.

Deliverables:

- model(s) for source discovery and proposal approval evidence;
- status fields showing proposal approval required/approved;
- tests for cross-profile target discovery and proposal blocking.

Verification:

```bash
python3 -m py_compile $(python3 - <<'PY'
from pathlib import Path
for p in Path('src').rglob('*.py'):
    print(p)
for p in Path('tests').rglob('*.py'):
    print(p)
PY
)
PYTHONPATH=src python3 -m pytest tests -q
```

### Slice B — Transition policy enforcement

Issues: #18, #20, #22.

Deliverables:

- policy rejecting implementation/PR phases without proposal approval for ambiguous initiatives;
- policy rejecting material progress without driver authorization evidence in driver-test mode;
- tests for both blocked and approved paths.

### Slice C — Acceptance proof and DONE gate

Issue: #19.

Deliverables:

- acceptance report model/convention;
- terminal `DONE` validation helper;
- regression test showing `9120` preview cannot satisfy `8787` target unless approved.

### Slice D — Failed-run audit fixture

Issue: #23.

Deliverables:

- fixture based on local-agents UI failed run;
- invariant checker reporting proposal/source/ownership/authorization/done proof failures;
- test that the failed run cannot pass V2 invariants.

## Review and implementation loop

1. Open this plan as a PR.
2. Tag/request Micaiah with full context and explicit request to verify the plan before implementation.
3. Do not implement V2 until plan review has been received and critical findings are resolved.
4. After plan approval, implement one slice at a time.
5. For each implementation PR:
   - run py_compile and tests;
   - tag/request Micaiah;
   - address changes requested;
   - merge only after approval/mergeability verification;
   - close or update issues as evidence.
6. End the loop when all critical issues #18-#22 are closed and #23 has a passing regression/audit fixture, or when a blocker with owner/decision is reached.

## Definition of good V2

V2 is good enough when the same local-agents UI initiative cannot repeat the failure:

- it discovers `8787` before choosing a repo;
- it identifies `/home/zachariah/Documents/el-micaiah/micaiah-status-ui` as cross-profile;
- it produces a proposal for user review;
- it waits for approval before implementation;
- it routes collaboration/ownership correctly;
- it cannot mark `DONE` unless the approved target and original acceptance criteria are verified.
