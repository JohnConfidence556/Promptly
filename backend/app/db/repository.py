import json
import uuid

from app.db.database import connect
from app.schemas.architecture import Architecture
from app.schemas.plan import Plan
import hashlib
import secrets


def _insert_version(
    connection,
    project_id: str,
    number: int,
    prompt: str,
    plan: Plan,
    architecture: Architecture,
    files: dict[str, str],
    fix_rounds: int,
) -> None:
    connection.execute(
        """
        INSERT INTO versions
            (project_id, number, prompt, plan_json, architecture_json,
             files_json, fix_rounds)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            number,
            prompt,
            plan.model_dump_json(),
            architecture.model_dump_json(),
            json.dumps(files),
            fix_rounds,
        ),
    )


def save_new_project(
    prompt: str,
    plan: Plan,
    architecture: Architecture,
    files: dict[str, str],
    fix_rounds: int,
    user_id: str | None = None,
) -> tuple[str, int]:
    """Create a project with version 1. Returns (project_id, version_number)."""
    project_id = uuid.uuid4().hex[:12]

    with connect() as connection:
        connection.execute(
            "INSERT INTO projects (id, user_id, title) VALUES (?, ?, ?)",
            (project_id, user_id, plan.app_name),
        )
        _insert_version(
            connection, project_id, 1, prompt, plan, architecture, files, fix_rounds
        )

    return project_id, 1


def add_version(
    project_id: str,
    prompt: str,
    plan: Plan,
    architecture: Architecture,
    files: dict[str, str],
    fix_rounds: int,
) -> int | None:
    """Add the next version. Returns its number, or None if the project is unknown."""
    with connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if exists is None:
            return None

        row = connection.execute(
            "SELECT COALESCE(MAX(number), 0) AS latest FROM versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        number = row["latest"] + 1

        _insert_version(
            connection, project_id, number, prompt, plan, architecture, files, fix_rounds
        )

    return number


def list_projects() -> list[dict]:
    """All projects, newest first, with their latest version number."""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT p.id, p.title, p.created_at, MAX(v.number) AS latest_version
            FROM projects p
            JOIN versions v ON v.project_id = p.id
            GROUP BY p.id
            ORDER BY p.rowid DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_project(project_id: str) -> dict | None:
    """One project with a summary of each version, or None if unknown."""
    with connect() as connection:
        project = connection.execute(
            "SELECT id, title, created_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if project is None:
            return None

        versions = connection.execute(
            """
            SELECT number, prompt, fix_rounds, created_at
            FROM versions WHERE project_id = ? ORDER BY number
            """,
            (project_id,),
        ).fetchall()

    return {**dict(project), "versions": [dict(row) for row in versions]}


def get_version(project_id: str, number: int) -> dict | None:
    """One version with its files, plan and architecture, or None if unknown."""
    with connect() as connection:
        row = connection.execute(
            """
            SELECT number, prompt, plan_json, architecture_json, files_json,
                   fix_rounds, created_at
            FROM versions WHERE project_id = ? AND number = ?
            """,
            (project_id, number),
        ).fetchone()

    if row is None:
        return None

    return {
        "number": row["number"],
        "prompt": row["prompt"],
        "fix_rounds": row["fix_rounds"],
        "created_at": row["created_at"],
        "plan": json.loads(row["plan_json"]),
        "architecture": json.loads(row["architecture_json"]),
        "files": json.loads(row["files_json"]),
    }


def _hash_token(token: str) -> str:
    # Tokens are long and random, so a plain SHA-256 is enough to store them safely.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user(name: str, email: str) -> tuple[dict, str]:
    """Create a user. Returns (user, secret_token). The token is never stored."""
    user_id = uuid.uuid4().hex[:12]
    token = secrets.token_urlsafe(32)

    with connect() as connection:
        connection.execute(
            "INSERT INTO users (id, name, email, token_hash) VALUES (?, ?, ?, ?)",
            (user_id, name, email, _hash_token(token)),
        )

    return {"id": user_id, "name": name, "email": email}, token


def get_user_by_token(token: str) -> dict | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT id, name, email FROM users WHERE token_hash = ?",
            (_hash_token(token),),
        ).fetchone()

    return dict(row) if row else None


def get_project_owner(project_id: str) -> str | None:
    """The owner's user id, or None if the project is unknown or has no owner."""
    with connect() as connection:
        row = connection.execute(
            "SELECT user_id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    return row["user_id"] if row else None


def list_projects_for_user(user_id: str) -> list[dict]:
    """A user's projects, newest first."""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT p.id, p.title, p.created_at,
                   MAX(v.number) AS latest_version,
                   MAX(v.created_at) AS updated_at
            FROM projects p
            JOIN versions v ON v.project_id = p.id
            WHERE p.user_id = ?
            GROUP BY p.id
            ORDER BY p.rowid DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def copy_version(project_id: str, source_number: int) -> int | None:
    """Restore a version by copying it as the newest one. Returns the new number."""
    with connect() as connection:
        source = connection.execute(
            "SELECT 1 FROM versions WHERE project_id = ? AND number = ?",
            (project_id, source_number),
        ).fetchone()
        if source is None:
            return None

        row = connection.execute(
            "SELECT COALESCE(MAX(number), 0) AS latest FROM versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        number = row["latest"] + 1

        connection.execute(
            """
            INSERT INTO versions
                (project_id, number, prompt, plan_json, architecture_json,
                 files_json, fix_rounds)
            SELECT project_id, ?, ?, plan_json, architecture_json, files_json, 0
            FROM versions WHERE project_id = ? AND number = ?
            """,
            (number, f"Restored version {source_number}", project_id, source_number),
        )

    return number


def delete_project(project_id: str) -> bool:
    """Delete a project, its versions (by cascade) and its run log."""
    with connect() as connection:
        connection.execute("DELETE FROM runs WHERE project_id = ?", (project_id,))
        cursor = connection.execute(
            "DELETE FROM projects WHERE id = ?", (project_id,)
        )
        return cursor.rowcount > 0


def save_run(
    *,
    user_id: str | None,
    project_id: str | None,
    version: int | None,
    kind: str,
    prompt: str,
    status: str,
    error: str | None,
    fix_rounds: int,
    summary: dict,
) -> None:
    """Record one build or edit. Failed builds have no project yet."""
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO runs
                (user_id, project_id, version, kind, prompt, status, error,
                 duration_seconds, prompt_tokens, completion_tokens, llm_calls,
                 wait_seconds, fix_rounds, steps_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                project_id,
                version,
                kind,
                prompt,
                status,
                error,
                summary["duration_seconds"],
                summary["prompt_tokens"],
                summary["completion_tokens"],
                summary["llm_calls"],
                summary["wait_seconds"],
                fix_rounds,
                json.dumps(summary["steps"]),
            ),
        )


def list_runs(project_id: str) -> list[dict]:
    """A project's runs, newest first."""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, version, kind, prompt, status, error, duration_seconds,
                   prompt_tokens, completion_tokens, llm_calls, wait_seconds,
                   fix_rounds, steps_json, created_at
            FROM runs WHERE project_id = ? ORDER BY id DESC
            """,
            (project_id,),
        ).fetchall()

    runs = []
    for row in rows:
        run = dict(row)
        run["steps"] = json.loads(run.pop("steps_json"))
        runs.append(run)

    return runs


def count_runs_since(hours: int, user_id: str | None = None) -> int:
    """How many builds and edits ran in the last `hours` hours (all users, or one)."""
    query = "SELECT COUNT(*) AS total FROM runs WHERE created_at >= datetime('now', ?)"
    params: list = [f"-{int(hours)} hours"]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    with connect() as connection:
        return connection.execute(query, params).fetchone()["total"]