from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from job_agent.config import load_policy, load_profile
from job_agent.models import ApplyAction
from job_agent.prompts import resolve_request
from job_agent.workflow import JobAgentWorkflow

app = typer.Typer(help="Prompt-driven autonomous job search and application assistant.")
console = Console()


def _workflow(profile_path: str, policy_path: str) -> JobAgentWorkflow:
    profile = load_profile(profile_path)
    policy = load_policy(policy_path)
    return JobAgentWorkflow(profile=profile, policy=policy)


def _render_jobs(rows: list[dict]) -> None:
    table = Table(title="Stored Jobs")
    for column in ["company", "title", "source", "score", "status", "url"]:
        table.add_column(column)
    for row in rows:
        table.add_row(
            row["company"],
            row["title"],
            row["source"],
            f"{row['score']:.1f}",
            row["status"],
            row["url"],
        )
    console.print(table)


@app.command()
def search(
    profile: str = typer.Option(..., help="Path to profile YAML."),
    policy: str = typer.Option(..., help="Path to policy YAML."),
    request: Optional[str] = typer.Option(None, help="Natural-language search request."),
    request_file: Optional[str] = typer.Option(None, help="Path to request text file."),
) -> None:
    workflow = _workflow(profile, policy)
    prompt = resolve_request(request, request_file)
    result = asyncio.run(workflow.search(prompt))
    rows = [
        {
            "company": ranked.job.company,
            "title": ranked.job.title,
            "source": ranked.job.source,
            "score": ranked.score,
            "status": "discovered",
            "url": str(ranked.job.url),
        }
        for ranked in result.jobs[:20]
    ]
    _render_jobs(rows)


@app.command()
def list(
    profile: str = typer.Option(..., help="Path to profile YAML."),
    policy: str = typer.Option(..., help="Path to policy YAML."),
    limit: int = typer.Option(20, help="Number of jobs to show."),
) -> None:
    workflow = _workflow(profile, policy)
    _render_jobs(workflow.store.list_jobs(limit=limit))


@app.command()
def apply(
    profile: str = typer.Option(..., help="Path to profile YAML."),
    policy: str = typer.Option(..., help="Path to policy YAML."),
    job_id: str = typer.Option(..., "--job-id", help="Stored job dedupe key."),
    action: ApplyAction = typer.Option(ApplyAction.preview, help="preview, fill, or submit"),
) -> None:
    workflow = _workflow(profile, policy)
    outcome = asyncio.run(workflow.apply(job_id, action))
    console.print(
        {
            "job": outcome.job.title,
            "company": outcome.job.company,
            "action": outcome.action.value,
            "status": outcome.status.value,
            "notes": outcome.notes,
            "screenshots": outcome.screenshot_paths,
        }
    )


@app.command()
def autopilot(
    profile: str = typer.Option(..., help="Path to profile YAML."),
    policy: str = typer.Option(..., help="Path to policy YAML."),
    request: Optional[str] = typer.Option(None, help="Natural-language search request."),
    request_file: Optional[str] = typer.Option(None, help="Path to request text file."),
    max_jobs: int = typer.Option(25, help="How many ranked jobs to keep."),
    apply_limit: int = typer.Option(5, help="How many jobs to run automation against."),
    action: ApplyAction = typer.Option(ApplyAction.fill, help="preview, fill, or submit"),
) -> None:
    workflow = _workflow(profile, policy)
    prompt = resolve_request(request, request_file)
    result = asyncio.run(workflow.autopilot(prompt, max_jobs=max_jobs, apply_limit=apply_limit, action=action))
    rows = [
        {
            "company": ranked.job.company,
            "title": ranked.job.title,
            "source": ranked.job.source,
            "score": ranked.score,
            "status": "processed",
            "url": str(ranked.job.url),
        }
        for ranked in result.jobs
    ]
    _render_jobs(rows)


@app.command("tracker-export")
def tracker_export(
    profile: str = typer.Option(..., help="Path to profile YAML."),
    policy: str = typer.Option(..., help="Path to policy YAML."),
) -> None:
    workflow = _workflow(profile, policy)
    workflow.tracker.export(workflow.store)
    console.print({"tracker": str(workflow.tracker.path)})


@app.command()
def verify(
    profile: str = typer.Option(..., help="Path to profile YAML."),
    policy: str = typer.Option(..., help="Path to policy YAML."),
) -> None:
    workflow = _workflow(profile, policy)
    issues = workflow.tracker.verify()
    if issues:
        console.print({"ok": False, "issues": issues})
        raise typer.Exit(code=1)
    console.print({"ok": True, "tracker": str(workflow.tracker.path)})


@app.command("linkedin-login")
def linkedin_login(
    profile: str = typer.Option(..., help="Path to profile YAML."),
    policy: str = typer.Option(..., help="Path to policy YAML."),
) -> None:
    workflow = _workflow(profile, policy)
    state_path = asyncio.run(workflow.apply_agent.login_linkedin())
    console.print({"linkedin_storage_state": state_path})


if __name__ == "__main__":
    app()
