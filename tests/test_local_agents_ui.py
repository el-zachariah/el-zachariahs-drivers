from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from el_zachariahs_drivers.cli import main
from el_zachariahs_drivers.local_agents import discover_local_agents, render_dashboard


def test_discover_local_agents_lists_profiles_jobs_outputs_and_custom_views(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    agent = profiles / "el-zachariah"
    output_dir = agent / "cron" / "output" / "2637149857cd"
    output_dir.mkdir(parents=True)
    (output_dir / "2026-07-31_16-12-17.md").write_text(
        "# Local agents UI progress\nGenerated board slice.", encoding="utf-8"
    )
    (agent / "cron" / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": "2637149857cd",
                        "name": "local-agents-ui-driver-loop",
                        "enabled": True,
                        "schedule": {"kind": "interval", "minutes": 5, "display": "every 5m"},
                        "last_run_at": "2026-07-31T16:12:17-05:00",
                        "next_run_at": "2026-07-31T16:20:41-05:00",
                        "created_at": "2026-07-31T14:50:10-05:00",
                    },
                    {
                        "id": "disabled",
                        "name": "unknown future job",
                        "enabled": False,
                        "schedule": {"kind": "cron", "expr": "0 3 * * *"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (profiles / "el-micaiah" / "cron").mkdir(parents=True)

    dashboard = discover_local_agents(
        profiles, now=datetime(2026, 7, 31, 21, 15, tzinfo=UTC)
    )

    assert [agent.profile for agent in dashboard.agents] == ["el-micaiah", "el-zachariah"]
    zach = dashboard.agents[1]
    assert zach.job_count == 2
    assert zach.enabled_job_count == 1
    assert zach.jobs[0].id == "2637149857cd"
    assert zach.jobs[0].status == "scheduled"
    assert zach.jobs[0].latest_output is not None
    assert zach.jobs[0].latest_output.preview == "# Local agents UI progress\nGenerated board slice."
    assert zach.jobs[0].custom_view.kind == "local-agents-ui-driver"
    assert zach.jobs[1].status == "disabled"
    assert zach.jobs[1].custom_view.kind == "default"


def test_overdue_enabled_job_is_flagged(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    cron = profiles / "agent" / "cron"
    cron.mkdir(parents=True)
    (cron / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": "review",
                        "name": "GitHub review monitor",
                        "enabled": True,
                        "schedule": {"kind": "interval", "minutes": 5},
                        "next_run_at": "2026-07-31T20:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    dashboard = discover_local_agents(
        profiles, now=datetime(2026, 7, 31, 21, 15, tzinfo=UTC)
    )

    job = dashboard.agents[0].jobs[0]
    assert job.status == "overdue"
    assert job.custom_view.kind == "github-review-monitor"
    assert job.schedule == "every 5m"


def test_render_dashboard_writes_index_data_and_agent_detail(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    cron = profiles / "agent-one" / "cron"
    cron.mkdir(parents=True)
    (cron / "jobs.json").write_text(
        json.dumps([{"id": "inbox", "name": "Proton inbox monitor", "enabled": True}]),
        encoding="utf-8",
    )
    dashboard = discover_local_agents(profiles)
    out = tmp_path / "site"

    written = render_dashboard(dashboard, out)

    assert out / "index.html" in written
    assert out / "data.json" in written
    assert out / "agents" / "agent-one.html" in written
    assert "Local agents board" in (out / "index.html").read_text(encoding="utf-8")
    detail = (out / "agents" / "agent-one.html").read_text(encoding="utf-8")
    assert "Inbox monitor" in detail
    data = json.loads((out / "data.json").read_text(encoding="utf-8"))
    assert data["total_jobs"] == 1
    assert data["agents"][0]["jobs"][0]["custom_view"]["kind"] == "inbox-monitor"


def test_cli_generates_local_agents_ui(tmp_path: Path, capsys) -> None:
    profiles = tmp_path / "profiles"
    cron = profiles / "agent" / "cron"
    cron.mkdir(parents=True)
    (cron / "jobs.json").write_text(
        json.dumps({"jobs": [{"id": "job", "name": "watchdog", "enabled": True}]}),
        encoding="utf-8",
    )
    out = tmp_path / "out"

    assert main(["local-agents-ui", "--profiles-root", str(profiles), "--out", str(out)]) == 0

    assert (out / "index.html").exists()
    assert (out / "agents" / "agent.html").exists()
    assert "1 agents, 1 jobs" in capsys.readouterr().out
