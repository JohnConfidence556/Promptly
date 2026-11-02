import pytest
from fastapi.testclient import TestClient

from app.db import repository
from app.db.database import connect
from app.main import app
from app.schemas.architecture import Architecture
from tests.test_graph import make_plan_object
from tests.test_validator import contract_data, good_files_dict

client = TestClient(app)


@pytest.fixture(autouse=True)
def real_auth(signed_in_user):
    app.dependency_overrides.clear()


def make_user(name="Ada"):
    user, token = repository.create_user(name, f"{name.lower()}@example.com")
    return user, {"Authorization": f"Bearer {token}"}


def make_project_for(user):
    project_id, _ = repository.save_new_project(
        "a calculator",
        make_plan_object(),
        Architecture.model_validate(contract_data()),
        good_files_dict(),
        0,
        user_id=user["id"],
    )
    return project_id


def test_sign_up_returns_a_user_and_a_token():
    response = client.post(
        "/api/users", json={"name": " Ada ", "email": "Ada@Example.com"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["name"] == "Ada"
    assert body["user"]["email"] == "ada@example.com"
    assert len(body["token"]) >= 32


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "email": "a@b.co"},
        {"name": "Ada", "email": "not-an-email"},
        {"name": "Ada"},
        {"email": "a@b.co"},
    ],
)
def test_invalid_sign_ups_are_rejected(body):
    assert client.post("/api/users", json=body).status_code == 422


def test_token_is_not_stored_in_plain_text():
    token = client.post(
        "/api/users", json={"name": "Ada", "email": "ada@example.com"}
    ).json()["token"]

    with connect() as connection:
        stored = [row["token_hash"] for row in connection.execute("SELECT token_hash FROM users")]

    assert len(stored) == 1
    assert token not in stored


def test_me_returns_the_signed_in_user():
    user, headers = make_user()

    assert client.get("/api/me", headers=headers).json() == user


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong"},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer"},
    ],
)
def test_missing_or_bad_credentials_are_rejected(headers):
    assert client.get("/api/me", headers=headers).status_code == 401


def test_users_only_see_their_own_projects():
    ada, ada_headers = make_user("Ada")
    _, bob_headers = make_user("Bob")
    project_id = make_project_for(ada)

    mine = client.get("/api/projects", headers=ada_headers).json()
    theirs = client.get("/api/projects", headers=bob_headers).json()

    assert [project["id"] for project in mine] == [project_id]
    assert theirs == []


def test_other_users_cannot_read_edit_restore_or_delete():
    ada, _ = make_user("Ada")
    _, bob_headers = make_user("Bob")
    project_id = make_project_for(ada)

    for method, path in [
        ("get", f"/api/projects/{project_id}"),
        ("get", f"/api/projects/{project_id}/versions/1"),
        ("post", f"/api/projects/{project_id}/versions/1/restore"),
        ("delete", f"/api/projects/{project_id}"),
        ("get", f"/api/projects/{project_id}/runs"),
    ]:
        assert client.request(method, path, headers=bob_headers).status_code == 404

    edit = client.post(
        f"/api/projects/{project_id}/edits/stream",
        json={"prompt": "make it green"},
        headers=bob_headers,
    )
    assert edit.status_code == 404
    assert repository.get_project(project_id) is not None


def test_restore_creates_a_new_version():
    ada, headers = make_user()
    project_id = make_project_for(ada)

    response = client.post(
        f"/api/projects/{project_id}/versions/1/restore", headers=headers
    )

    assert response.json() == {"project_id": project_id, "version": 2}
    restored = repository.get_version(project_id, 2)
    assert restored["files"] == good_files_dict()
    assert restored["prompt"] == "Restored version 1"


def test_restoring_an_unknown_version_returns_404():
    ada, headers = make_user()
    project_id = make_project_for(ada)

    response = client.post(
        f"/api/projects/{project_id}/versions/9/restore", headers=headers
    )

    assert response.status_code == 404


def test_delete_removes_the_project():
    ada, headers = make_user()
    project_id = make_project_for(ada)

    assert client.delete(f"/api/projects/{project_id}", headers=headers).status_code == 204
    assert client.get(f"/api/projects/{project_id}", headers=headers).status_code == 404
    assert client.get("/api/projects", headers=headers).json() == []


def test_projects_without_an_owner_are_hidden():
    _, headers = make_user()
    legacy_id, _ = repository.save_new_project(
        "old",
        make_plan_object(),
        Architecture.model_validate(contract_data()),
        good_files_dict(),
        0,
    )

    assert client.get("/api/projects", headers=headers).json() == []
    assert client.get(f"/api/projects/{legacy_id}", headers=headers).status_code == 404