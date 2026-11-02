import sys
import types

import pytest

from app.services import tracing


@pytest.fixture
def langfuse_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")


def test_tracing_does_nothing_without_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    with tracing.observation("span", "anything") as trace:
        trace.update(output="fine")

    tracing.tag_trace(user_id="u", tags=["build"])
    tracing.flush()
    assert tracing.enabled() is False


def test_errors_in_traced_code_still_propagate(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)

    with pytest.raises(ValueError, match="boom"):
        with tracing.observation("span", "anything"):
            raise ValueError("boom")


def test_langfuse_failures_never_break_the_caller(monkeypatch, langfuse_keys):
    broken = types.ModuleType("langfuse")

    def get_client():
        raise RuntimeError("langfuse is down")

    broken.get_client = get_client
    monkeypatch.setitem(sys.modules, "langfuse", broken)

    with tracing.observation("generation", "groq-chat", model="m") as trace:
        trace.update(output="still works")

    tracing.tag_trace(user_id="u", tags=["build"])
    tracing.flush()


def test_enabled_tracing_forwards_to_langfuse(monkeypatch, langfuse_keys):
    calls = []

    class FakeObservation:
        def update(self, **fields):
            calls.append(("update", fields))

    class FakeManager:
        def __enter__(self):
            calls.append(("enter", None))
            return FakeObservation()

        def __exit__(self, *args):
            calls.append(("exit", None))
            return False

    class FakeClient:
        def start_as_current_observation(self, **kwargs):
            calls.append(("start", kwargs))
            return FakeManager()

    fake = types.ModuleType("langfuse")
    fake.get_client = lambda: FakeClient()
    monkeypatch.setitem(sys.modules, "langfuse", fake)

    with tracing.observation("generation", "groq-chat", model="m") as trace:
        trace.update(output="x")

    assert calls[0] == (
        "start",
        {"as_type": "generation", "name": "groq-chat", "model": "m"},
    )
    assert ("update", {"output": "x"}) in calls
    assert calls[-1] == ("exit", None)