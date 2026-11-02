
from app.agents.planner import _load_instructions
from app.services.llm import ask
from app.schemas.plan import Plan

import json


def main():
    request = "Build a todo list with add, complete, and delete features."

    system_prompt = (
        f"{_load_instructions()}\n\n"
        "# Required JSON schema\n"
        "Your output must conform to this schema:\n"
        f"{json.dumps(Plan.model_json_schema(), indent=2)}"
    )

    reply = ask(
        prompt=request,
        system=system_prompt,
        json_mode=False,
    )

    print("RAW MODEL REPLY:")
    print(reply)


if __name__ == "__main__":
    main()
