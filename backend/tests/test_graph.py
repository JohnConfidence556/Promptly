from types import SimpleNamespace

import pytest

from app.agents import graph
from app.agents.planner import PlanError
from app.schemas.architecture import Architecture
from app.schemas.plan import Plan
from tests.test_validator import contract_data, good_files_dict
from app.agents.editor import EditError
from app.schemas.edit_plan import EditPlan
from app.services import progress


def make_plan_object():
    return Plan.model_validate(
        {
            "app_name": "Calc",
            "summary": "A small calculator app.",
            "features": ["Add numbers"],
            "visual_style_notes": "Dark and minimal",
            "scope_status": "supported",
            "scope_note": "Fully supported.",
        }
    )


def files_with_forbidden_call():
    files = good_files_dict()
    files["script.js"] += "\nfetch('/x');"
    return files


@pytest.fixture
def stubs(monkeypatch):
    """Stub every LLM-backed step and count how often each one runs."""
    state = SimpleNamespace(
        calls={"plan": 0, "architect": 0, "generate": 0, "repair": 0},
        generated=good_files_dict(),
        repaired=good_files_dict(),
    )

    def fake_make_plan(request):
        state.calls["plan"] += 1
        return make_plan_object()

    def fake_design_architecture(plan):
        state.calls["architect"] += 1
        return Architecture.model_validate(contract_data())

    def fake_generate(plan, architecture):
        state.calls["generate"] += 1
        return dict(state.generated)

    def fake_repair(plan, architecture, files, report, edit_instructions=None):
        state.calls["repair"] += 1
        return dict(state.repaired)

    monkeypatch.setattr(graph, "make_plan", fake_make_plan)
    monkeypatch.setattr(graph, "design_architecture", fake_design_architecture)
    monkeypatch.setattr(graph, "generate_initial_files", fake_generate)
    monkeypatch.setattr(graph, "repair_files", fake_repair)

    return state


def test_clean_build_passes_without_repairs(stubs, tmp_path):
    result = graph.run_build("a calculator", tmp_path)

    assert result["status"] == "passed"
    assert result["fix_rounds"] == 0
    assert stubs.calls["repair"] == 0
    for filename in ("index.html", "style.css", "script.js"):
        assert (tmp_path / filename).exists()


def test_problem_is_repaired_in_one_round(stubs, tmp_path):
    stubs.generated = files_with_forbidden_call()

    result = graph.run_build("a calculator", tmp_path)

    assert result["status"] == "passed"
    assert result["fix_rounds"] == 1
    assert stubs.calls["repair"] == 1


def test_build_gives_up_after_max_fix_rounds(stubs, tmp_path):
    stubs.generated = files_with_forbidden_call()
    stubs.repaired = files_with_forbidden_call()

    result = graph.run_build("a calculator", tmp_path)

    assert result["status"] == "failed"
    assert stubs.calls["repair"] == graph.MAX_FIX_ROUNDS
    assert "forbidden_api" in result["error"]
    assert list(tmp_path.iterdir()) == []


def test_planner_error_stops_the_pipeline(stubs, monkeypatch, tmp_path):
    def failing_plan(request):
        raise PlanError("boom")

    monkeypatch.setattr(graph, "make_plan", failing_plan)

    result = graph.run_build("a calculator", tmp_path)

    assert result["status"] == "failed"
    assert result["error"] == "boom"
    assert stubs.calls["architect"] == 0


def test_expired_time_limit_stops_repairs(stubs, tmp_path):
    stubs.generated = files_with_forbidden_call()

    result = graph.run_build("a calculator", tmp_path, time_limit=-1)

    assert result["status"] == "failed"
    assert "time limit" in result["error"]
    assert stubs.calls["repair"] == 0


def test_steps_stream_in_order(stubs, tmp_path):
    names = [name for name, _ in graph.stream_build("a calculator", tmp_path)]

    assert names == ["planner", "architect", "coder", "validator", "writer"]


def test_repair_path_streams_in_order(stubs, tmp_path):
    stubs.generated = files_with_forbidden_call()

    names = [name for name, _ in graph.stream_build("a calculator", tmp_path)]

    assert names == [
        "planner",
        "architect",
        "coder",
        "validator",
        "repairer",
        "validator",
        "writer",
    ]


@pytest.fixture
def edit_stubs(monkeypatch):
    state = SimpleNamespace(
        calls={"plan_edit": 0, "edit_files": 0, "repair": 0},
        add_ids=[],
        edited=good_files_dict(),
        repaired=good_files_dict(),
        instructions=None,
    )

    def fake_plan_edit(plan, architecture, instruction):
        state.calls["plan_edit"] += 1
        return EditPlan.model_validate(
            {
                "summary": "Make it green",
                "edits": [{"filename": "style.css", "instruction": "Make it green"}],
                "add_element_ids": state.add_ids,
            }
        )

    def fake_edit_files(plan, architecture, files, edit_plan):
        state.calls["edit_files"] += 1
        return dict(state.edited)

    def fake_repair(plan, architecture, files, report, edit_instructions=None):
        state.calls["repair"] += 1
        state.instructions = edit_instructions
        return dict(state.repaired)

    monkeypatch.setattr(graph, "plan_edit", fake_plan_edit)
    monkeypatch.setattr(graph, "edit_files", fake_edit_files)
    monkeypatch.setattr(graph, "repair_files", fake_repair)

    return state


def collect_edit(instruction="make it green"):
    architecture = Architecture.model_validate(contract_data())
    steps, final = [], {}

    for step, update in graph.stream_edit(
        instruction, make_plan_object(), architecture, good_files_dict()
    ):
        steps.append(step)
        final.update(update)

    return steps, final


def test_clean_edit_flows_through_the_edit_graph(edit_stubs):
    steps, final = collect_edit()

    assert steps == ["edit_planner", "editor", "validator", "writer"]
    assert final["status"] == "passed"
    assert final["edited_files"] == ["style.css"]
    assert edit_stubs.calls == {"plan_edit": 1, "edit_files": 1, "repair": 0}


def test_new_contract_items_are_enforced_after_an_edit(edit_stubs):
    edit_stubs.add_ids = [{"name": "history-panel", "purpose": "History"}]
    repaired = good_files_dict()
    repaired["index.html"] = repaired["index.html"].replace(
        "</div>", '<div id="history-panel"></div></div>', 1
    )
    edit_stubs.repaired = repaired

    steps, final = collect_edit()

    assert steps == [
        "edit_planner",
        "editor",
        "validator",
        "repairer",
        "validator",
        "writer",
    ]
    assert final["status"] == "passed"
    assert edit_stubs.instructions == {"style.css": "Make it green"}


def test_edit_planner_error_stops_the_edit(edit_stubs, monkeypatch):
    def failing(plan, architecture, instruction):
        raise EditError("nope")

    monkeypatch.setattr(graph, "plan_edit", failing)

    steps, final = collect_edit()

    assert final["status"] == "failed"
    assert final["error"] == "nope"
    assert edit_stubs.calls["edit_files"] == 0


def test_progress_emitted_inside_a_step_reaches_the_sink(stubs, monkeypatch, tmp_path):
    def noisy_generate(plan, architecture):
        progress.emit({"kind": "file", "file": "index.html", "state": "started"})
        return good_files_dict()

    monkeypatch.setattr(graph, "generate_initial_files", noisy_generate)
    received = []

    list(graph.stream_build("a calculator", tmp_path, emit=received.append))
    progress.emit({"kind": "after the build"})

    assert received == [{"kind": "file", "file": "index.html", "state": "started"}]