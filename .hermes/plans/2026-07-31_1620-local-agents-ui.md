# Local agents UI implementation plan

## Goal

Build a controlled local layer in `el-zachariahs-drivers` that discovers Hermes local profiles and cron/job metadata, then emits a cohesive static dashboard with an agent board, per-agent detail pages, default cron/job views, and extensible custom views.

## Boundary / upstream justification

Do **not** change `/home/zachariah/.hermes/hermes-agent`. The UI only needs to read local Hermes state (`~/.hermes/profiles/*/cron/jobs.json`, output directories, heartbeat/status files) and present it. A static artifact generator in this repo is sufficient, profile-safe, easy to test with fixtures, and broadly avoids upstream release/review risk.

## Slices

### Slice 1: discovery and data model

Files:
- `src/el_zachariahs_drivers/local_agents.py`
- `tests/test_local_agents_ui.py`

Tasks:
1. Add dataclasses for `LocalAgent`, `LocalJob`, `JobOutput`, and `JobCustomView`.
2. Discover profile dirs under a passed `profiles_root`.
3. Parse `cron/jobs.json` container forms (`{"jobs": [...]}` and list fallback).
4. Detect latest output markdown under `cron/output/<job_id>/`.
5. Compute default status (`enabled`, `disabled`, `overdue`, `unknown`) from metadata.
6. Add deterministic tests with temp profile fixtures.

Verification:
- `uv run pytest tests/test_local_agents_ui.py -q`

### Slice 2: static UI renderer and CLI

Files:
- `src/el_zachariahs_drivers/local_agents.py`
- `src/el_zachariahs_drivers/cli.py`
- `README.md`
- `tests/test_local_agents_ui.py`

Tasks:
1. Render `index.html`, one `agents/<profile>.html` detail page per detected profile, and `data.json`.
2. Make the main board list all detected agents and link to detail pages.
3. Make each detail page list all jobs with schedule, enabled state, last/next run, latest output, and custom/default view hints.
4. Add CLI: `el-zachariahs-drivers local-agents-ui --profiles-root ... --out ...`.
5. Document usage and auto-detection/default/custom view rules.

Verification:
- `uv run pytest tests/test_local_agents_ui.py -q`
- `uv run pytest -q`
- `uv run el-zachariahs-drivers local-agents-ui --profiles-root /home/zachariah/.hermes/profiles --out build/local-agents-ui`

### Slice 3: known-job custom views and cron optimization hints

Files:
- `src/el_zachariahs_drivers/local_agents.py`
- `tests/test_local_agents_ui.py`
- `README.md`

Tasks:
1. Add keyword-based custom views for known local job patterns: GitHub monitor/review, Proton/inbox monitor, local-agents UI driver, agent-toolkit driver, watchdog/sentinel, curator/growth.
2. Surface optimization hints: silence/no-op policy, review wait vs progress, active interval cadence warnings, disabled stale jobs.
3. Keep unknown new jobs on the generic/default card.

Verification:
- Targeted + full tests and generated live artifact smoke test.

## Review gate

Commit and push the implementation branch, open a PR, and request/tag `el-micaiah`. If review requests changes, fix code/tests/docs and re-request. Merge only after approval, mergeability, and green local verification.
