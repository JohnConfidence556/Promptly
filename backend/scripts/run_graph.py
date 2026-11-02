import logging
import sys
import time
from pathlib import Path

from app.agents.graph import stream_build

logging.basicConfig(level=logging.INFO)

WORKSPACE = Path(__file__).resolve().parent.parent / "workspace" / "demo"


def main():
    request = " ".join(sys.argv[1:]) or (
        "Build a simple calculator with number buttons, arithmetic "
        "operations, a display, and an equals button."
    )
    print(f"REQUEST: {request}\n")

    started = time.monotonic()
    final = {}

    for step, update in stream_build(request, WORKSPACE):
        elapsed = time.monotonic() - started
        print(f"[{elapsed:6.1f}s] finished step: {step}")
        final.update(update)

    if final.get("status") == "passed":
        print(f"\nBuild passed after {final.get('fix_rounds', 0)} fix round(s).")
        print(f"Open this file in your browser: {WORKSPACE / 'index.html'}")
    else:
        print(f"\nBUILD FAILED: {final.get('error', 'unknown error')}")


if __name__ == "__main__":
    main()