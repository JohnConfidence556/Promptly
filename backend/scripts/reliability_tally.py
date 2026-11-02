
import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from app.schemas.tool_args import WriteFileArgs
from app.services.llm import LLMError, ask_with_tools
from app.tools.file_tools import ToolError, write_file
from app.tools.write_file_tool import WRITE_FILE_TOOL


WORKSPACE = Path(__file__).resolve().parents[2] / "generated_app"
RUNS = 10

PROMPT = (
    "Create a simple index.html welcome page. "
    "Include a heading that says 'Hello, World!' and a short paragraph. "
    "Use the write_file tool to write the complete HTML file."
)


def run_once():
    try:
        result = ask_with_tools(
            prompt=PROMPT,
            tools=[WRITE_FILE_TOOL],
            tool_choice="required",
        )
    except LLMError as exc:
        print(f"  LLM/API error: {exc}")
        return "llm_api_error"

    if not result.tool_calls:
        print("  Model returned text without a tool call.")
        return "no_tool_call"

    # Our design expects one file per call.
    if len(result.tool_calls) > 1:
        print("  Model returned multiple tool calls.")
        return "unexpected_multiple_calls"

    call = result.tool_calls[0]

    if call.name != "write_file":
        print(f"  Unknown tool: {call.name}")
        return "unknown_tool"

    try:
        arguments = json.loads(call.arguments)
    except json.JSONDecodeError:
        print("  Tool arguments were malformed JSON.")
        return "invalid_json"

    try:
        validated = WriteFileArgs.model_validate(arguments)
    except ValidationError as exc:
        print(f"  Argument validation failed: {exc}")
        return "argument_validation_failure"

    try:
        path = write_file(
            workspace=WORKSPACE,
            filename=validated.filename,
            content=validated.content,
        )
    except ToolError as exc:
        print(f"  File tool rejected the request: {exc}")
        return "file_tool_failure"

    print(f"  Successfully wrote {path.name}")
    return "successful_write"


def main():
    counts = Counter()

    for run_number in range(1, RUNS + 1):
        print(f"\nRun {run_number}/{RUNS}")
        outcome = run_once()
        counts[outcome] += 1

    print("\n=== Reliability tally ===")

    categories = [
        "successful_write",
        "no_tool_call",
        "invalid_json",
        "unknown_tool",
        "argument_validation_failure",
        "file_tool_failure",
        "unexpected_multiple_calls",
        "llm_api_error",
    ]

    for category in categories:
        print(f"{category}: {counts[category]}")

    print(f"Total runs: {sum(counts.values())}")


if __name__ == "__main__":
    main()
