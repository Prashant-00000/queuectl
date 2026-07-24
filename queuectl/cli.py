import typer

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
def enqueue():
    """Add a job to the queue."""
    typer.echo("Enqueue - Coming soon")


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