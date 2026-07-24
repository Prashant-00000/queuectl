import uuid

from queuectl.db import Database
from queuectl.models import Job, JobState


def make_job(
    command="echo Hello",
    state=JobState.PENDING,
):
    return Job(
        id=str(uuid.uuid4()),
        command=command,
        state=state,
    )


def test_database_file_created(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path):
        pass

    assert db_path.exists()


def test_jobs_table_exists(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        cursor = db.conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name='jobs'
            """
        )

        assert cursor.fetchone() is not None


def test_create_tables_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        db.create_tables()
        db.create_tables()


def test_context_manager(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        assert db.conn is not None

    assert db.conn is None


def test_row_factory(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        cursor = db.conn.execute("SELECT 1")
        row = cursor.fetchone()

        assert row.keys() == ["1"]


def test_custom_database_path(tmp_path):
    db_path = tmp_path / "custom.db"

    with Database(db_path):
        pass

    assert db_path.exists()


def test_add_and_get_job(tmp_path):
    db_path = tmp_path / "test.db"

    job = make_job()

    with Database(db_path) as db:
        db.add_job(job)

        loaded = db.get_job(job.id)

        assert loaded is not None
        assert loaded.id == job.id
        assert loaded.command == job.command
        assert loaded.state == JobState.PENDING


def test_get_job_returns_none(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        assert db.get_job("does-not-exist") is None


def test_claim_next_job_returns_none_when_empty(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        assert db.claim_next_job() is None


def test_claim_next_job_claims_pending_job(tmp_path):
    db_path = tmp_path / "test.db"

    job = make_job()

    with Database(db_path) as db:
        db.add_job(job)

        claimed = db.claim_next_job()

        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.state == JobState.PROCESSING

        loaded = db.get_job(job.id)
        assert loaded.state == JobState.PROCESSING


def test_claim_next_job_skips_completed_jobs(tmp_path):
    db_path = tmp_path / "test.db"

    completed = make_job(state=JobState.COMPLETED)
    pending = make_job()

    with Database(db_path) as db:
        db.add_job(completed)
        db.add_job(pending)

        claimed = db.claim_next_job()

        assert claimed.id == pending.id


def test_update_job_persists_changes(tmp_path):
    db_path = tmp_path / "test.db"

    job = make_job()

    with Database(db_path) as db:
        db.add_job(job)

        job.state = JobState.COMPLETED
        job.attempts = 2

        db.update_job(job)

        updated = db.get_job(job.id)

        assert updated.state == JobState.COMPLETED
        assert updated.attempts == 2


def test_claim_next_job_atomic(tmp_path):
    db_path = tmp_path / "test.db"

    job = make_job()

    db1 = Database(db_path)
    db2 = Database(db_path)

    db1.connect()
    db1.create_tables()

    db2.connect()
    db2.create_tables()

    db1.add_job(job)

    claimed1 = db1.claim_next_job()
    claimed2 = db2.claim_next_job()

    assert (claimed1 is None) != (claimed2 is None)

    db1.close()
    db2.close()