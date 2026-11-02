
import json

import pytest
from pydantic import ValidationError

from app.schemas.tool_args import WriteFileArgs

from app.services.llm import ToolCallResult
import scripts.test_tool_call as tool_call_script


def process_tool_call(name, arguments):
    """Validate a tool call before executing any file operation."""

    if name != "write_file":
        raise ValueError(f"Unknown tool: {name}")

    try:
        parsed_arguments = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON in tool arguments.") from exc

    try:
        return WriteFileArgs.model_validate(parsed_arguments)
    except ValidationError as exc:
        raise ValueError("Tool arguments failed validation.") from exc


def test_rejects_unknown_tool():
    with pytest.raises(ValueError, match="Unknown tool"):
        process_tool_call("delete_file", '{"filename":"index.html","content":"Hi"}')


def test_rejects_malformed_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        process_tool_call("write_file", '{"filename":')


def test_rejects_invalid_filename():
    arguments = json.dumps({
        "filename": "../hello.txt",
        "content": "Hello",
    })

    with pytest.raises(ValueError, match="failed validation"):
        process_tool_call("write_file", arguments)


def test_rejects_empty_content():
    arguments = json.dumps({
        "filename": "index.html",
        "content": "",
    })

    with pytest.raises(ValueError, match="failed validation"):
        process_tool_call("write_file", arguments)



def test_handles_response_without_tool_calls(monkeypatch, capsys):
    def fake_ask_with_tools(**kwargs):
        return ToolCallResult(
            content="Here is your HTML.",
            tool_calls=[],
        )

    monkeypatch.setattr(
        tool_call_script,
        "ask_with_tools",
        fake_ask_with_tools,
    )

    tool_call_script.main()

    output = capsys.readouterr().out

    assert "NO TOOL CALL" in output
    assert "Here is your HTML." in output

