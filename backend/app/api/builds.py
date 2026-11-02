import json
import logging
import queue
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.agents.graph import DEFAULT_TIME_LIMIT_SECONDS, stream_build, stream_edit
from app.api.auth import current_user
from app.api.projects import PROJECT_ID_PATTERN
from app.db import repository
from app.schemas.architecture import Architecture
from app.schemas.plan import Plan
from app.services import runlog, tracing
from app import config


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Seconds of silence before the server sends a keep-alive comment.
HEARTBEAT_SECONDS = 10.0


class BuildSlot:
    """Allows one build at a time. A slot older than max_age is treated as abandoned."""

    def __init__(self, max_age_seconds: float):
        self._lock = threading.Lock()
        self._taken_at: float | None = None
        self._max_age = max_age_seconds

    def try_acquire(self) -> bool:
        with self._lock:
            now = time.monotonic()
            if self._taken_at is not None and now - self._taken_at < self._max_age:
                return False
            self._taken_at = now
            return True

    def release(self) -> None:
        with self._lock:
            self._taken_at = None


BUILD_SLOT = BuildSlot(max_age_seconds=DEFAULT_TIME_LIMIT_SECONDS + 60)

def _check_quota(user: dict) -> None:
    """Refuse requests once daily limits are reached."""
    if repository.count_runs_since(24, user_id=user["id"]) >= config.DAILY_RUN_LIMIT_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You've used your {config.DAILY_RUN_LIMIT_PER_USER} builds and edits "
                "for today. Come back tomorrow."
            ),
            headers={"Retry-After": "3600"},
        )

    if repository.count_runs_since(24) >= config.DAILY_RUN_LIMIT_TOTAL:
        raise HTTPException(
            status_code=429,
            detail="Promptly has reached its daily limit. Please come back tomorrow.",
            headers={"Retry-After": "3600"},
        )


class BuildRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(min_length=3, max_length=2000)


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def describe_update(step: str, update: dict) -> dict:
    """Pick the small, useful parts of a step's state update for the browser."""
    if "error" in update:
        return {"error": update["error"]}

    if step == "planner" and "plan" in update:
        plan = update["plan"]
        return {
            "app_name": plan.app_name,
            "scope_status": plan.scope_status,
            "scope_note": plan.scope_note,
        }

    if step == "architect" and "architecture" in update:
        architecture = update["architecture"]
        return {
            "element_ids": len(architecture.element_ids),
            "css_classes": len(architecture.css_classes),
            "js_functions": len(architecture.js_functions),
        }

    if step == "coder" and "files" in update:
        return {"files": sorted(update["files"])}

    if step == "validator" and "report" in update:
        report = update["report"]
        return {
            "passed": report.passed,
            "issues": [
                {"file": issue.file, "code": issue.code, "message": issue.message}
                for issue in report.issues
            ],
        }

    if step == "edit_planner" and "edit_plan" in update:
        edit_plan = update["edit_plan"]
        return {
            "summary": edit_plan.summary,
            "files": [edit.filename for edit in edit_plan.edits],
        }

    if step == "editor" and "edited_files" in update:
        return {"files": update["edited_files"]}

    if step == "repairer":
        return {"fix_rounds": update.get("fix_rounds")}

    return {}


def _result_payload(
    status: str,
    fix_rounds: int,
    error: str | None,
    project_id: str | None = None,
    version: int | None = None,
    files: list[str] | None = None,
) -> dict:
    return {
        "status": status,
        "project_id": project_id,
        "version": version,
        "fix_rounds": fix_rounds,
        "files": files or [],
        "error": error,
    }


def _busy() -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Another build is running. Please try again shortly.",
        headers={"Retry-After": "30"},
    )


def _sse_response(events) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _start_build(
    make_steps,
    save,
    initial: dict | None = None,
    *,
    kind: str = "build",
    prompt: str = "",
    user_id: str | None = None,
    project_id: str | None = None,
) -> queue.Queue:
    """Run a build on a background thread and return the queue its events arrive on.

    The thread owns the build, not the browser connection, so the result is saved
    even if the tab is closed halfway through.
    """
    events: queue.Queue = queue.Queue()
    started = time.monotonic()
    timeline: list[dict] = []

    def now() -> float:
        return time.monotonic() - started

    def emit(event: dict) -> None:
        timeline.append({**event, "type": event.get("kind"), "t": now()})
        # Token counts are for the run log only.
        if event.get("kind") != "llm":
            events.put(("progress", event))

    def worker() -> None:
        final: dict = dict(initial or {})

        with tracing.observation(
            "span", f"promptly-{kind}", input={"prompt": prompt}
        ) as root:
            tracing.tag_trace(user_id=user_id, tags=[kind])

            try:
                for step, update in make_steps(emit):
                    final.update(update)
                    timeline.append({"type": "step", "step": step, "t": now()})
                    events.put(
                        ("step", {"step": step, **describe_update(step, update)})
                    )

                fix_rounds = final.get("fix_rounds", 0)

                if final.get("status") == "passed":
                    saved_id, version = save(final)
                    payload = _result_payload(
                        "passed",
                        fix_rounds,
                        None,
                        project_id=saved_id,
                        version=version,
                        files=sorted(final["files"]),
                    )
                else:
                    payload = _result_payload(
                        "failed",
                        fix_rounds,
                        final.get("error") or "The build ended without a result.",
                    )
            except Exception:
                logger.exception("Unexpected error during build")
                payload = _result_payload(
                    "failed",
                    final.get("fix_rounds", 0),
                    "Internal error while building the app.",
                )

            root.update(
                output={
                    "status": payload["status"],
                    "fix_rounds": payload["fix_rounds"],
                    "error": payload["error"],
                }
            )

        try:
            repository.save_run(
                user_id=user_id,
                project_id=payload["project_id"] or project_id,
                version=payload["version"],
                kind=kind,
                prompt=prompt,
                status=payload["status"],
                error=payload["error"],
                fix_rounds=payload["fix_rounds"],
                summary=runlog.summarize(list(timeline), now()),
            )
        except Exception:
            logger.exception("Couldn't save the run log.")

        # Free the slot first, so a new build can start the moment the browser sees the result.
        BUILD_SLOT.release()
        events.put(("result", payload))
        events.put((None, None))

    threading.Thread(target=worker, name="build-worker", daemon=True).start()
    return events


def _relay(events: queue.Queue):
    """Forward queued events to the browser, with keep-alive comments while idle."""
    yield _sse("started", {})

    while True:
        try:
            kind, payload = events.get(timeout=HEARTBEAT_SECONDS)
        except queue.Empty:
            yield ": keep-alive\n\n"
            continue

        if kind is None:
            return

        yield _sse(kind, payload)


def _load_latest_version(project_id: str, user: dict) -> dict:
    owner = (
        repository.get_project_owner(project_id)
        if PROJECT_ID_PATTERN.fullmatch(project_id)
        else None
    )
    if owner is None or owner != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found.")

    project = repository.get_project(project_id)
    latest = repository.get_version(project_id, project["versions"][-1]["number"])

    return {
        "plan": Plan.model_validate(latest["plan"]),
        "architecture": Architecture.model_validate(latest["architecture"]),
        "files": latest["files"],
    }


@router.post("/builds/stream")
def stream_build_events(body: BuildRequest, user: dict = Depends(current_user)):
    _check_quota(user)

    if not BUILD_SLOT.try_acquire():
        raise _busy()

    prompt = body.prompt

    def save(final: dict):
        return repository.save_new_project(
            prompt,
            final["plan"],
            final["architecture"],
            final["files"],
            final.get("fix_rounds", 0),
            user_id=user["id"],
        )

    events = _start_build(
        lambda emit: stream_build(prompt, None, emit=emit),
        save,
        kind="build",
        prompt=prompt,
        user_id=user["id"],
    )
    return _sse_response(_relay(events))


@router.post("/projects/{project_id}/edits/stream")
def stream_edit_events(
    project_id: str, body: BuildRequest, user: dict = Depends(current_user)
):
    base = _load_latest_version(project_id, user)

    _check_quota(user)

    if not BUILD_SLOT.try_acquire():
        raise _busy()

    prompt = body.prompt

    def save(final: dict):
        version = repository.add_version(
            project_id,
            prompt,
            final["plan"],
            final["architecture"],
            final["files"],
            final.get("fix_rounds", 0),
        )
        if version is None:
            raise RuntimeError("The project disappeared while it was being edited.")
        return project_id, version

    events = _start_build(
        lambda emit: stream_edit(
            prompt, base["plan"], base["architecture"], base["files"], emit=emit
        ),
        save,
        initial=base,
        kind="edit",
        prompt=prompt,
        user_id=user["id"],
        project_id=project_id,
    )
    return _sse_response(_relay(events))