
import pytest
from pydantic import ValidationError

from app.schemas.tool_args import WriteFileArgs


def test_valid_arguments():
    args = WriteFileArgs(
        filename="index.html",
        content="<h1>Hello</h1>",
    )

    assert args.filename == "index.html"
    assert args.content == "<h1>Hello</h1>"


def test_rejects_invalid_filename():
    with pytest.raises(ValidationError):
        WriteFileArgs(
            filename="../hello.txt",
            content="Hello",
        )


def test_rejects_empty_content():
    with pytest.raises(ValidationError):
        WriteFileArgs(
            filename="index.html",
            content="",
        )


def test_rejects_extra_arguments():
    with pytest.raises(ValidationError):
        WriteFileArgs(
            filename="index.html",
            content="Hello",
            workspace="../../",
        )


def test_generates_json_schema():
    schema = WriteFileArgs.model_json_schema()

    assert "filename" in schema["properties"]
    assert "content" in schema["properties"]
