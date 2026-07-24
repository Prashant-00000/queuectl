import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: str = "queue.db"):
        self.db_path = Path(db_path)
        self.conn = None

    def connect(self):
        if self.conn is not None:
            return

        self.conn = sqlite3.connect(self.db_path)

        self.conn.row_factory = sqlite3.Row

        self.conn.execute("PRAGMA journal_mode=WAL;")

        self.conn.execute("PRAGMA busy_timeout=5000;")

    def create_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                max_retries INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                next_run_at TEXT NOT NULL
            )
            """
        )

        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.connect()
        self.create_tables()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()