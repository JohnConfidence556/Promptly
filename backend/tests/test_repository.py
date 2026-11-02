from app.db import repository
from app.schemas.architecture import Architecture
from tests.test_graph import make_plan_object
from tests.test_validator import contract_data, good_files_dict
from app.db.database import connect


def architecture():
    return Architecture.model_validate(contract_data())


def save_project(prompt="a calculator"):
    return repository.save_new_project(
        prompt, make_plan_object(), architecture(), good_files_dict(), 1
    )


def test_saved_project_round_trips():
    project_id, number = save_project()

    version = repository.get_version(project_id, number)

    assert number == 1
    assert version["files"] == good_files_dict()
    assert version["prompt"] == "a calculator"
    assert version["fix_rounds"] == 1
    assert version["plan"]["app_name"] == "Calc"
    assert version["architecture"]["element_ids"][0]["name"] == "display"


def test_add_version_increments_the_number():
    project_id, _ = save_project()

    number = repository.add_version(
        project_id, "make it blue", make_plan_object(), architecture(), good_files_dict(), 0
    )

    assert number == 2
    assert repository.get_version(project_id, 2)["prompt"] == "make it blue"
    assert repository.get_version(project_id, 1)["prompt"] == "a calculator"


def test_add_version_to_unknown_project_returns_none():
    result = repository.add_version(
        "000000000000", "x", make_plan_object(), architecture(), good_files_dict(), 0
    )

    assert result is None


def test_projects_are_listed_newest_first():
    first, _ = save_project("first")
    second, _ = save_project("second")

    projects = repository.list_projects()

    assert [project["id"] for project in projects] == [second, first]
    assert projects[0]["latest_version"] == 1


def test_project_lists_its_versions_in_order():
    project_id, _ = save_project()
    repository.add_version(
        project_id, "again", make_plan_object(), architecture(), good_files_dict(), 0
    )

    project = repository.get_project(project_id)

    assert project["title"] == "Calc"
    assert [version["number"] for version in project["versions"]] == [1, 2]


def test_unknown_lookups_return_none():
    assert repository.get_project("000000000000") is None
    assert repository.get_version("000000000000", 1) is None

def test_users_are_created_and_found_by_token():
    user, token = repository.create_user("Ada", "ada@example.com")

    assert repository.get_user_by_token(token) == user
    assert repository.get_user_by_token("wrong") is None


def test_projects_are_listed_per_user():
    ada, _ = repository.create_user("Ada", "ada@example.com")
    bob, _ = repository.create_user("Bob", "bob@example.com")
    mine, _ = repository.save_new_project(
        "a", make_plan_object(), architecture(), good_files_dict(), 0, user_id=ada["id"]
    )
    repository.save_new_project(
        "b", make_plan_object(), architecture(), good_files_dict(), 0, user_id=bob["id"]
    )

    listed = repository.list_projects_for_user(ada["id"])

    assert [project["id"] for project in listed] == [mine]
    assert listed[0]["updated_at"]
    assert repository.get_project_owner(mine) == ada["id"]


def test_copy_version_creates_the_next_version():
    project_id, _ = save_project()
    repository.add_version(
        project_id,
        "edit",
        make_plan_object(),
        architecture(),
        {"index.html": "x", "style.css": "y", "script.js": "z"},
        0,
    )

    number = repository.copy_version(project_id, 1)

    assert number == 3
    restored = repository.get_version(project_id, 3)
    assert restored["files"] == good_files_dict()
    assert restored["prompt"] == "Restored version 1"


def test_copying_an_unknown_version_returns_none():
    project_id, _ = save_project()

    assert repository.copy_version(project_id, 9) is None


def test_deleting_a_project_removes_its_versions():
    project_id, _ = save_project()

    assert repository.delete_project(project_id) is True
    assert repository.get_project(project_id) is None
    assert repository.get_version(project_id, 1) is None
    assert repository.delete_project(project_id) is False


def run_summary():
    return {
        "duration_seconds": 12.5,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "llm_calls": 3,
        "wait_seconds": 4.0,
        "steps": [{"step": "planner", "seconds": 2.0}],
    }


def test_runs_are_saved_and_listed_newest_first():
    project_id, _ = save_project()
    repository.save_run(
        user_id="u1", project_id=project_id, version=1, kind="build",
        prompt="a calculator", status="passed", error=None, fix_rounds=0,
        summary=run_summary(),
    )
    repository.save_run(
        user_id="u1", project_id=project_id, version=2, kind="edit",
        prompt="make it green", status="passed", error=None, fix_rounds=1,
        summary=run_summary(),
    )

    runs = repository.list_runs(project_id)

    assert [run["kind"] for run in runs] == ["edit", "build"]
    assert runs[0]["fix_rounds"] == 1
    assert runs[1]["steps"] == [{"step": "planner", "seconds": 2.0}]
    assert runs[1]["prompt_tokens"] == 100


def test_a_failed_build_can_be_recorded_without_a_project():
    repository.save_run(
        user_id="u1", project_id=None, version=None, kind="build",
        prompt="a calculator", status="failed", error="boom", fix_rounds=2,
        summary=run_summary(),
    )


def test_deleting_a_project_removes_its_runs():
    project_id, _ = save_project()
    repository.save_run(
        user_id="u1", project_id=project_id, version=1, kind="build",
        prompt="a calculator", status="passed", error=None, fix_rounds=0,
        summary=run_summary(),
    )

    repository.delete_project(project_id)

    assert repository.list_runs(project_id) == []


def test_runs_are_counted_per_user_and_by_time_window():
    project_id, _ = save_project()
    for user_id in ("u1", "u1", "u2"):
        repository.save_run(
            user_id=user_id, project_id=project_id, version=1, kind="build",
            prompt="x", status="passed", error=None, fix_rounds=0,
            summary=run_summary(),
        )

    assert repository.count_runs_since(24) == 3
    assert repository.count_runs_since(24, user_id="u1") == 2

    with connect() as connection:
        connection.execute("UPDATE runs SET created_at = datetime('now', '-2 days')")

    assert repository.count_runs_since(24) == 0