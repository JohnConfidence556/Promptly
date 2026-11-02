from app.services.runlog import summarize


def test_summary_splits_time_and_tokens_by_step():
    events = [
        {"type": "llm", "t": 1.0, "prompt_tokens": 100, "completion_tokens": 50},
        {"type": "step", "step": "planner", "t": 2.0},
        {"type": "waiting", "t": 2.5, "seconds": 5},
        {"type": "llm", "t": 8.0, "prompt_tokens": 200, "completion_tokens": 80},
        {"type": "step", "step": "architect", "t": 9.0},
    ]

    summary = summarize(events, total_seconds=9.5)

    assert summary["duration_seconds"] == 9.5
    assert summary["prompt_tokens"] == 300
    assert summary["completion_tokens"] == 130
    assert summary["llm_calls"] == 2
    assert summary["wait_seconds"] == 5.0

    planner, architect = summary["steps"]
    assert planner == {
        "step": "planner",
        "seconds": 2.0,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "llm_calls": 1,
        "waited": 0.0,
    }
    assert architect["seconds"] == 7.0
    assert architect["waited"] == 5.0
    assert architect["prompt_tokens"] == 200


def test_activity_outside_any_step_still_counts_in_totals():
    summary = summarize(
        [{"type": "llm", "t": 1.0, "prompt_tokens": 10, "completion_tokens": 5}], 2.0
    )

    assert summary["steps"] == []
    assert summary["prompt_tokens"] == 10
    assert summary["llm_calls"] == 1


def test_events_are_read_in_time_order():
    events = [
        {"type": "step", "step": "architect", "t": 6.0},
        {"type": "step", "step": "planner", "t": 2.0},
    ]

    steps = summarize(events, 6.0)["steps"]

    assert [step["step"] for step in steps] == ["planner", "architect"]
    assert [step["seconds"] for step in steps] == [2.0, 4.0]