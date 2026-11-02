
import logging

from app.agents.planner import make_plan
from app.agents.architect import design_architecture, ArchitectError
from app.services.llm import ask_with_usage


logging.basicConfig(level=logging.INFO)

EXAMPLES = [
    "Build a simple calculator with number buttons, arithmetic operations, "
    "a display, and an equals button.",
]


def main():
    for index, request in enumerate(EXAMPLES, start=1):
        print(f"\n{'=' * 60}")
        print(f"Example {index}: {request}")

        try:
            plan = make_plan(request)
            print("\nPLAN:")
            print(plan.model_dump_json(indent=2))

            architecture = design_architecture(plan)
            print("\nARCHITECTURE:")
            print(architecture.model_dump_json(indent=2))

        except ArchitectError as exc:
            print(f"\nARCHITECTURE FAILED: {exc}")
        except Exception as exc:
            print(f"\nEXAMPLE FAILED: {exc}")


if __name__ == "__main__":
    main()
