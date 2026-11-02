import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.schemas.architecture import Architecture
from app.schemas.edit_plan import EditPlan
from app.schemas.plan import Plan
from app.services.errors import LLMError
from app.services.llm import ask_with_usage

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "editor.md"


class EditError(Exception):
    """Raised when an edit cannot be planned or applied."""


def _load_instructions() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise EditError("Could not load Edit planner instructions.") from exc


def _format_errors(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'edit plan'}: "
        f"{error['msg']}"
        for error in exc.errors()
    )


def parse_edit_plan(raw: str) -> EditPlan:
    """Parse and validate the Edit planner's JSON response."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Edit planner returned invalid JSON. Raw reply: %r", raw)
        raise EditError("The Edit planner returned invalid JSON.") from exc

    if not isinstance(data, dict):
        logger.error("Edit planner JSON was not an object. Raw reply: %r", raw)
        raise EditError(
            "The Edit planner returned JSON, but the top-level value was not an object."
        )

    try:
        return EditPlan.model_validate(data)
    except ValidationError as exc:
        details = _format_errors(exc)
        logger.error(
            "Edit plan failed schema validation: %s. Raw reply: %r", details, raw
        )
        raise EditError(
            f"The Edit planner returned a plan that does not match the schema: {details}"
        ) from exc


def apply_edit_plan(architecture: Architecture, edit_plan: EditPlan) -> Architecture:
    """Return the contract after the edit's additions and removals."""
    removed = set(edit_plan.remove_names)

    def merged(items, additions):
        kept = [item for item in items if item.name not in removed]
        existing = {item.name for item in kept}
        new = [item for item in additions if item.name not in existing]
        return [item.model_dump() for item in kept + new]

    data = {
        "element_ids": merged(architecture.element_ids, edit_plan.add_element_ids),
        "css_classes": merged(architecture.css_classes, edit_plan.add_css_classes),
        "js_functions": merged(architecture.js_functions, edit_plan.add_js_functions),
        "file_tasks": [task.model_dump() for task in architecture.file_tasks],
    }

    try:
        return Architecture.model_validate(data)
    except ValidationError as exc:
        raise EditError(
            f"The edit would make the shared contract invalid: {_format_errors(exc)}"
        ) from exc


def plan_edit(plan: Plan, architecture: Architecture, instruction: str) -> EditPlan:
    """Ask the model which files an edit touches and how the contract changes."""
    system_prompt = (
        f"{_load_instructions()}\n\n"
        "# Required JSON schema\n"
        f"{json.dumps(EditPlan.model_json_schema(), separators=(',', ':'))}"
    )
    user_prompt = (
        f"# Plan\n{plan.model_dump_json()}\n\n"
        f"# Current shared contract\n"
        f"{architecture.model_dump_json(exclude={'file_tasks'})}\n\n"
        f"# Requested change\n{instruction}"
    )

    try:
        result = ask_with_usage(
            prompt=user_prompt,
            system=system_prompt,
            json_mode=True,
        )
    except LLMError as exc:
        raise EditError(f"Edit planner LLM request failed: {exc}") from exc

    logger.info(
        "Edit planner call finished: prompt_tokens=%s completion_tokens=%s",
        result.prompt_tokens,
        result.completion_tokens,
    )

    return parse_edit_plan(result.reply)