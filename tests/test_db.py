import sqlite3

from queuectl.models import Job

from queuectl.db import Database


def test_database_file_is_created(tmp_path):
    db_path = tmp_path / "test.db"

    db = Database(db_path)
    db.connect()

    assert db_path.exists()

    db.close()


def test_jobs_table_is_created(tmp_path):
    db_path = tmp_path / "test.db"

    db = Database(db_path)
    db.connect()
    db.create_tables()

    cursor = db.conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name='jobs'
    """)

    assert cursor.fetchone() is not None

    db.close()


def test_create_tables_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"

    db = Database(db_path)
    db.connect()

    db.create_tables()
    db.create_tables()
    db.create_tables()

    db.close()


def test_database_context_manager(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        assert db.conn is not None

    assert db.conn is None


def test_row_factory_returns_named_columns(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        cursor = db.conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name='jobs'
        """)

        row = cursor.fetchone()

        assert row["name"] == "jobs"


def test_database_uses_custom_path(tmp_path):
    db_path = tmp_path / "custom.db"

    with Database(db_path):
        pass

    assert db_path.exists()


def test_add_job(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        job = Job(
            id="job1",
            command="echo Hello",
        )

        db.add_job(job)

        row = db.conn.execute(
            "SELECT * FROM jobs WHERE id=?",
            ("job1",)
        ).fetchone()

        assert row is not None
        assert row["id"] == "job1"
        assert row["command"] == "echo Hello"
        assert row["state"] == "pending"


def test_add_job_duplicate_id(tmp_path):
    db_path = tmp_path / "test.db"

    with Database(db_path) as db:
        job = Job(id="job1", command="echo Hello")

        db.add_job(job)

        try:
            db.add_job(job)
            assert False, "Expected sqlite3.IntegrityError"
        except sqlite3.IntegrityError:
            pass