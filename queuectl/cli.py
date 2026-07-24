import json
import sqlite3
import uuid

import typer

from queuectl.db import Database
from queuectl.models import Job

app = typer.Typer(
    help="QueueCTL - A command-line background job queue."
)

worker_app = typer.Typer(help="Manage workers.")
app.add_typer(worker_app, name="worker")


@worker_app.command("start")
def start_worker():
    """Start worker(s)."""
    typer.echo("Worker start - Coming soon")


@worker_app.command("stop")
def stop_worker():
    """Stop worker(s)."""
    typer.echo("Worker stop - Coming soon")


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
        max_retries=data.get("max_retries", 3),
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
    typer.echo("Status - Coming soon")


@app.command()
def list():
    """List jobs."""
    typer.echo("List - Coming soon")


if __name__ == "__main__":
    app()