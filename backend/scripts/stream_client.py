import sys

import httpx

URL = "http://localhost:8000/api/builds/stream"


def main():
    prompt = " ".join(sys.argv[1:]) or (
        "Build a simple calculator with number buttons, arithmetic "
        "operations, a display, and an equals button."
    )

    with httpx.stream("POST", URL, json={"prompt": prompt}, timeout=None) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                print(line)


if __name__ == "__main__":
    main()