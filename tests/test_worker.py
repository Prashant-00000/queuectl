import uuid
from unittest.mock import patch

from queuectl.db import Database
from queuectl.models import Job, JobState
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


def test_process_one_job_failure(tmp_path):
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
            assert updated_job.state == JobState.FAILED
