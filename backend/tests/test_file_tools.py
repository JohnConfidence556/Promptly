
import pytest

from app.tools.file_tools import ToolError, write_file


@pytest.mark.parametrize(
    "filename",
    ["index.html", "style.css", "script.js"],
)
def test_write_file_accepts_allowed_filenames(tmp_path, filename):
    content = "Hello from my app"

    result = write_file(tmp_path, filename, content)

    assert result == tmp_path.resolve() / filename
    assert result.read_text(encoding="utf-8") == content


def test_write_file_rejects_parent_directory_traversal(tmp_path):
    with pytest.raises(ToolError, match="not allowed"):
        write_file(tmp_path, "../evil.txt", "malicious content")


def test_write_file_rejects_absolute_path(tmp_path):
    absolute_path = str((tmp_path / "index.html").resolve())

    with pytest.raises(ToolError, match="not allowed"):
        write_file(tmp_path, absolute_path, "Hello")


def test_write_file_rejects_subdirectory_path(tmp_path):
    with pytest.raises(ToolError, match="not allowed"):
        write_file(tmp_path, "sub/index.html", "Hello")


def test_write_file_rejects_disallowed_extension(tmp_path):
    with pytest.raises(ToolError, match="not allowed"):
        write_file(tmp_path, "index.py", "print('Hello')")


def test_write_file_rejects_oversized_content(tmp_path):
    content = "a" * (100 * 1024 + 1)

    with pytest.raises(ToolError, match="limit"):
        write_file(tmp_path, "index.html", content)


def test_write_file_does_not_write_when_rejected(tmp_path):
    with pytest.raises(ToolError):
        write_file(tmp_path, "../evil.txt", "malicious content")

    assert not (tmp_path.parent / "evil.txt").exists()
