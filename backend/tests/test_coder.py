import json
from collections import Counter
import re

import pytest

from app.agents import coder
from app.agents.coder import BuildError, CoderError, build_app, generate_file
from app.schemas.architecture import Architecture
from app.schemas.plan import Plan
from app.services.llm import ToolCall, ToolCallResult
from tests.test_validator import contract_data, good_files_dict
from app.schemas.edit_plan import EditPlan
from app.services import progress


class FakeLLM:
    """Stands in for ask_with_tools. Records prompts and counts calls per file."""

    def __init__(self, responder):
        self.responder = responder
        self.prompts = []
        self.reasoning_efforts = []
        self.calls_per_file = Counter()

    def __call__(
        self,
        prompt,
        tools,
        system=None,
        tool_choice="auto",
        reasoning_effort=None,
    ):
        filename = re.search(r"# Target file\n(\S+)", prompt).group(1)
        self.prompts.append((filename, prompt))
        self.reasoning_efforts.append(reasoning_effort)
        self.calls_per_file[filename] += 1

        content = self.responder(filename, self.calls_per_file[filename])
        arguments = json.dumps({"content": content})
        return ToolCallResult(
            content=None,
            tool_calls=[ToolCall(id="call_1", name="write_file", arguments=arguments)],
        )

@pytest.fixture
def plan():
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


@pytest.fixture
def architecture():
    return Architecture.model_validate(contract_data())


def result_with_arguments(raw, name="write_file"):
    return ToolCallResult(
        content=None, tool_calls=[ToolCall(id="call_1", name=name, arguments=raw)]
    )


def test_generate_file_returns_content(monkeypatch, plan, architecture):
    monkeypatch.setattr(coder, "ask_with_tools", FakeLLM(lambda f, n: "<p>hello</p>"))

    content = generate_file("index.html", plan, architecture, {})

    assert content == "<p>hello</p>"


def test_reply_without_tool_call_is_retried_then_fails(monkeypatch, plan, architecture):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return ToolCallResult(content="Sure!", tool_calls=[])

    monkeypatch.setattr(coder, "ask_with_tools", fake)

    with pytest.raises(CoderError, match="after 2 attempts"):
        generate_file("index.html", plan, architecture, {})

    assert len(calls) == coder.MAX_GENERATION_ATTEMPTS


@pytest.mark.parametrize(
    "raw",
    [
        "{not json",
        json.dumps(["a", "list"]),
        json.dumps({"content": "   "}),
        json.dumps({"content": 42}),
        json.dumps({}),
    ],
)

def test_bad_tool_arguments_are_rejected(monkeypatch, plan, architecture, raw):
    monkeypatch.setattr(
        coder, "ask_with_tools", lambda **kwargs: result_with_arguments(raw)
    )

    with pytest.raises(CoderError):
        generate_file("index.html", plan, architecture, {})


def test_unknown_tool_name_is_rejected(monkeypatch, plan, architecture):
    raw = json.dumps({"filename": "index.html", "content": "<p>x</p>"})
    monkeypatch.setattr(
        coder,
        "ask_with_tools",
        lambda **kwargs: result_with_arguments(raw, name="delete_everything"),
    )

    with pytest.raises(CoderError):
        generate_file("index.html", plan, architecture, {})


def test_successful_build_writes_all_files(monkeypatch, tmp_path, plan, architecture):
    good = good_files_dict()
    fake = FakeLLM(lambda filename, n: good[filename])
    monkeypatch.setattr(coder, "ask_with_tools", fake)

    result = build_app(plan, architecture, tmp_path)

    assert result.fix_rounds == 0
    assert result.report.passed
    for filename in ("index.html", "style.css", "script.js"):
        assert (tmp_path / filename).exists()


def test_style_prompt_includes_html_but_not_script(monkeypatch, tmp_path, plan, architecture):
    good = good_files_dict()
    fake = FakeLLM(lambda filename, n: good[filename])
    monkeypatch.setattr(coder, "ask_with_tools", fake)

    build_app(plan, architecture, tmp_path)
    prompts = dict(fake.prompts)

    assert '<input id="display">' in prompts["style.css"]
    assert "function calculateResult" not in prompts["style.css"]
    assert "# Current" not in prompts["index.html"]


def test_coder_asks_for_low_reasoning_effort(monkeypatch, tmp_path, plan, architecture):
    good = good_files_dict()
    fake = FakeLLM(lambda filename, n: good[filename])
    monkeypatch.setattr(coder, "ask_with_tools", fake)

    build_app(plan, architecture, tmp_path)

    assert set(fake.reasoning_efforts) == {coder.CODER_REASONING_EFFORT}


def test_build_fixes_a_problem_in_one_round(monkeypatch, tmp_path, plan, architecture):
    good = good_files_dict()

    def responder(filename, call_number):
        if filename == "script.js" and call_number == 1:
            return good["script.js"] + "\nfetch('/x');"
        return good[filename]

    fake = FakeLLM(responder)
    monkeypatch.setattr(coder, "ask_with_tools", fake)

    result = build_app(plan, architecture, tmp_path)

    assert result.fix_rounds == 1
    assert fake.calls_per_file["script.js"] == 2
    assert fake.calls_per_file["index.html"] == 1

    script_prompts = [prompt for name, prompt in fake.prompts if name == "script.js"]
    assert "forbidden_api" in script_prompts[1]
    assert (tmp_path / "script.js").read_text(encoding="utf-8") == good["script.js"]


def test_build_gives_up_and_writes_nothing(monkeypatch, tmp_path, plan, architecture):
    good = good_files_dict()

    def responder(filename, call_number):
        if filename == "script.js":
            return good["script.js"] + "\nfetch('/x');"
        return good[filename]

    fake = FakeLLM(responder)
    monkeypatch.setattr(coder, "ask_with_tools", fake)

    with pytest.raises(BuildError) as error:
        build_app(plan, architecture, tmp_path)

    assert error.value.fix_rounds == coder.MAX_FIX_ROUNDS
    assert any(issue.code == "forbidden_api" for issue in error.value.report.issues)
    assert fake.calls_per_file["script.js"] == 1 + coder.MAX_FIX_ROUNDS
    assert list(tmp_path.iterdir()) == []


def test_edit_prompt_includes_instruction_and_current_content(monkeypatch, plan, architecture):
    fake = FakeLLM(lambda filename, n: "body { color: green; }")
    monkeypatch.setattr(coder, "ask_with_tools", fake)

    generate_file(
        "style.css",
        plan,
        architecture,
        good_files_dict(),
        current_content="body { color: red; }",
        edit_instruction="Make buttons green",
    )

    prompt = fake.prompts[0][1]
    assert "# Requested change for style.css" in prompt
    assert "Make buttons green" in prompt
    assert "body { color: red; }" in prompt
    assert "# Task for style.css" not in prompt


def test_edit_files_only_regenerates_named_files(monkeypatch, plan, architecture):
    fake = FakeLLM(lambda filename, n: "/* edited */")
    monkeypatch.setattr(coder, "ask_with_tools", fake)
    edit_plan = EditPlan.model_validate(
        {
            "summary": "Make it greener",
            "edits": [{"filename": "style.css", "instruction": "Make it green"}],
        }
    )

    result = coder.edit_files(plan, architecture, good_files_dict(), edit_plan)

    assert dict(fake.calls_per_file) == {"style.css": 1}
    assert result["style.css"] == "/* edited */"
    assert result["index.html"] == good_files_dict()["index.html"]

def test_file_progress_events_are_emitted(monkeypatch, plan, architecture):
    monkeypatch.setattr(coder, "ask_with_tools", FakeLLM(lambda f, n: "<p>x</p>"))
    received = []

    token = progress.set_sink(received.append)
    try:
        generate_file("index.html", plan, architecture, {})
        generate_file(
            "style.css",
            plan,
            architecture,
            good_files_dict(),
            current_content="x",
            edit_instruction="Make it green",
        )
    finally:
        progress.reset_sink(token)

    assert received == [
        {"kind": "file", "file": "index.html", "state": "started", "action": "write"},
        {"kind": "file", "file": "index.html", "state": "done", "action": "write"},
        {"kind": "file", "file": "style.css", "state": "started", "action": "edit"},
        {"kind": "file", "file": "style.css", "state": "done", "action": "edit"},
    ]