import sys

import httpx

BASE_URL = "http://localhost:8000/api"


def main():
    if len(sys.argv) < 3:
        print('Usage: python -m scripts.edit_client <project_id> "<change request>"')
        return

    project_id = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    url = f"{BASE_URL}/projects/{project_id}/edits/stream"

    with httpx.stream("POST", url, json={"prompt": prompt}, timeout=None) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                print(line)


if __name__ == "__main__":
    main()