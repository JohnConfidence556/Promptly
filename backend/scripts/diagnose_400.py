
import json

from groq import APIStatusError

from app.config import GROQ_MODEL
from app.schemas.plan import Plan
from app.services.llm import client
from app.agents.planner import _load_instructions


request = "Build me a Python web server using FastAPI."

system_prompt = (
    f"{_load_instructions()}\n\n"
    "# Required JSON schema\n"
    "Your output must conform to this schema:\n"
    f"{json.dumps(Plan.model_json_schema(), indent=2)}"
)

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": request},
]

for json_mode in (True, False):
    print(f"\n--- json_mode={json_mode} ---")

    try:
        args = {
            "model": GROQ_MODEL,
            "messages": messages,
        }

        if json_mode:
            args["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**args)
        print("RAW REPLY:")
        print(response.choices[0].message.content)

    except APIStatusError as exc:
        print("HTTP STATUS:", exc.status_code)
        print("MESSAGE:", getattr(exc, "message", None))
        print("BODY:", repr(getattr(exc, "body", None)))

        if getattr(exc, "response", None) is not None:
            print("RESPONSE TEXT:", exc.response.text)
