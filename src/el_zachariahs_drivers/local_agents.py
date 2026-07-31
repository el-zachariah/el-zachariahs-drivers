"""Local Hermes profile and cron/job dashboard generator.

This module is intentionally a controlled local layer: it reads Hermes profile
state from disk and emits static artifacts. It does not modify Hermes upstream
code or profile configuration.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JobOutput:
    path: str
    modified_at: str | None
    preview: str


@dataclass(frozen=True)
class JobCustomView:
    kind: str
    title: str
    summary: str
    fields: dict[str, str] = field(default_factory=dict)
    optimization_hints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LocalJob:
    id: str
    name: str
    enabled: bool | None
    schedule: str
    schedule_kind: str
    last_run_at: str | None
    next_run_at: str | None
    created_at: str | None
    state: str | None
    last_status: str | None
    last_error: str | None
    repeat: str | None
    workdir: str | None
    toolsets: list[str]
    prompt_preview: str | None
    status: str
    status_detail: str
    latest_output: JobOutput | None
    custom_view: JobCustomView
    raw_keys: list[str]


@dataclass(frozen=True)
class LocalAgent:
    profile: str
    path: str
    exists: bool
    job_count: int
    enabled_job_count: int
    heartbeat_at: str | None
    jobs: list[LocalJob]


@dataclass(frozen=True)
class LocalAgentsDashboard:
    generated_at: str
    profiles_root: str
    agents: list[LocalAgent]

    @property
    def total_jobs(self) -> int:
        return sum(agent.job_count for agent in self.agents)

    @property
    def enabled_jobs(self) -> int:
        return sum(agent.enabled_job_count for agent in self.agents)


def discover_local_agents(profiles_root: str | Path, *, now: datetime | None = None) -> LocalAgentsDashboard:
    """Discover local Hermes profiles and their cron jobs."""

    root = Path(profiles_root).expanduser()
    current_time = now or datetime.now(UTC)
    agents: list[LocalAgent] = []
    if root.exists():
        for profile_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            agents.append(_discover_agent(profile_dir, current_time))
    return LocalAgentsDashboard(
        generated_at=_format_dt(current_time),
        profiles_root=str(root),
        agents=agents,
    )


def render_dashboard(dashboard: LocalAgentsDashboard, out_dir: str | Path) -> list[Path]:
    """Render static HTML and JSON artifacts for a dashboard."""

    output = Path(out_dir)
    agents_dir = output / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    written = [output / "data.json", output / "index.html"]
    (output / "data.json").write_text(
        json.dumps(_dashboard_to_dict(dashboard), indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "index.html").write_text(_render_index(dashboard), encoding="utf-8")

    for agent in dashboard.agents:
        page = agents_dir / f"{_slug(agent.profile)}.html"
        page.write_text(_render_agent(agent, dashboard), encoding="utf-8")
        written.append(page)
    return written


def generate_dashboard(profiles_root: str | Path, out_dir: str | Path) -> LocalAgentsDashboard:
    dashboard = discover_local_agents(profiles_root)
    render_dashboard(dashboard, out_dir)
    return dashboard


def _discover_agent(profile_dir: Path, now: datetime) -> LocalAgent:
    jobs = _load_jobs(profile_dir, now)
    heartbeat = profile_dir / "state" / "gateway.heartbeat"
    heartbeat_at = _file_mtime(heartbeat) if heartbeat.exists() else None
    return LocalAgent(
        profile=profile_dir.name,
        path=str(profile_dir),
        exists=True,
        job_count=len(jobs),
        enabled_job_count=sum(1 for job in jobs if job.enabled is True),
        heartbeat_at=heartbeat_at,
        jobs=jobs,
    )


def _load_jobs(profile_dir: Path, now: datetime) -> list[LocalJob]:
    jobs_path = profile_dir / "cron" / "jobs.json"
    if not jobs_path.exists():
        return []
    try:
        payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    records = payload.get("jobs", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        return []

    jobs = []
    for index, record in enumerate(records):
        if isinstance(record, dict):
            jobs.append(_job_from_record(profile_dir, record, index, now))
    return sorted(jobs, key=lambda job: (job.enabled is not True, job.name.lower(), job.id))


def _job_from_record(profile_dir: Path, record: dict[str, Any], index: int, now: datetime) -> LocalJob:
    job_id = str(record.get("id") or f"job-{index}")
    name = str(record.get("name") or record.get("title") or job_id)
    schedule = record.get("schedule")
    schedule_display = _schedule_display(schedule)
    schedule_kind = schedule.get("kind", "unknown") if isinstance(schedule, dict) else "unknown"
    enabled = record.get("enabled")
    enabled_bool = enabled if isinstance(enabled, bool) else None
    last_run_at = _string_or_none(record.get("last_run_at"))
    next_run_at = _string_or_none(record.get("next_run_at"))
    state = _string_or_none(record.get("state"))
    last_status = _string_or_none(record.get("last_status"))
    last_error = _string_or_none(record.get("last_error") or record.get("last_delivery_error"))
    repeat = _repeat_display(record.get("repeat"))
    workdir = _string_or_none(record.get("workdir"))
    toolsets = _string_list(record.get("enabled_toolsets"))
    prompt_preview = _preview_text(record.get("prompt"), 280)
    status, detail = _job_status(enabled_bool, state, last_status, last_error, next_run_at, now)
    latest_output = _latest_output(profile_dir, job_id)
    custom_view = _custom_view_for_job(
        name,
        job_id,
        schedule_display,
        enabled_bool,
        latest_output,
        state=state,
        last_status=last_status,
        repeat=repeat,
        workdir=workdir,
        toolsets=toolsets,
    )
    return LocalJob(
        id=job_id,
        name=name,
        enabled=enabled_bool,
        schedule=schedule_display,
        schedule_kind=schedule_kind,
        last_run_at=last_run_at,
        next_run_at=next_run_at,
        created_at=_string_or_none(record.get("created_at")),
        state=state,
        last_status=last_status,
        last_error=last_error,
        repeat=repeat,
        workdir=workdir,
        toolsets=toolsets,
        prompt_preview=prompt_preview,
        status=status,
        status_detail=detail,
        latest_output=latest_output,
        custom_view=custom_view,
        raw_keys=sorted(str(key) for key in record),
    )


def _schedule_display(schedule: Any) -> str:
    if isinstance(schedule, dict):
        if schedule.get("display"):
            return str(schedule["display"])
        if schedule.get("kind") == "interval" and schedule.get("minutes"):
            return f"every {schedule['minutes']}m"
        if schedule.get("expr"):
            return str(schedule["expr"])
    return "unscheduled/unknown"


def _job_status(
    enabled: bool | None,
    state: str | None,
    last_status: str | None,
    last_error: str | None,
    next_run_at: str | None,
    now: datetime,
) -> tuple[str, str]:
    if last_error:
        return "error", f"Last error: {_preview_text(last_error, 160) or last_error}"
    if last_status and last_status.lower() not in {"ok", "success", "completed"}:
        return "attention", f"Last status: {last_status}"
    if enabled is False:
        detail = f"Job is present but {state}." if state else "Job is present but disabled."
        return "disabled", detail
    if enabled is None:
        return "unknown", "Job metadata does not declare enabled state."
    if next_run_at:
        parsed = _parse_dt(next_run_at)
        if parsed and parsed < now:
            return "overdue", f"Next run time is in the past: {next_run_at}"
        return "scheduled", f"Next run: {next_run_at}"
    return "enabled", "Enabled; next run was not recorded."


def _latest_output(profile_dir: Path, job_id: str) -> JobOutput | None:
    output_dir = profile_dir / "cron" / "output" / job_id
    if not output_dir.exists():
        return None
    files = sorted((p for p in output_dir.glob("*.md") if p.is_file()), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    latest = files[-1]
    text = latest.read_text(encoding="utf-8", errors="replace")
    preview = "\n".join(line.strip() for line in text.splitlines() if line.strip())[:500]
    return JobOutput(path=str(latest), modified_at=_file_mtime(latest), preview=preview)


def _custom_view_for_job(
    name: str,
    job_id: str,
    schedule: str,
    enabled: bool | None,
    output: JobOutput | None,
    *,
    state: str | None,
    last_status: str | None,
    repeat: str | None,
    workdir: str | None,
    toolsets: list[str],
) -> JobCustomView:
    lower = name.lower()
    words = set(re.findall(r"[a-z0-9]+", lower))
    base_fields = {
        "job_id": job_id,
        "schedule": schedule,
        "enabled": str(enabled),
        "state": state or "not recorded",
        "last_status": last_status or "not recorded",
        "repeat": repeat or "not configured",
        "workdir": workdir or "not configured",
        "toolsets": ", ".join(toolsets) if toolsets else "not recorded",
    }
    if "github" in words or "review" in words or "pr" in words:
        return JobCustomView(
            kind="github-review-monitor",
            title="GitHub / review monitor",
            summary="Tracks GitHub attention, PR review, or requested-change loops.",
            fields=base_fields | {"latest_output": output.path if output else "none detected"},
            optimization_hints=[
                "Treat unchanged PR/check state as controlled wait, not material progress.",
                "When review feedback cites docs/examples, check whether model or policy code also needs a regression test.",
            ],
        )
    if any(token in lower for token in ["proton", "inbox", "email"]):
        return JobCustomView(
            kind="inbox-monitor",
            title="Inbox monitor",
            summary="Watches mailbox state and should report only newly actionable items.",
            fields=base_fields,
            optimization_hints=["Keep a seen-state ledger so repeated empty inbox scans can return [SILENT]."],
        )
    if "local-agents" in lower or "local agents" in lower or "ui" in words:
        return JobCustomView(
            kind="local-agents-ui-driver",
            title="Local agents UI driver",
            summary="Drives this dashboard work through PR/review/merge evidence.",
            fields=base_fields,
            optimization_hints=[
                "Each tick must produce material progress, controlled wait, blocker, done, or failed.",
                "End and remove the cron once the dashboard backlog is complete.",
            ],
        )
    if "agent-toolkit" in lower:
        return JobCustomView(
            kind="agent-toolkit-driver",
            title="Agent Toolkit project driver",
            summary="Moves agent-toolkit implementation slices through PR and review gates.",
            fields=base_fields,
            optimization_hints=["Prefer small branch slices and re-check live PR state before every write."],
        )
    if "wealth" in words or "first-dollar" in lower or "first dollar" in lower:
        return JobCustomView(
            kind="wealth-hunter-revenue",
            title="Wealth hunter / first-dollar loop",
            summary="Tracks concrete revenue or buyer-acquisition work and should avoid activity-only reports.",
            fields=base_fields | {"latest_output": output.path if output else "none detected"},
            optimization_hints=[
                "Report only verified revenue movement, buyer contact changes, or a new human-owned blocker.",
                "Paused/expired deadline jobs should stay visible but not wake users unless reactivated intentionally.",
            ],
        )
    if "revenue" in words or "buyer" in words or "customer" in words:
        return JobCustomView(
            kind="revenue-experiment",
            title="Revenue experiment loop",
            summary="Moves buyer-facing experiments toward validated exposure, payment, or customer feedback.",
            fields=base_fields | {"latest_output": output.path if output else "none detected"},
            optimization_hints=[
                "Separate durable experiment evidence from chat updates.",
                "Prefer externally observable buyer/payment signals over internal asset churn.",
            ],
        )
    if "self" in words and "check" in words or "readiness" in words or "recovery" in words:
        return JobCustomView(
            kind="agent-health-check",
            title="Agent health/readiness check",
            summary="Verifies agent-owned surfaces, cron health, or readiness state before escalating issues.",
            fields=base_fields | {"latest_output": output.path if output else "none detected"},
            optimization_hints=[
                "Empty/healthy checks should produce [SILENT] or controlled wait.",
                "Escalate only changed failures with owner and required decision/action.",
            ],
        )
    if any(token in lower for token in ["watchdog", "sentinel"]):
        return JobCustomView(
            kind="watchdog",
            title="Watchdog / sentinel",
            summary="Monitors a system boundary for missing heartbeats or actionable changes.",
            fields=base_fields,
            optimization_hints=["Escalate only on changed failure evidence; otherwise record controlled wait."],
        )
    if any(token in lower for token in ["curator", "growth", "daily"]):
        return JobCustomView(
            kind="maintenance-growth",
            title="Maintenance / growth loop",
            summary="Runs recurring maintenance, learning, or improvement workflows.",
            fields=base_fields,
            optimization_hints=["Keep outputs concise and attach durable evidence paths for non-chat review."],
        )
    return JobCustomView(
        kind="default",
        title="Default cron/job view",
        summary="Auto-detected job with generic metadata. Add a custom view by matching this job pattern.",
        fields=base_fields,
        optimization_hints=["New jobs are visible here automatically until a developer adds a custom renderer."],
    )


def _render_index(dashboard: LocalAgentsDashboard) -> str:
    rows = []
    for agent in dashboard.agents:
        rows.append(
            "<tr>"
            f"<td><a href='agents/{_slug(agent.profile)}.html'>{_e(agent.profile)}</a></td>"
            f"<td>{agent.job_count}</td><td>{agent.enabled_job_count}</td>"
            f"<td>{_e(agent.heartbeat_at or 'not detected')}</td>"
            f"<td>{_e(agent.path)}</td>"
            "</tr>"
        )
    return _page(
        "Local agents board",
        f"""
        <p>Generated {_e(dashboard.generated_at)} from <code>{_e(dashboard.profiles_root)}</code>.</p>
        <section class='stats'>
          <div><strong>{len(dashboard.agents)}</strong><span>agents</span></div>
          <div><strong>{dashboard.total_jobs}</strong><span>jobs</span></div>
          <div><strong>{dashboard.enabled_jobs}</strong><span>enabled jobs</span></div>
        </section>
        <table><thead><tr><th>Agent</th><th>Jobs</th><th>Enabled</th><th>Heartbeat</th><th>Path</th></tr></thead>
        <tbody>{''.join(rows)}</tbody></table>
        """,
    )


def _render_agent(agent: LocalAgent, dashboard: LocalAgentsDashboard) -> str:
    cards = []
    for job in agent.jobs:
        output = "No output detected."
        if job.latest_output:
            output = (
                f"<p><strong>Latest output:</strong> <code>{_e(job.latest_output.path)}</code> "
                f"({_e(job.latest_output.modified_at or 'unknown mtime')})</p>"
                f"<pre>{_e(job.latest_output.preview or '(empty output)')}</pre>"
            )
        fields = "".join(
            f"<li><strong>{_e(key)}:</strong> {_e(value)}</li>"
            for key, value in job.custom_view.fields.items()
        )
        hints = "".join(f"<li>{_e(hint)}</li>" for hint in job.custom_view.optimization_hints)
        cards.append(
            f"""
            <article class='job {job.status}'>
              <h2>{_e(job.name)}</h2>
              <p><strong>Status:</strong> {_e(job.status)} — {_e(job.status_detail)}</p>
              <p><strong>Schedule:</strong> {_e(job.schedule)} ({_e(job.schedule_kind)})</p>
              <p><strong>State:</strong> {_e(job.state or 'not recorded')}<br>
                 <strong>Last status:</strong> {_e(job.last_status or 'not recorded')}<br>
                 <strong>Last error:</strong> {_e(job.last_error or 'none')}<br>
                 <strong>Repeat:</strong> {_e(job.repeat or 'not configured')}</p>
              <p><strong>Workdir:</strong> <code>{_e(job.workdir or 'not configured')}</code><br>
                 <strong>Toolsets:</strong> {_e(', '.join(job.toolsets) if job.toolsets else 'not recorded')}</p>
              <p><strong>Prompt preview:</strong> {_e(job.prompt_preview or 'not recorded')}</p>
              <p><strong>Last run:</strong> {_e(job.last_run_at or 'not recorded')}<br>
                 <strong>Next run:</strong> {_e(job.next_run_at or 'not recorded')}<br>
                 <strong>Created:</strong> {_e(job.created_at or 'not recorded')}</p>
              <section><h3>{_e(job.custom_view.title)}</h3>
                <p>{_e(job.custom_view.summary)}</p>
                <ul>{fields}</ul>
                <h4>Optimization/default-view hints</h4><ul>{hints}</ul>
              </section>
              {output}
              <details><summary>Raw metadata keys</summary><code>{_e(', '.join(job.raw_keys))}</code></details>
            </article>
            """
        )
    if not cards:
        cards.append("<p>No cron/jobs detected for this agent. New jobs appear automatically when a cron/jobs.json file is created.</p>")
    return _page(
        f"Agent: {agent.profile}",
        f"""
        <p><a href='../index.html'>← main board</a></p>
        <p>Generated {_e(dashboard.generated_at)}. Profile path: <code>{_e(agent.path)}</code></p>
        <section class='stats'>
          <div><strong>{agent.job_count}</strong><span>jobs</span></div>
          <div><strong>{agent.enabled_job_count}</strong><span>enabled</span></div>
          <div><strong>{_e(agent.heartbeat_at or 'none')}</strong><span>heartbeat</span></div>
        </section>
        {''.join(cards)}
        """,
    )


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{_e(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; background: #f7f8fb; }}
a {{ color: #1d4ed8; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #d8deea; padding: .55rem; text-align: left; vertical-align: top; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 1rem; margin: 1rem 0; }}
.stats div {{ background: white; border: 1px solid #d8deea; border-radius: .6rem; padding: .8rem 1rem; }}
.stats strong {{ display: block; font-size: 1.4rem; }}
.job {{ background: white; border: 1px solid #d8deea; border-left: .5rem solid #94a3b8; border-radius: .6rem; padding: 1rem; margin: 1rem 0; }}
.job.scheduled, .job.enabled {{ border-left-color: #16a34a; }}
.job.disabled {{ border-left-color: #64748b; opacity: .86; }}
.job.overdue {{ border-left-color: #dc2626; }}
.job.error, .job.attention {{ border-left-color: #f97316; }}
pre {{ white-space: pre-wrap; background: #0f172a; color: #e2e8f0; padding: .75rem; border-radius: .4rem; max-height: 14rem; overflow: auto; }}
code {{ word-break: break-word; }}
</style>
</head>
<body>
<h1>{_e(title)}</h1>
{body}
</body>
</html>
"""


def _dashboard_to_dict(dashboard: LocalAgentsDashboard) -> dict[str, Any]:
    return asdict(dashboard) | {"total_jobs": dashboard.total_jobs, "enabled_jobs": dashboard.enabled_jobs}


def _file_mtime(path: Path) -> str:
    return _format_dt(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))


def _format_dt(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_dt(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _repeat_display(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    times = value.get("times")
    completed = value.get("completed")
    if times is None and completed is None:
        return None
    return f"{completed if completed is not None else '?'} / {times if times is not None else '?'}"


def _preview_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 1]}…"


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "-" for char in value)


def _e(value: str) -> str:
    return html.escape(value, quote=True)
