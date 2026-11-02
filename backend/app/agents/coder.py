import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.agents.validator import (
    ValidationReport,
    format_issues_for_model,
    validate_files,
)
from app.schemas.architecture import Architecture
from app.schemas.plan import Plan
from app.services.llm import ToolCallResult, ask_with_tools
from app.tools.file_tools import write_file
from app.schemas.edit_plan import EditPlan

from app.services import progress

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "coder.md"

GENERATION_ORDER = ("index.html", "style.css", "script.js")

# Which already-written files each file is shown, so it matches real markup.
CONTEXT_FILES = {
    "index.html": (),
    "style.css": ("index.html",),
    "script.js": ("index.html",),
}

# Retries for unusable model OUTPUT (no tool call, bad arguments).
# Network and rate-limit failures are retried separately inside llm.py.
MAX_GENERATION_ATTEMPTS = 2

# Rounds of "show the model its problems and regenerate the broken files".
MAX_FIX_ROUNDS = 2

# Hidden reasoning counts as completion tokens, so keep it low for Coder calls.
CODER_REASONING_EFFORT = "low"

# Worst case per build: 3 initial files + 2 fix rounds x up to 3 files = 9 file
# generations. Each generation can take 2 attempts, and each attempt up to 3
# HTTP tries, so about 54 HTTP calls. A normal build is 3. The graph will add
# an overall deadline for the whole request.


class CoderError(Exception):
    """Raised when the model's output for one file is unusable."""


class BuildError(Exception):
    """Raised when the app still fails validation after all fix rounds."""

    def __init__(self, report: ValidationReport, fix_rounds: int):
        super().__init__(
            f"The app still has {len(report.issues)} validation issue(s) "
            f"after {fix_rounds} fix round(s)."
        )
        self.report = report
        self.fix_rounds = fix_rounds


@dataclass
class BuildResult:
    files: dict[str, str]
    fix_rounds: int
    report: ValidationReport


def _load_instructions() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoderError("Could not load Coder instructions.") from exc



def _write_file_tool(filename: str) -> dict:
    """Generate content for one specific file."""
    return {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                f"Generate the complete contents of {filename}. "
                "The target filename is already fixed. "
                "Provide only the content argument. "
                "Call this exactly once."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The complete file content.",
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
    }



def _build_prompt(
    filename: str,
    plan: Plan,
    architecture: Architecture,
    existing_files: dict[str, str],
    issues_text: str | None,
    current_content: str | None,
    edit_instruction: str | None = None,
) -> str:
    task = next(
        item.task for item in architecture.file_tasks if item.filename == filename
    )
    contract_json = architecture.model_dump_json(exclude={"file_tasks"})

    sections = [
        f"# Target file\n{filename}",
        f"# Plan\n{plan.model_dump_json()}",
        f"# Shared contract\n{contract_json}",
    ]

    if edit_instruction:
        sections.append(f"# Requested change for {filename}\n{edit_instruction}")
    else:
        sections.append(f"# Task for {filename}\n{task}")

    for name in CONTEXT_FILES[filename]:
        if name in existing_files:
            sections.append(
                f"# Current {name} (already written; match it exactly)\n"
                f"```\n{existing_files[name]}\n```"
            )

    if issues_text:
        sections.append(
            f"# Problems found in your previous version of {filename}\n"
            f"{issues_text}"
        )
        sections.append(
            f"# Your previous version of {filename}\n```\n{current_content}\n```\n"
            "Fix every problem above and return the complete corrected file."
        )
    elif edit_instruction:
        sections.append(
            f"# Current {filename}\n```\n{current_content}\n```\n"
            "Apply the requested change and return the complete updated file. "
            "Keep everything that was not asked to change. "
            "If nothing needs to change, return the file unchanged."
        )

    return "\n\n".join(sections)



def _parse_arguments(raw: str, filename: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error(
            "Coder tool arguments were not valid JSON: %r",
            raw[:500],
        )
        raise CoderError(
            "The model sent tool arguments that are not valid JSON."
        ) from exc

    if not isinstance(data, dict):
        raise CoderError(
            "The model's tool arguments were not a JSON object."
        )

    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        raise CoderError(
            f"The model sent empty or non-text content for {filename}."
        )

    return content


def _extract_content(result: ToolCallResult, filename: str) -> str:
    if not result.tool_calls:
        raise CoderError("The model replied without calling the write_file tool.")

    if len(result.tool_calls) != 1:
        raise CoderError(
            f"The model made {len(result.tool_calls)} tool calls; expected exactly one."
        )

    call = result.tool_calls[0]
    if call.name != "write_file":
        raise CoderError(f"The model called an unknown tool '{call.name}'.")

    return _parse_arguments(call.arguments, filename)


def generate_file(
    filename: str,
    plan: Plan,
    architecture: Architecture,
    existing_files: dict[str, str],
    issues_text: str | None = None,
    current_content: str | None = None,
    edit_instruction: str | None = None,
) -> str:
    """Ask the model to write one file and return its content."""
    prompt = _build_prompt(
        filename,
        plan,
        architecture,
        existing_files,
        issues_text,
        current_content,
        edit_instruction,
    )
    system = _load_instructions()
    tools = [_write_file_tool(filename)]

    action = "fix" if issues_text else "edit" if edit_instruction else "write"
    progress.emit(
        {"kind": "file", "file": filename, "state": "started", "action": action}
    )

    last_error: CoderError | None = None

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        result = ask_with_tools(
            prompt=prompt,
            tools=tools,
            system=system,
            tool_choice="required",
            reasoning_effort=CODER_REASONING_EFFORT,
        )

        logger.info(
            "Coder call for %s: prompt_tokens=%s completion_tokens=%s",
            filename,
            result.prompt_tokens,
            result.completion_tokens,
        )
        try:
            content = _extract_content(result, filename)
        except CoderError as exc:
            last_error = exc
            logger.warning(
                "Unusable Coder output for %s (attempt %s/%s): %s",
                filename,
                attempt,
                MAX_GENERATION_ATTEMPTS,
                exc,
            )
        else:
            progress.emit(
                {"kind": "file", "file": filename, "state": "done", "action": action}
            )
            return content

    raise CoderError(
        f"Could not get a usable {filename} after "
        f"{MAX_GENERATION_ATTEMPTS} attempts: {last_error}"
    ) from last_error



def generate_initial_files(plan: Plan, architecture: Architecture) -> dict[str, str]:
    """Generate all three files in order, each seeing the files before it."""
    files: dict[str, str] = {}

    for filename in GENERATION_ORDER:
        files[filename] = generate_file(filename, plan, architecture, files)

    return files


def repair_files(
    plan: Plan,
    architecture: Architecture,
    files: dict[str, str],
    report: ValidationReport,
    edit_instructions: dict[str, str] | None = None,
) -> dict[str, str]:
    """Regenerate only the files that have issues; return the updated files."""
    repaired = dict(files)

    for filename in GENERATION_ORDER:
        file_issues = [issue for issue in report.issues if issue.file == filename]
        if not file_issues:
            continue

        repaired[filename] = generate_file(
            filename,
            plan,
            architecture,
            repaired,
            issues_text=format_issues_for_model(ValidationReport(file_issues)),
            current_content=repaired[filename],
            edit_instruction=(edit_instructions or {}).get(filename),
        )

    return repaired


def edit_files(
    plan: Plan,
    architecture: Architecture,
    files: dict[str, str],
    edit_plan: EditPlan,
) -> dict[str, str]:
    """Regenerate only the files named in the edit plan, in dependency order."""
    instructions = {edit.filename: edit.instruction for edit in edit_plan.edits}
    updated = dict(files)

    for filename in GENERATION_ORDER:
        if filename not in instructions:
            continue

        updated[filename] = generate_file(
            filename,
            plan,
            architecture,
            updated,
            current_content=updated[filename],
            edit_instruction=instructions[filename],
        )

    return updated


def build_app(
    plan: Plan,
    architecture: Architecture,
    workspace: Path,
    max_fix_rounds: int = MAX_FIX_ROUNDS,
) -> BuildResult:
    """Generate all three files, validate, fix, and write only if valid."""
    files = generate_initial_files(plan, architecture)
    report = validate_files(files, architecture)
    fix_rounds = 0

    while not report.passed and fix_rounds < max_fix_rounds:
        fix_rounds += 1
        logger.info(
            "Fix round %s: %s issue(s):\n%s",
            fix_rounds,
            len(report.issues),
            format_issues_for_model(report),
        )
        files = repair_files(plan, architecture, files, report)
        report = validate_files(files, architecture)

    if not report.passed:
        raise BuildError(report, fix_rounds)

    for filename, content in files.items():
        write_file(workspace, filename, content)

    return BuildResult(files=files, fix_rounds=fix_rounds, report=report)