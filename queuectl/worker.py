import subprocess
import time
import typer

from queuectl.db import Database
from queuectl.models import JobState


def process_one_job(db: Database) -> bool:
    """
    Claims a single job, executes it, updates its state, and returns True.
    If no job is available, returns False.
    """
    job = db.claim_next_job()

    if job is None:
        return False

    result = subprocess.run(
        job.command,
        shell=True,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        job.state = JobState.COMPLETED
    else:
        job.state = JobState.FAILED

    db.update_job(job)

    return True


def run_worker(db):
    """
    Continuously process jobs until interrupted.
    """
    try:
        while True:
            processed = process_one_job(db)

            if not processed:
                time.sleep(1)

    except KeyboardInterrupt:
        typer.echo("\nWorker stopped.")
