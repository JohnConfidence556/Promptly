import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.schemas.architecture import Architecture
from app.schemas.plan import Plan
from app.services.errors import LLMError
from app.services.llm import ask_with_usage


logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "architect.md"


class ArchitectError(Exception):
    """Raised when the Architect cannot produce a valid architecture."""


def _load_instructions() -> str:
    """Load the Architect instructions from the prompt file."""
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise ArchitectError("Could not load Architect instructions.") from exc


def parse_architecture(raw: str) -> Architecture:
    """Parse and validate the Architect's JSON response."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Architect returned invalid JSON. Raw reply: %r", raw)
        raise ArchitectError("The Architect returned invalid JSON.") from exc

    if not isinstance(data, dict):
        logger.error("Architect JSON was not an object. Raw reply: %r", raw)
        raise ArchitectError(
            "The Architect returned JSON, but the top-level value was not an object."
        )

    try:
        return Architecture.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'architecture'}: "
            f"{error['msg']}"
            for error in exc.errors()
        )
        logger.error(
            "Architect output failed schema validation: %s. Raw reply: %r",
            details,
            raw,
        )
        raise ArchitectError(
            f"The Architect returned an architecture that does not match "
            f"the schema: {details}"
        ) from exc


def design_architecture(plan: Plan) -> Architecture:
    """Design a shared contract for the files described by a validated Plan."""
    instructions = _load_instructions()

    system_prompt = (
        f"{instructions}\n\n"
        "# Required JSON schema\n"
        "Your output must conform to this schema:\n"
        f"{json.dumps(Architecture.model_json_schema(), indent=2)}"
    )

    try:
        result = ask_with_usage(
            prompt=json.dumps(plan.model_dump(), indent=2),
            system=system_prompt,
            json_mode=True,
        )
    except LLMError as exc:
        raise ArchitectError(f"Architect LLM request failed: {exc}") from exc

    # Log usage BEFORE parsing: failed generations still spend your quota.
    logger.info(
        "Architect call finished: prompt_tokens=%s completion_tokens=%s",
        result.prompt_tokens,
        result.completion_tokens,
    )

    return parse_architecture(result.reply)