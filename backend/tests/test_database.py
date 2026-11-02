import sqlite3

from app import config
from app.db.database import init_db


def test_init_db_adds_the_owner_column_to_an_old_projects_table(monkeypatch, tmp_path):
    old_db = tmp_path / "old.db"
    connection = sqlite3.connect(old_db)
    connection.execute(
        "CREATE TABLE projects (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(config, "DATABASE_PATH", old_db)
    init_db()

    connection = sqlite3.connect(old_db)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    connection.close()

    assert "user_id" in columns