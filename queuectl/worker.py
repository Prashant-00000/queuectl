from datetime import timedelta
import subprocess
import time
import typer

from queuectl.db import Database
from queuectl.models import JobState, utc_now
from queuectl.config import get_config, BACKOFF_MAX_SECONDS


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
        job.attempts += 1

        if job.attempts < job.max_retries:
            backoff_base = int(get_config("backoff_base"))
            delay_seconds = min(
                backoff_base ** job.attempts,
                BACKOFF_MAX_SECONDS,
            )
            job.next_run_at = utc_now() + timedelta(seconds=delay_seconds)
            job.state = JobState.PENDING
        else:
            job.state = JobState.DEAD

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
