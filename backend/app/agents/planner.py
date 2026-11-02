
import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.schemas.plan import Plan
from app.services.llm import ask, LLMError


logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "planner.md"


class PlanError(Exception):
    """Raised when the Planner cannot produce a valid plan."""


def _load_instructions() -> str:
    """Load the Planner instructions from the prompt file."""
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise PlanError("Could not load Planner instructions.") from exc


def parse_plan(raw_reply: str) -> Plan:
    """Convert raw JSON text into a validated Plan."""
    try:
        data = json.loads(raw_reply)
    except json.JSONDecodeError as exc:
        logger.error("Planner returned invalid JSON. Raw reply: %r", raw_reply)
        raise PlanError("The Planner returned invalid JSON.") from exc

    if not isinstance(data, dict):
        logger.error(
            "Planner JSON was not an object. Raw reply: %r",
            raw_reply,
        )
        raise PlanError(
            "The Planner returned JSON, but the top-level value was not an object."
        )

    try:
        return Plan.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        logger.error(
            "Planner output failed schema validation: %s. Raw reply: %r",
            details,
            raw_reply,
        )
        raise PlanError(
            f"The Planner returned a plan that does not match the schema: {details}"
        ) from exc


def make_plan(request: str) -> Plan:
    """Generate and validate a plan for a simple web app."""
    if not request.strip():
        raise PlanError("The app request cannot be empty.")

    instructions = _load_instructions()

    system_prompt = (
        f"{instructions}\n\n"
        "# Required JSON schema\n"
        "Your output must conform to this schema:\n"
        f"{json.dumps(Plan.model_json_schema(), indent=2)}"
    )

    try:
        raw_reply = ask(
            prompt=request,
            system=system_prompt,
            json_mode=True,
        )
    except LLMError as exc:
        raise PlanError(f"Planner LLM request failed: {exc}") from exc

    return parse_plan(raw_reply)
