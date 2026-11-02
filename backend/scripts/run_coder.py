import logging
import sys
from pathlib import Path

from app.agents.architect import ArchitectError, design_architecture
from app.agents.coder import BuildError, CoderError, build_app
from app.agents.planner import PlanError, make_plan
from app.agents.validator import format_issues_for_model
from app.services.errors import LLMError

logging.basicConfig(level=logging.INFO)

WORKSPACE = Path(__file__).resolve().parent.parent / "workspace" / "demo"


def main():
    request = " ".join(sys.argv[1:]) or (
        "Build a simple calculator with number buttons, arithmetic "
        "operations, a display, and an equals button."
    )
    print(f"REQUEST: {request}\n")

    try:
        plan = make_plan(request)
        architecture = design_architecture(plan)
        result = build_app(plan, architecture, WORKSPACE)
    except BuildError as exc:
        print(f"\nBUILD FAILED: {exc}\n")
        print(format_issues_for_model(exc.report))
        return
    except (PlanError, ArchitectError, CoderError, LLMError) as exc:
        print(f"\nFAILED: {exc}")
        return

    print(f"\nBuild passed after {result.fix_rounds} fix round(s).")
    print(f"Open this file in your browser: {WORKSPACE / 'index.html'}")


if __name__ == "__main__":
    main()