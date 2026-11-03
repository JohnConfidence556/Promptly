
import json

import pytest

from app.agents import architect
from app.services.llm import LLMResult

from app.agents.architect import ArchitectError, parse_architecture
from tests.test_architecture import valid_architecture
from tests.test_graph import make_plan_object

def test_parse_broken_json():
    with pytest.raises(ArchitectError, match="invalid JSON"):
        parse_architecture("{broken json")


def test_parse_json_array_instead_of_object():
    with pytest.raises(ArchitectError, match="top-level value was not an object"):
        parse_architecture("[]")


def test_parse_valid_json_with_wrong_shape():
    raw = json.dumps({"unexpected": "shape"})

    with pytest.raises(ArchitectError, match="does not match the schema"):
        parse_architecture(raw)


def test_parse_valid_architecture():
    raw = json.dumps(valid_architecture())

    result = parse_architecture(raw)

    assert result.file_tasks[0].filename == "index.html"

def fake_reply(text):
    return LLMResult(reply=text, prompt_tokens=1, completion_tokens=1, total_tokens=2)


def test_rejected_reply_is_retried_with_the_error_shown(monkeypatch):
    prompts = []
    replies = [json.dumps({"unexpected": "shape"}), json.dumps(valid_architecture())]

    def fake_ask(prompt, system, json_mode, **kwargs):
        prompts.append(prompt)
        return fake_reply(replies.pop(0))

    monkeypatch.setattr(architect, "ask_with_usage", fake_ask)

    result = architect.design_architecture(make_plan_object())

    assert result.file_tasks[0].filename == "index.html"
    assert len(prompts) == 2
    assert "previous reply was rejected" in prompts[1]


def test_gives_up_after_the_maximum_attempts(monkeypatch):
    calls = []

    def fake_ask(prompt, system, json_mode, **kwargs):
        calls.append(prompt)
        return fake_reply("{broken")

    monkeypatch.setattr(architect, "ask_with_usage", fake_ask)

    with pytest.raises(ArchitectError, match="invalid JSON"):
        architect.design_architecture(make_plan_object())

    assert len(calls) == architect.MAX_DESIGN_ATTEMPTS