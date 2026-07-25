import uuid
from datetime import timedelta
from unittest.mock import patch

from queuectl.db import Database
from queuectl.models import Job, JobState, utc_now
from queuectl.worker import process_one_job


def make_job(command="echo Hello", state=JobState.PENDING):
    return Job(
        id=str(uuid.uuid4()),
        command=command,
        state=state,
    )


def test_process_one_job_empty_queue(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        result = process_one_job(db)
        assert result is False


def test_process_one_job_success(tmp_path):
    db_path = tmp_path / "test.db"
    job = make_job()

    with Database(db_path) as db:
        db.add_job(job)

        with patch("queuectl.worker.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            
            result = process_one_job(db)
            
            assert result is True
            mock_run.assert_called_once_with(job.command, shell=True, capture_output=True, text=True)
            
            updated_job = db.get_job(job.id)
            assert updated_job.state == JobState.COMPLETED


def test_failed_job_is_requeued(tmp_path):
    db_path = tmp_path / "test.db"
    job = make_job()

    with Database(db_path) as db:
        db.add_job(job)

        with patch("queuectl.worker.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            
            result = process_one_job(db)
            
            assert result is True
            mock_run.assert_called_once_with(job.command, shell=True, capture_output=True, text=True)
            
            updated_job = db.get_job(job.id)
            assert updated_job.attempts == 1
            assert updated_job.state == JobState.PENDING
            assert updated_job.next_run_at > utc_now()


def test_failed_job_exhausts_retries(tmp_path):
    db_path = tmp_path / "test.db"
    job = make_job()
    job.attempts = 2
    job.max_retries = 3

    with Database(db_path) as db:
        db.add_job(job)

        with patch("queuectl.worker.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            
            result = process_one_job(db)
            
            assert result is True
            mock_run.assert_called_once_with(job.command, shell=True, capture_output=True, text=True)
            
            updated_job = db.get_job(job.id)
            assert updated_job.attempts == 3
            assert updated_job.state == JobState.DEAD


def test_failed_job_backoff_increases(tmp_path):
    db_path = tmp_path / "test.db"
    job = make_job()

    with Database(db_path) as db:
        db.add_job(job)

        with patch("queuectl.worker.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            
            # Failure 1
            process_one_job(db)
            updated_job = db.get_job(job.id)
            delay1 = (updated_job.next_run_at - utc_now()).total_seconds()
            assert delay1 >= 1.5
            
            # Make the job eligible to run again
            updated_job.next_run_at = utc_now() - timedelta(minutes=1)
            db.update_job(updated_job)

            # Failure 2
            process_one_job(db)
            updated_job = db.get_job(job.id)
            delay2 = (updated_job.next_run_at - utc_now()).total_seconds()
            assert delay2 >= 3.5


def test_future_jobs_are_not_claimed(tmp_path):
    db_path = tmp_path / "test.db"
    job = make_job()
    job.next_run_at = utc_now() + timedelta(minutes=1)
    job.state = JobState.PENDING

    with Database(db_path) as db:
        db.add_job(job)

        claimed = db.claim_next_job()
        assert claimed is None


def test_dead_job_is_not_claimed(tmp_path):
    db_path = tmp_path / "test.db"
    job = make_job()
    job.state = JobState.DEAD

    with Database(db_path) as db:
        db.add_job(job)

        claimed = db.claim_next_job()
        assert claimed is None

