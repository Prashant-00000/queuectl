import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from queuectl.models import Job, JobState, utc_now


class Database:
    def __init__(self, db_path: str = "queue.db"):
        self.db_path = Path(db_path)
        self.conn = None

    def connect(self):
        """Open a database connection if one is not already open."""
        if self.conn is not None:
            return

        self.conn = sqlite3.connect(
            self.db_path,
            timeout=5,
        )

        self.conn.row_factory = sqlite3.Row

        # Better concurrent read/write behavior.
        self.conn.execute("PRAGMA journal_mode=WAL;")

        # Wait up to 5 seconds if another writer holds the database lock.
        self.conn.execute("PRAGMA busy_timeout=5000;")

    def create_tables(self):
        """Create database tables and indexes."""
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

        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_state_next_run
            ON jobs(state, next_run_at)
            """
        )

        self.conn.commit()

    def _row_to_job(self, row) -> Optional[Job]:
        """Convert a SQLite row into a Job object."""
        if row is None:
            return None

        return Job(
            id=row["id"],
            command=row["command"],
            state=JobState(row["state"]),
            attempts=row["attempts"],
            max_retries=row["max_retries"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            next_run_at=datetime.fromisoformat(row["next_run_at"]),
        )

    def add_job(self, job: Job):
        """Insert a new job into the queue."""
        self.conn.execute(
            """
            INSERT INTO jobs (
                id,
                command,
                state,
                attempts,
                max_retries,
                created_at,
                updated_at,
                next_run_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.command,
                job.state.value,
                job.attempts,
                job.max_retries,
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
                job.next_run_at.isoformat(),
            ),
        )

        self.conn.commit()

    def get_job(self, job_id: str) -> Optional[Job]:
        """Fetch a job by its ID."""
        cursor = self.conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        )

        return self._row_to_job(cursor.fetchone())

    def claim_next_job(self) -> Optional[Job]:
        """
        Atomically claim the next available job.

        The job state is changed from PENDING to PROCESSING in the same
        SQL statement, preventing multiple workers from claiming the
        same job.
        """
        now = utc_now().isoformat()

        cursor = self.conn.execute(
            """
            UPDATE jobs
            SET
                state = ?,
                updated_at = ?
            WHERE id = (
                SELECT id
                FROM jobs
                WHERE state = ?
                  AND next_run_at <= ?
                ORDER BY next_run_at ASC, created_at ASC
                LIMIT 1
            )
            RETURNING *
            """,
            (
                JobState.PROCESSING.value,
                now,
                JobState.PENDING.value,
                now,
            ),
        )

        row = cursor.fetchone()
        self.conn.commit()

        return self._row_to_job(row)

    def update_job(self, job: Job):
        """
        Persist changes made to an existing job.

        The database layer owns the updated_at timestamp so callers
        cannot accidentally forget to refresh it.
        """
        job.updated_at = utc_now()

        self.conn.execute(
            """
            UPDATE jobs
            SET
                command = ?,
                state = ?,
                attempts = ?,
                max_retries = ?,
                updated_at = ?,
                next_run_at = ?
            WHERE id = ?
            """,
            (
                job.command,
                job.state.value,
                job.attempts,
                job.max_retries,
                job.updated_at.isoformat(),
                job.next_run_at.isoformat(),
                job.id,
            ),
        )

        self.conn.commit()

    def list_jobs(self, state: Optional[JobState] = None) -> list[Job]:
        """Fetch a list of jobs, optionally filtered by state."""
        query = "SELECT * FROM jobs"
        params = []
        if state:
            query += " WHERE state = ?"
            params.append(state.value)
        query += " ORDER BY created_at ASC"

        cursor = self.conn.execute(query, params)
        return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_job_counts(self) -> dict[str, int]:
        """Return the count of jobs for each state."""
        cursor = self.conn.execute("SELECT state, COUNT(*) as count FROM jobs GROUP BY state")
        return {row["state"]: row["count"] for row in cursor.fetchall()}

    def close(self):
        """Close the database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.connect()
        self.create_tables()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()