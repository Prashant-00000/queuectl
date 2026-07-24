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