
from app.schemas.tool_args import WriteFileArgs


WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": (
            "Write content to one allowed file in the application workspace. "
            "Allowed filenames are index.html, style.css, and script.js. "
            "Use only a filename, never a path. "
            "The content must be non-empty and contain the complete file."
        ),
        "parameters": WriteFileArgs.model_json_schema(),
    },
}
