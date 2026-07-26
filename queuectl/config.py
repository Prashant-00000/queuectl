import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = "queue.db"
BACKOFF_MAX_SECONDS = 60
WORKER_POLL_INTERVAL = 1

def get_connection(db_path: str):
    conn = sqlite3.connect(Path(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

def get_config(key: str, db_path: str = DEFAULT_DB_PATH) -> str:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown config key: {key}")
        return row["value"]
    except sqlite3.OperationalError:
        # If the table doesn't exist yet, return defaults
        defaults = {"max_retries": "3", "backoff_base": "2"}
        if key in defaults:
            return defaults[key]
        raise KeyError(f"Unknown config key: {key}")
    finally:
        conn.close()

def set_config(key: str, value: str, db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    try:
        # Ensure the table exists before attempting to set a config value
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        conn.commit()
    finally:
        conn.close()
