import json
import sqlite3
import uuid

import typer

from queuectl.config import get_config, set_config
from queuectl.db import Database
from queuectl.models import Job, JobState, utc_now
from queuectl.worker import run_worker

app = typer.Typer(
    help="QueueCTL - A command-line background job queue."
)

worker_app = typer.Typer(help="Manage workers.")
app.add_typer(worker_app, name="worker")

config_app = typer.Typer(help="Manage configuration.")
app.add_typer(config_app, name="config")

@config_app.command("set")
def config_set(key: str, value: str):
    """Set a configuration value."""
    set_config(key, value)
    typer.echo(f"Set {key} to {value}")

@config_app.command("get")
def config_get(key: str):
    """Get a configuration value."""
    val = get_config(key)
    typer.echo(f"{key}: {val}")


dlq_app = typer.Typer(help="Manage the Dead Letter Queue.")
app.add_typer(dlq_app, name="dlq")

@dlq_app.command("list")
def dlq_list():
    """List dead jobs."""
    with Database() as db:
        dead_jobs = db.list_jobs(state=JobState.DEAD)

    if not dead_jobs:
        typer.echo("No jobs in the Dead Letter Queue.")
        return

    for job in dead_jobs:
        typer.echo(f"{job.id}\tAttempts: {job.attempts}\tCommand: {job.command}")

@dlq_app.command("retry")
def dlq_retry(job_id: str):
    """Retry a dead job."""
    with Database() as db:
        job = db.get_job(job_id)

        if job is None:
            typer.echo("Job not found.")
            raise typer.Exit(1)

        if job.state != JobState.DEAD:
            typer.echo("Job is not in the Dead Letter Queue.")
            raise typer.Exit(1)

        job.state = JobState.PENDING
        job.attempts = 0
        job.next_run_at = utc_now()

        db.update_job(job)

    typer.echo(f"Requeued {job.id}")


@worker_app.command("start")
def start_worker():
    """Start the worker."""
    with Database() as db:
        run_worker(db)


@worker_app.command("stop")
def stop_worker():
    """Stop worker(s)."""
    typer.echo(
        "Worker stop is not currently implemented. Workers run in the foreground "
        "and can be stopped with Ctrl+C.\n"
        "Graceful SIGTERM management is planned as a future improvement."
    )


@app.command()
def enqueue(payload: str):
    """
    Add a job to the queue.

    Example:

    queuectl enqueue '{"id":"job1","command":"sleep 2"}'
    """

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        typer.secho(f"Invalid JSON: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if "command" not in data:
        typer.secho(
            "Missing required field: command",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    job = Job(
        id=data.get("id", str(uuid.uuid4())),
        command=data["command"],
        max_retries=data.get("max_retries", int(get_config("max_retries"))),
    )

    try:
        with Database() as db:
            db.add_job(job)
    except sqlite3.IntegrityError:
        typer.secho(
            f"Job '{job.id}' already exists.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.echo(f"Queued job: {job.id}")


@app.command()
def status():
    """Show queue status."""
    with Database() as db:
        counts = db.get_job_counts()
    
    total = sum(counts.values())

    typer.echo("Queue Status")
    typer.echo("------------")
    typer.echo(f"Pending:      {counts.get(JobState.PENDING.value, 0)}")
    typer.echo(f"Processing:   {counts.get(JobState.PROCESSING.value, 0)}")
    typer.echo(f"Completed:    {counts.get(JobState.COMPLETED.value, 0)}")
    typer.echo(f"Dead:         {counts.get(JobState.DEAD.value, 0)}")
    typer.echo("")
    typer.echo(f"Total Jobs:   {total}")


@app.command()
def list():
    """List jobs."""
    typer.echo("List - Coming soon")


if __name__ == "__main__":
    app()