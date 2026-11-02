from pathlib import Path

class ToolError(Exception):

    """Raised when a file-writing request is invalid or unsafe."""


ALLOWED_FILENAMES = {"index.html", "style.css", "script.js"}
MAX_CONTENT_BYTES = 100 * 1024 # 100 KB

def write_file(workspace: Path, filename: str, content: str) -> Path:
    """Safely write content to an allowed file inside the workspace."""

    # 1. Validate the filename.
    if filename not in ALLOWED_FILENAMES:
        raise ToolError(
            f"Filename '{filename}' is not allowed."
        )

    # 2. Reject absolute paths and nested paths.
    requested_path = Path(filename)

    if requested_path.is_absolute():
        raise ToolError("Absolute file paths are not allowed.")

    if requested_path.name != filename:
        raise ToolError("Subdirectories are not allowed.")

    # 3. Resolve the workspace and target paths.
    workspace_path = workspace.resolve()
    target_path = (workspace_path / requested_path).resolve()

    # 4. Ensure the target stays inside the workspace.
    if not target_path.is_relative_to(workspace_path):
        raise ToolError("The target path is outside the workspace.")

    # 5. Enforce the content size limit.
    if not isinstance(content, str):
        raise ToolError("File content must be a string.")

    content_size = len(content.encode("utf-8"))

    if content_size > MAX_CONTENT_BYTES:
        raise ToolError(
            f"Content exceeds the {MAX_CONTENT_BYTES}-byte limit."
        )

    # 6. Write the file only after validation succeeds.
    try:
        workspace_path.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"Could not write file: {exc}") from exc

    return target_path