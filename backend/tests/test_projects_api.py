import pytest
from fastapi.testclient import TestClient

from app.db import repository
from app.main import app
from app.schemas.architecture import Architecture
from tests.test_graph import make_plan_object
from tests.test_validator import contract_data, good_files_dict
from tests.constants import TEST_USER

client = TestClient(app)


def create_project():
    project_id, _ = repository.save_new_project(
        "a calculator",
        make_plan_object(),
        Architecture.model_validate(contract_data()),
        good_files_dict(),
        0,
        user_id=TEST_USER["id"],
    )
    return project_id


def test_no_projects_at_first():
    assert client.get("/api/projects").json() == []


def test_created_project_is_listed():
    project_id = create_project()

    projects = client.get("/api/projects").json()

    assert projects[0]["id"] == project_id
    assert projects[0]["title"] == "Calc"
    assert projects[0]["latest_version"] == 1


def test_project_detail_lists_versions():
    project_id = create_project()

    project = client.get(f"/api/projects/{project_id}").json()

    assert project["versions"][0]["number"] == 1
    assert project["versions"][0]["prompt"] == "a calculator"


def test_version_detail_includes_files():
    project_id = create_project()

    version = client.get(f"/api/projects/{project_id}/versions/1").json()

    assert version["files"] == good_files_dict()
    assert version["plan"]["app_name"] == "Calc"


@pytest.mark.parametrize(
    "path",
    [
        "/api/projects/000000000000",
        "/api/projects/not-a-valid-id",
        "/api/projects/000000000000/versions/1",
    ],
)
def test_unknown_projects_return_404(path):
    assert client.get(path).status_code == 404


def test_unknown_version_returns_404():
    project_id = create_project()

    assert client.get(f"/api/projects/{project_id}/versions/99").status_code == 404
    assert client.get(f"/api/projects/{project_id}/versions/0").status_code == 404


@pytest.mark.parametrize(
    "filename, media_type",
    [
        ("index.html", "text/html"),
        ("style.css", "text/css"),
        ("script.js", "text/javascript"),
    ],
)
def test_files_are_served_with_the_right_type_and_safety_headers(filename, media_type):
    project_id = create_project()

    response = client.get(f"/api/projects/{project_id}/versions/1/files/{filename}")

    assert response.status_code == 200
    assert response.text == good_files_dict()[filename]
    assert response.headers["content-type"].startswith(media_type)
    assert "connect-src 'none'" in response.headers["content-security-policy"]


def test_unknown_filename_returns_404():
    project_id = create_project()

    response = client.get(f"/api/projects/{project_id}/versions/1/files/secret.txt")

    assert response.status_code == 404


def test_runs_endpoint_lists_a_projects_runs():
    project_id = create_project()
    repository.save_run(
        user_id=TEST_USER["id"], project_id=project_id, version=1, kind="build",
        prompt="a calculator", status="passed", error=None, fix_rounds=0,
        summary={
            "duration_seconds": 5.0, "prompt_tokens": 10, "completion_tokens": 5,
            "llm_calls": 1, "wait_seconds": 0.0, "steps": [],
        },
    )

    runs = client.get(f"/api/projects/{project_id}/runs").json()

    assert runs[0]["kind"] == "build"
    assert runs[0]["prompt_tokens"] == 10