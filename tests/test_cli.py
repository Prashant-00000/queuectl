import json
import uuid

from typer.testing import CliRunner

from queuectl.cli import app
from queuectl.config import set_config
from queuectl.db import Database
from queuectl.models import Job, JobState


def test_enqueue_persists_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    payload = json.dumps({"id": "job1", "command": "echo Hello"})

    result = runner.invoke(app, ["enqueue", payload])

    assert result.exit_code == 0
    assert "Queued job: job1" in result.output

    with Database(tmp_path / "queue.db") as db:
        row = db.conn.execute(
            "SELECT * FROM jobs WHERE id=?",
            ("job1",),
        ).fetchone()

    assert row is not None
    assert row["id"] == "job1"
    assert row["command"] == "echo Hello"


def test_enqueue_generates_uuid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    payload = json.dumps({"command": "echo Hello"})

    result = runner.invoke(app, ["enqueue", payload])

    assert result.exit_code == 0

    queued_line = next(
        line for line in result.output.splitlines() if line.startswith("Queued job: ")
    )
    job_id = queued_line.removeprefix("Queued job: ").strip()

    uuid.UUID(job_id)

    with Database(tmp_path / "queue.db") as db:
        row = db.conn.execute(
            "SELECT * FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()

    assert row is not None
    assert row["command"] == "echo Hello"


def test_invalid_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()

    result = runner.invoke(app, ["enqueue", '{"command": "echo Hello"'])

    assert result.exit_code == 1
    assert "Invalid JSON:" in result.output


def test_missing_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    payload = json.dumps({"id": "job1"})

    result = runner.invoke(app, ["enqueue", payload])

    assert result.exit_code == 1
    assert "Missing required field: command" in result.output


def test_enqueue_respects_max_retries_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_config("max_retries", "5")
    
    runner = CliRunner()
    payload = json.dumps({"command": "echo Hello"})
    result = runner.invoke(app, ["enqueue", payload])
    
    assert result.exit_code == 0
    
    queued_line = next(line for line in result.output.splitlines() if line.startswith("Queued job: "))
    job_id = queued_line.removeprefix("Queued job: ").strip()
    
    with Database(tmp_path / "queue.db") as db:
        job = db.get_job(job_id)
        assert job.max_retries == 5


def test_dlq_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = Job(id="dead-job-1", command="echo hello", state=JobState.DEAD)
    with Database(tmp_path / "queue.db") as db:
        db.add_job(job)
    
    runner = CliRunner()
    result = runner.invoke(app, ["dlq", "list"])
    assert result.exit_code == 0
    assert "dead-job-1" in result.output


def test_dlq_retry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = Job(id="dead-job-2", command="echo hello", state=JobState.DEAD, attempts=3)
    with Database(tmp_path / "queue.db") as db:
        db.add_job(job)
    
    runner = CliRunner()
    result = runner.invoke(app, ["dlq", "retry", "dead-job-2"])
    assert result.exit_code == 0
    assert "Requeued dead-job-2" in result.output
    
    with Database(tmp_path / "queue.db") as db:
        updated = db.get_job("dead-job-2")
        assert updated.state == JobState.PENDING
        assert updated.attempts == 0


def test_dlq_retry_non_dead_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = Job(id="pending-job", command="echo hello", state=JobState.PENDING)
    with Database(tmp_path / "queue.db") as db:
        db.add_job(job)
    
    runner = CliRunner()
    result = runner.invoke(app, ["dlq", "retry", "pending-job"])
    assert result.exit_code == 1
    assert "Job is not in the Dead Letter Queue." in result.output


def test_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jobs = [
        Job(id="job-1", command="echo hello", state=JobState.PENDING),
        Job(id="job-2", command="echo hello", state=JobState.COMPLETED),
        Job(id="job-3", command="echo hello", state=JobState.DEAD),
    ]
    with Database(tmp_path / "queue.db") as db:
        for job in jobs:
            db.add_job(job)
    
    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Pending:      1" in result.output
    assert "Completed:    1" in result.output
    assert "Dead:         1" in result.output
    assert "Total Jobs:   3" in result.output


def test_list_jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jobs = [
        Job(id="job-1", command="echo hello", state=JobState.PENDING),
        Job(id="job-2", command="echo hello", state=JobState.COMPLETED),
    ]
    with Database(tmp_path / "queue.db") as db:
        for job in jobs:
            db.add_job(job)
    
    runner = CliRunner()
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "job-1" in result.output
    assert "job-2" in result.output


def test_list_jobs_filtered(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    jobs = [
        Job(id="job-1", command="echo hello", state=JobState.PENDING),
        Job(id="job-2", command="echo hello", state=JobState.COMPLETED),
    ]
    with Database(tmp_path / "queue.db") as db:
        for job in jobs:
            db.add_job(job)
    
    runner = CliRunner()
    result = runner.invoke(app, ["list", "--state", "pending"])
    assert result.exit_code == 0
    assert "job-1" in result.output
    assert "job-2" not in result.output


def test_enqueue_not_dict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    
    result = runner.invoke(app, ["enqueue", '"just a string"'])
    assert result.exit_code == 1
    assert "Payload must be a JSON object" in result.output


def test_worker_start_count(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    
    class MockProcess:
        start_count = 0
        join_count = 0
        
        def __init__(self, target):
            self.target = target
            
        def start(self):
            MockProcess.start_count += 1
            
        def join(self, timeout=None):
            MockProcess.join_count += 1
            
        def is_alive(self):
            return False

    monkeypatch.setattr("queuectl.cli.multiprocessing.Process", MockProcess)
    
    result = runner.invoke(app, ["worker", "start", "--count", "3"])
    assert result.exit_code == 0
    
    assert MockProcess.start_count == 3
    assert MockProcess.join_count == 3
