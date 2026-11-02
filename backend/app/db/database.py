import sqlite3
from contextlib import contextmanager

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    architecture_json TEXT NOT NULL,
    files_json TEXT NOT NULL,
    fix_rounds INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, number)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    project_id TEXT,
    version INTEGER,
    kind TEXT NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    duration_seconds REAL NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    llm_calls INTEGER NOT NULL DEFAULT 0,
    wait_seconds REAL NOT NULL DEFAULT 0,
    fix_rounds INTEGER NOT NULL DEFAULT 0,
    steps_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def connect():
    """Open a short-lived connection; commit on success, roll back on error."""
    connection = sqlite3.connect(config.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _add_missing_columns(connection) -> None:
    """Upgrade databases created before projects had an owner."""
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(projects)")
    }
    if "user_id" not in columns:
        connection.execute("ALTER TABLE projects ADD COLUMN user_id TEXT")


def init_db() -> None:
    """Create the database file and tables if they don't exist yet."""
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with connect() as connection:
        connection.executescript(SCHEMA)
        _add_missing_columns(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id)"
        )