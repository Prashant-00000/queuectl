import json
import uuid

from typer.testing import CliRunner

from queuectl.cli import app
from queuectl.config import set_config
from queuectl.db import Database


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