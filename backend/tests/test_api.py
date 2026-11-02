import json

import pytest
from fastapi.testclient import TestClient

from app.agents.validator import ValidationReport
from app.api import builds
from app.db import repository
from app.main import app
from app.schemas.architecture import Architecture
from tests.test_graph import make_plan_object
from app.schemas.edit_plan import EditPlan
from tests.test_validator import contract_data, good_files_dict
from tests.constants import TEST_USER
import time
from tests.constants import TEST_USER
from app import config

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_slot(monkeypatch):
    monkeypatch.setattr(builds, "BUILD_SLOT", builds.BuildSlot(max_age_seconds=60))


def parse_events(text):
    events = []
    for block in text.strip().split("\n\n"):
        if block.startswith(":"):
            continue  # keep-alive comment
        lines = block.splitlines()
        name = lines[0].removeprefix("event: ")
        data = json.loads(lines[1].removeprefix("data: "))
        events.append((name, data))
    return events


def use_steps(monkeypatch, steps):
    def fake_stream(request, workspace, time_limit=300.0, emit=None):
        yield from steps

    monkeypatch.setattr(builds, "stream_build", fake_stream)


def passing_steps():
    return [
        ("planner", {"plan": make_plan_object()}),
        ("architect", {"architecture": Architecture.model_validate(contract_data())}),
        ("coder", {"files": good_files_dict()}),
        ("validator", {"report": ValidationReport()}),
        ("writer", {"status": "passed"}),
    ]


def post_build():
    return client.post("/api/builds/stream", json={"prompt": "a calculator"})


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_successful_build_streams_events_and_saves_a_project(monkeypatch):
    use_steps(monkeypatch, passing_steps())

    response = post_build()
    events = parse_events(response.text)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [name for name, _ in events] == [
        "started", "step", "step", "step", "step", "step", "result",
    ]
    assert [data["step"] for name, data in events if name == "step"] == [
        "planner", "architect", "coder", "validator", "writer",
    ]

    result = events[-1][1]
    assert result["status"] == "passed"
    assert result["version"] == 1
    assert result["files"] == ["index.html", "script.js", "style.css"]

    saved = repository.get_version(result["project_id"], 1)
    assert saved["files"] == good_files_dict()


def test_failed_build_reports_the_error_and_saves_nothing(monkeypatch):
    use_steps(monkeypatch, [("planner", {"status": "failed", "error": "boom"})])

    events = parse_events(post_build().text)

    assert events[1] == ("step", {"step": "planner", "error": "boom"})
    assert events[-1][1]["status"] == "failed"
    assert events[-1][1]["error"] == "boom"
    assert events[-1][1]["project_id"] is None
    assert repository.list_projects() == []


def test_unexpected_error_becomes_a_failed_result_and_frees_the_slot(monkeypatch):
    def exploding(request, workspace, time_limit=300.0, emit=None):
        raise RuntimeError("bug")
        yield  # makes this a generator

    monkeypatch.setattr(builds, "stream_build", exploding)

    events = parse_events(post_build().text)
    assert events[-1][1]["status"] == "failed"
    assert "Internal error" in events[-1][1]["error"]

    use_steps(monkeypatch, passing_steps())
    again = parse_events(post_build().text)
    assert again[-1][1]["status"] == "passed"


@pytest.mark.parametrize("body", [{"prompt": "hi"}, {}])
def test_invalid_requests_are_rejected(body):
    assert client.post("/api/builds/stream", json=body).status_code == 422


def test_second_build_is_refused_while_one_runs():
    assert builds.BUILD_SLOT.try_acquire()

    response = post_build()

    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_slot_allows_one_build_at_a_time():
    slot = builds.BuildSlot(max_age_seconds=60)

    assert slot.try_acquire() is True
    assert slot.try_acquire() is False
    slot.release()
    assert slot.try_acquire() is True


def test_abandoned_slot_can_be_taken_over():
    slot = builds.BuildSlot(max_age_seconds=0)

    assert slot.try_acquire() is True
    assert slot.try_acquire() is True

def make_project():
    project_id, _ = repository.save_new_project(
        "a calculator",
        make_plan_object(),
        Architecture.model_validate(contract_data()),
        good_files_dict(),
        0,
        user_id=TEST_USER["id"],
    )
    return project_id


def edit_steps():
    edited = good_files_dict()
    edited["style.css"] = ".calculator { display: grid; color: green; }"
    edit_plan = EditPlan.model_validate(
        {
            "summary": "Make it green",
            "edits": [{"filename": "style.css", "instruction": "Make it green"}],
        }
    )
    steps = [
        (
            "edit_planner",
            {
                "edit_plan": edit_plan,
                "architecture": Architecture.model_validate(contract_data()),
            },
        ),
        ("editor", {"files": edited, "edited_files": ["style.css"]}),
        ("validator", {"report": ValidationReport()}),
        ("writer", {"status": "passed"}),
    ]
    return steps, edited


def use_edit_steps(monkeypatch, steps, captured=None):
    def fake_edit(instruction, plan, architecture, files, time_limit=300.0, emit=None):
        if captured is not None:
            captured.update(
                instruction=instruction, plan=plan, architecture=architecture, files=files
            )
        yield from steps

    monkeypatch.setattr(builds, "stream_edit", fake_edit)


def post_edit(project_id):
    return client.post(
        f"/api/projects/{project_id}/edits/stream", json={"prompt": "make it green"}
    )


def test_edit_saves_a_new_version(monkeypatch):
    project_id = make_project()
    steps, edited = edit_steps()
    use_edit_steps(monkeypatch, steps)

    events = parse_events(post_edit(project_id).text)

    assert [data["step"] for name, data in events if name == "step"] == [
        "edit_planner",
        "editor",
        "validator",
        "writer",
    ]
    result = events[-1][1]
    assert result["status"] == "passed"
    assert result["project_id"] == project_id
    assert result["version"] == 2
    assert repository.get_version(project_id, 2)["files"] == edited
    assert repository.get_version(project_id, 1)["files"] == good_files_dict()


def test_edit_starts_from_the_latest_version(monkeypatch):
    project_id = make_project()
    steps, _ = edit_steps()
    captured = {}
    use_edit_steps(monkeypatch, steps, captured)

    post_edit(project_id)

    assert captured["instruction"] == "make it green"
    assert captured["files"] == good_files_dict()
    assert captured["plan"].app_name == "Calc"


def test_editing_an_unknown_project_returns_404_without_taking_the_slot():
    assert post_edit("000000000000").status_code == 404
    assert builds.BUILD_SLOT.try_acquire() is True


def test_failed_edit_adds_no_version(monkeypatch):
    project_id = make_project()
    use_edit_steps(
        monkeypatch, [("edit_planner", {"status": "failed", "error": "nope"})]
    )

    events = parse_events(post_edit(project_id).text)

    assert events[-1][1]["status"] == "failed"
    assert len(repository.get_project(project_id)["versions"]) == 1


def test_edit_is_refused_while_a_build_runs():
    project_id = make_project()
    assert builds.BUILD_SLOT.try_acquire()

    assert post_edit(project_id).status_code == 429
    

def test_progress_events_are_relayed(monkeypatch):
    announcement = {"kind": "file", "file": "index.html", "state": "started", "action": "write"}

    def fake_stream(request, workspace, time_limit=300.0, emit=None):
        emit(announcement)
        yield from passing_steps()

    monkeypatch.setattr(builds, "stream_build", fake_stream)

    events = parse_events(post_build().text)

    assert events[0][0] == "started"
    assert events[1] == ("progress", announcement)
    assert events[-1][0] == "result"


def test_idle_builds_send_keep_alive_comments(monkeypatch):
    monkeypatch.setattr(builds, "HEARTBEAT_SECONDS", 0.05)

    def slow_stream(request, workspace, time_limit=300.0, emit=None):
        time.sleep(0.3)
        yield from passing_steps()

    monkeypatch.setattr(builds, "stream_build", slow_stream)

    response = post_build()

    assert ": keep-alive" in response.text
    assert parse_events(response.text)[-1][1]["status"] == "passed"


def test_build_finishes_and_saves_even_if_nobody_listens():
    def make_steps(emit):
        yield from passing_steps()

    def save(final):
        return repository.save_new_project(
            "a calculator",
            final["plan"],
            final["architecture"],
            final["files"],
            0,
            user_id=TEST_USER["id"],
        )

    assert builds.BUILD_SLOT.try_acquire()
    builds._start_build(make_steps, save)  # nobody reads the events

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if repository.list_projects_for_user(TEST_USER["id"]):
            break
        time.sleep(0.02)

    assert len(repository.list_projects_for_user(TEST_USER["id"])) == 1

    while time.monotonic() < deadline and not builds.BUILD_SLOT.try_acquire():
        time.sleep(0.02)
    assert builds.BUILD_SLOT.try_acquire() is False  # we hold it again; it was freed in between


def test_successful_build_records_a_run(monkeypatch):
    use_steps(monkeypatch, passing_steps())

    result = parse_events(post_build().text)[-1][1]
    runs = repository.list_runs(result["project_id"])

    assert len(runs) == 1
    assert runs[0]["kind"] == "build"
    assert runs[0]["status"] == "passed"
    assert runs[0]["prompt"] == "a calculator"
    assert [step["step"] for step in runs[0]["steps"]] == [
        "planner", "architect", "coder", "validator", "writer",
    ]


def test_edit_records_a_run_with_its_version(monkeypatch):
    project_id = make_project()
    steps, _ = edit_steps()
    use_edit_steps(monkeypatch, steps)

    parse_events(post_edit(project_id).text)
    runs = repository.list_runs(project_id)

    assert runs[0]["kind"] == "edit"
    assert runs[0]["version"] == 2


def test_token_events_go_to_the_run_log_but_not_the_browser(monkeypatch):
    def fake_stream(request, workspace, time_limit=300.0, emit=None):
        emit({"kind": "llm", "prompt_tokens": 120, "completion_tokens": 30})
        yield from passing_steps()

    monkeypatch.setattr(builds, "stream_build", fake_stream)

    events = parse_events(post_build().text)
    run = repository.list_runs(events[-1][1]["project_id"])[0]

    assert all(name != "progress" for name, _ in events)
    assert run["prompt_tokens"] == 120
    assert run["completion_tokens"] == 30
    assert run["llm_calls"] == 1


def test_per_user_daily_limit_refuses_the_next_build(monkeypatch):
    monkeypatch.setattr(config, "DAILY_RUN_LIMIT_PER_USER", 1)
    use_steps(monkeypatch, passing_steps())

    assert post_build().status_code == 200
    response = post_build()

    assert response.status_code == 429
    assert "today" in response.json()["detail"]
    assert builds.BUILD_SLOT.try_acquire() is True  # refused before taking the slot


def test_global_daily_limit_refuses_the_next_build(monkeypatch):
    monkeypatch.setattr(config, "DAILY_RUN_LIMIT_TOTAL", 1)
    use_steps(monkeypatch, passing_steps())

    assert post_build().status_code == 200
    response = post_build()

    assert response.status_code == 429
    assert "daily limit" in response.json()["detail"]