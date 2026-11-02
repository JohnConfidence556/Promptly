"""Turn the raw event timeline of a build into a compact, storable summary."""


def _fresh() -> dict:
    return {"prompt_tokens": 0, "completion_tokens": 0, "llm_calls": 0, "waited": 0.0}


def summarize(events: list[dict], total_seconds: float) -> dict:
    """Split a build's time and tokens by step.

    Steps run one after another, so everything that happens between two step
    completions belongs to the later step.
    """
    steps: list[dict] = []
    pending = _fresh()
    totals = _fresh()
    last_t = 0.0

    for event in sorted(events, key=lambda item: item["t"]):
        kind = event.get("type")

        if kind == "llm":
            for bucket in (pending, totals):
                bucket["prompt_tokens"] += int(event.get("prompt_tokens") or 0)
                bucket["completion_tokens"] += int(event.get("completion_tokens") or 0)
                bucket["llm_calls"] += 1
        elif kind == "waiting":
            for bucket in (pending, totals):
                bucket["waited"] += float(event.get("seconds") or 0)
        elif kind == "step":
            steps.append(
                {
                    "step": event["step"],
                    "seconds": round(event["t"] - last_t, 2),
                    "prompt_tokens": pending["prompt_tokens"],
                    "completion_tokens": pending["completion_tokens"],
                    "llm_calls": pending["llm_calls"],
                    "waited": round(pending["waited"], 1),
                }
            )
            last_t = event["t"]
            pending = _fresh()

    return {
        "duration_seconds": round(total_seconds, 2),
        "prompt_tokens": totals["prompt_tokens"],
        "completion_tokens": totals["completion_tokens"],
        "llm_calls": totals["llm_calls"],
        "wait_seconds": round(totals["waited"], 1),
        "steps": steps,
    }