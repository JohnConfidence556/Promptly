import functools
import logging
import time
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.architect import ArchitectError, design_architecture
from app.agents.coder import (
    MAX_FIX_ROUNDS,
    CoderError,
    edit_files,
    generate_initial_files,
    repair_files,
)
from app.agents.editor import EditError, apply_edit_plan, plan_edit
from app.agents.planner import PlanError, make_plan
from app.agents.validator import (
    ValidationReport,
    format_issues_for_model,
    validate_files,
)
from app.schemas.architecture import Architecture
from app.schemas.edit_plan import EditPlan
from app.schemas.plan import Plan
from app.services.errors import LLMError
from app.tools.file_tools import ToolError, write_file

from collections.abc import Callable
from app.services import progress, tracing

logger = logging.getLogger(__name__)

# Overall deadline for one build. Rate-limit waits can add up.
DEFAULT_TIME_LIMIT_SECONDS = 300.0

PIPELINE_ERRORS = (PlanError, ArchitectError, CoderError, EditError, LLMError, ToolError)


class BuildState(TypedDict, total=False):
    """The shared dictionary every step reads from and writes to."""

    request: str
    workspace: Path | None
    deadline: float
    plan: Plan
    architecture: Architecture
    files: dict[str, str]
    report: ValidationReport
    fix_rounds: int
    status: str  # "running", "passed" or "failed"
    error: str
    edit_plan: EditPlan
    edit_instructions: dict[str, str]
    edited_files: list[str]
    emit: Callable[[dict], None]


def _guard(node):
    """Turn expected pipeline errors into a failed state, and wire up progress and tracing."""

    @functools.wraps(node)
    def wrapper(state: BuildState) -> dict:
        token = progress.set_sink(state.get("emit"))
        try:
            with tracing.observation("span", node.__name__.removesuffix("_node")):
                return node(state)
        except PIPELINE_ERRORS as exc:
            logger.error("Step '%s' failed: %s", node.__name__, exc)
            return {"status": "failed", "error": str(exc)}
        finally:
            progress.reset_sink(token)

    return wrapper


@_guard
def planner_node(state: BuildState) -> dict:
    return {"plan": make_plan(state["request"])}


@_guard
def architect_node(state: BuildState) -> dict:
    return {"architecture": design_architecture(state["plan"])}


@_guard
def coder_node(state: BuildState) -> dict:
    files = generate_initial_files(state["plan"], state["architecture"])
    return {"files": files}


def validator_node(state: BuildState) -> dict:
    report = validate_files(state["files"], state["architecture"])
    logger.info("Validation found %s issue(s).", len(report.issues))
    return {"report": report}


@_guard
def repairer_node(state: BuildState) -> dict:
    rounds = state.get("fix_rounds", 0) + 1
    logger.info(
        "Fix round %s: %s issue(s):\n%s",
        rounds,
        len(state["report"].issues),
        format_issues_for_model(state["report"]),
    )
    files = repair_files(
        state["plan"],
        state["architecture"],
        state["files"],
        state["report"],
        state.get("edit_instructions"),
    )
    return {"files": files, "fix_rounds": rounds}

@_guard
def writer_node(state: BuildState) -> dict:
    # The API stores files in the database. A workspace is only used by demo scripts.
    workspace = state.get("workspace")
    if workspace is not None:
        for filename, content in state["files"].items():
            write_file(workspace, filename, content)
    return {"status": "passed"}


@_guard
def edit_planner_node(state: BuildState) -> dict:
    edit_plan = plan_edit(state["plan"], state["architecture"], state["request"])
    architecture = apply_edit_plan(state["architecture"], edit_plan)
    instructions = {edit.filename: edit.instruction for edit in edit_plan.edits}

    return {
        "edit_plan": edit_plan,
        "architecture": architecture,
        "edit_instructions": instructions,
    }


@_guard
def editor_node(state: BuildState) -> dict:
    files = edit_files(
        state["plan"], state["architecture"], state["files"], state["edit_plan"]
    )
    return {"files": files, "edited_files": sorted(state["edit_instructions"])}

def give_up_node(state: BuildState) -> dict:
    report = state["report"]

    if time.monotonic() > state["deadline"]:
        reason = "the time limit was reached"
    else:
        reason = f"{state.get('fix_rounds', 0)} fix round(s) were used"

    return {
        "status": "failed",
        "error": (
            f"The app still has {len(report.issues)} validation issue(s) "
            f"and {reason}.\n{format_issues_for_model(report)}"
        ),
    }


def _continue_or_end(next_node: str):
    """Go to the next step, unless an earlier step already failed."""

    def route(state: BuildState) -> str:
        return END if state.get("status") == "failed" else next_node

    return route


def route_after_validation(state: BuildState) -> str:
    if state["report"].passed:
        return "writer"

    if time.monotonic() > state["deadline"]:
        return "give_up"

    if state.get("fix_rounds", 0) >= MAX_FIX_ROUNDS:
        return "give_up"

    return "repairer"


def build_graph():
    # Node names must differ from state keys, so "plan" would not work here.
    builder = StateGraph(BuildState)

    builder.add_node("planner", planner_node)
    builder.add_node("architect", architect_node)
    builder.add_node("coder", coder_node)
    builder.add_node("validator", validator_node)
    builder.add_node("repairer", repairer_node)
    builder.add_node("writer", writer_node)
    builder.add_node("give_up", give_up_node)

    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", _continue_or_end("architect"))
    builder.add_conditional_edges("architect", _continue_or_end("coder"))
    builder.add_conditional_edges("coder", _continue_or_end("validator"))
    builder.add_conditional_edges("validator", route_after_validation)
    builder.add_conditional_edges("repairer", _continue_or_end("validator"))
    builder.add_edge("writer", END)
    builder.add_edge("give_up", END)

    return builder.compile()


GRAPH = build_graph()

def build_edit_graph():
    # Same validate/repair/write steps as a fresh build, with an edit front end.
    builder = StateGraph(BuildState)

    builder.add_node("edit_planner", edit_planner_node)
    builder.add_node("editor", editor_node)
    builder.add_node("validator", validator_node)
    builder.add_node("repairer", repairer_node)
    builder.add_node("writer", writer_node)
    builder.add_node("give_up", give_up_node)

    builder.add_edge(START, "edit_planner")
    builder.add_conditional_edges("edit_planner", _continue_or_end("editor"))
    builder.add_conditional_edges("editor", _continue_or_end("validator"))
    builder.add_conditional_edges("validator", route_after_validation)
    builder.add_conditional_edges("repairer", _continue_or_end("validator"))
    builder.add_edge("writer", END)
    builder.add_edge("give_up", END)

    return builder.compile()


EDIT_GRAPH = build_edit_graph()


def _initial_state(
    request: str,
    workspace: Path | None,
    time_limit: float,
    emit: "Callable[[dict], None] | None" = None,
) -> BuildState:
    state: BuildState = {
        "request": request,
        "workspace": workspace,
        "deadline": time.monotonic() + time_limit,
        "fix_rounds": 0,
        "status": "running",
    }
    if emit is not None:
        state["emit"] = emit
    return state


def _stream(compiled, initial: BuildState):
    for chunk in compiled.stream(initial, stream_mode="updates"):
        for node_name, update in chunk.items():
            yield node_name, update


def stream_build(
    request: str,
    workspace: Path | None,
    time_limit: float = DEFAULT_TIME_LIMIT_SECONDS,
    emit: "Callable[[dict], None] | None" = None,
):
    """Yield (step_name, state_update) as each step finishes."""
    yield from _stream(GRAPH, _initial_state(request, workspace, time_limit, emit))


def stream_edit(
    instruction: str,
    plan: Plan,
    architecture: Architecture,
    files: dict[str, str],
    time_limit: float = DEFAULT_TIME_LIMIT_SECONDS,
    emit: "Callable[[dict], None] | None" = None,
):
    """Yield (step_name, state_update) while editing an existing app."""
    initial = _initial_state(instruction, None, time_limit, emit)
    initial.update(
        {"plan": plan, "architecture": architecture, "files": dict(files)}
    )
    yield from _stream(EDIT_GRAPH, initial)


def run_build(
    request: str,
    workspace: Path | None,
    time_limit: float = DEFAULT_TIME_LIMIT_SECONDS,
) -> dict:
    """Run the whole pipeline and return the final state."""
    initial = _initial_state(request, workspace, time_limit)
    final = dict(initial)

    for _node_name, update in _stream(GRAPH, initial):
        final.update(update)

    return final