import json
import sqlite3
import uuid

import typer

from queuectl.config import get_config, set_config
from queuectl.db import Database
from queuectl.models import Job
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


@worker_app.command("start")
def start_worker():
    """Start the worker."""
    with Database() as db:
        run_worker(db)


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
    typer.echo("Status - Coming soon")


@app.command()
def list():
    """List jobs."""
    typer.echo("List - Coming soon")


if __name__ == "__main__":
    app()