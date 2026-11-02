
import json
from collections import Counter

import time

from pydantic import ValidationError

from app.schemas.tool_args import WriteFileArgs
from app.services.llm import LLMError, ask_with_tools
from app.tools.file_tools import ToolError, write_file
from app.tools.write_file_tool import WRITE_FILE_TOOL
import app.services.llm as llm_service


request_attempts = 0

_original_create_completion_once = llm_service._create_completion_once


def _counted_create_completion_once(**request_args):
    global request_attempts
    request_attempts += 1
    return _original_create_completion_once(**request_args)


llm_service._create_completion_once = _counted_create_completion_once


RUNS = 10
WORKSPACE = __import__("pathlib").Path(__file__).resolve().parents[2] / "generated_app"

PROMPT = """
Create a complete script.js file for a simple interactive welcome page.
The page contains a button with id="welcomeButton" and a paragraph with
id="message". When the button is clicked, change the paragraph text to
"Welcome! Your app is working." Use plain JavaScript without libraries.
Write the complete file using the write_file tool. The filename must be
script.js.
"""


def run_once():
    try:
        result = ask_with_tools(
            prompt=PROMPT,
            tools=[WRITE_FILE_TOOL],
            tool_choice="required",
        )
    except LLMError as exc:
        print(f"  LLM_ERROR: {exc}")
        return "llm_error"

    if not result.tool_calls:
        print(f"  NO_TOOL_CALL: {result.content}")
        return "no_tool_call"

    if len(result.tool_calls) != 1:
        print(f"  UNEXPECTED_TOOL_CALL_COUNT: {len(result.tool_calls)}")
        return "unexpected_tool_call_count"

    call = result.tool_calls[0]

    if call.name != "write_file":
        print(f"  UNKNOWN_TOOL: {call.name}")
        return "unknown_tool"

    try:
        raw_arguments = json.loads(call.arguments)
    except json.JSONDecodeError as exc:
        print(f"  INVALID_JSON: {exc}")
        return "invalid_json"

    try:
        args = WriteFileArgs.model_validate(raw_arguments)
    except ValidationError as exc:
        print(f"  VALIDATION_ERROR: {exc}")
        return "validation_error"

    if args.filename != "script.js":
        print(f"  WRONG_FILENAME: {args.filename}")
        return "wrong_filename"

    try:
        path = write_file(WORKSPACE, args.filename, args.content)
    except ToolError as exc:
        print(f"  FILE_TOOL_ERROR: {exc}")
        return "file_tool_error"

    print(f"  SUCCESS: Wrote {path.name} ({len(args.content)} characters)")
    return "success"



def main():
    counts = Counter()
    durations = []

    for run_number in range(1, RUNS + 1):
        print(f"\nRun {run_number}/{RUNS}")

        start = time.perf_counter()
        outcome = run_once()
        duration = time.perf_counter() - start

        durations.append(duration)
        counts[outcome] += 1

        print(f"  Duration: {duration:.2f} seconds")

    print("\n=== script.js tally (after retries) ===")

    for category in (
        "success",
        "llm_error",
        "no_tool_call",
        "unexpected_tool_call_count",
        "unknown_tool",
        "invalid_json",
        "validation_error",
        "wrong_filename",
        "file_tool_error",
    ):
        print(f"{category}: {counts[category]}")

    total_runs = sum(counts.values())
    successes = counts["success"]

    print(f"\nTotal runs: {total_runs}")
    print(f"Success rate: {successes / total_runs:.0%}")
    print(f"Average duration: {sum(durations) / len(durations):.2f} seconds")
    print(f"Slowest run: {max(durations):.2f} seconds")
    print(f"Total API attempts: {request_attempts}")
    print(f"Extra API attempts: {request_attempts - RUNS}")


if __name__ == "__main__":
    main()
