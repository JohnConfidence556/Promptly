import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.auth import current_user
from app.db import repository

router = APIRouter(prefix="/api")

PROJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")

FILE_MEDIA_TYPES = {
    "index.html": "text/html",
    "style.css": "text/css",
    "script.js": "text/javascript",
}

# Even if generated code slipped a network call past the Validator,
# the browser will refuse to make it.
FILE_HEADERS = {
    "Content-Security-Policy": "connect-src 'none'",
    "X-Content-Type-Options": "nosniff",
}


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Not found.")


def _require_project(project_id: str, user: dict) -> None:
    """404 unless the project exists and belongs to this user."""
    owner = (
        repository.get_project_owner(project_id)
        if PROJECT_ID_PATTERN.fullmatch(project_id)
        else None
    )
    if owner is None or owner != user["id"]:
        raise _not_found()


def _require_version(project_id: str, number: int) -> dict:
    if not PROJECT_ID_PATTERN.fullmatch(project_id) or number < 1:
        raise _not_found()

    version = repository.get_version(project_id, number)
    if version is None:
        raise _not_found()

    return version


@router.get("/projects")
def list_projects(user: dict = Depends(current_user)):
    return repository.list_projects_for_user(user["id"])


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: dict = Depends(current_user)):
    _require_project(project_id, user)

    project = repository.get_project(project_id)
    if project is None:
        raise _not_found()

    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, user: dict = Depends(current_user)):
    _require_project(project_id, user)
    repository.delete_project(project_id)
    return Response(status_code=204)


@router.get("/projects/{project_id}/versions/{number}")
def get_version(project_id: str, number: int, user: dict = Depends(current_user)):
    _require_project(project_id, user)
    return _require_version(project_id, number)


@router.post("/projects/{project_id}/versions/{number}/restore")
def restore_version(
    project_id: str, number: int, user: dict = Depends(current_user)
):
    _require_project(project_id, user)

    new_number = repository.copy_version(project_id, number) if number >= 1 else None
    if new_number is None:
        raise _not_found()

    return {"project_id": project_id, "version": new_number}


# Public by link: an iframe can't send an Authorization header, and the
# project id is unguessable. Nothing here exposes prompts or plans.
@router.get("/projects/{project_id}/versions/{number}/files/{filename}")
def get_version_file(project_id: str, number: int, filename: str):
    if filename not in FILE_MEDIA_TYPES:
        raise _not_found()

    version = _require_version(project_id, number)
    content = version["files"].get(filename)
    if content is None:
        raise _not_found()

    return Response(
        content=content,
        media_type=FILE_MEDIA_TYPES[filename],
        headers=FILE_HEADERS,
    )

@router.get("/projects/{project_id}/runs")
def list_project_runs(project_id: str, user: dict = Depends(current_user)):
    _require_project(project_id, user)
    return repository.list_runs(project_id)